"""Require load balancers to enforce HTTPS/TLS for traffic in transit."""

from lunar_policy import Check
from helpers import iter_resources, block


_SECURE = ("https", "tls", "ssl")
# ALB/NLB listener protocols this check can judge. TCP, UDP and TCP_UDP
# listeners pass traffic through without terminating it (TLS, if any, ends
# downstream), and Gateway Load Balancer listeners carry GENEVE.
_JUDGED = ("http", "https", "tls")


def _protocol(listener):
    # protocol is optional on aws_lb_listener; AWS defaults it to HTTP (ALB).
    return str(listener.get("protocol", "HTTP")).lower()


def main(node=None):
    c = Check("aws-elb-https-only", "Load balancers enforce HTTPS/TLS", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        listeners = [
            (rtype, name, cfg)
            for rtype, name, cfg in iter_resources(native, "aws_lb_listener", "aws_alb_listener")
            if _protocol(cfg) in _JUDGED
        ]
        elbs = list(iter_resources(native, "aws_elb"))
        if not listeners and not elbs:
            c.skip("No HTTP, HTTPS or TLS load balancer listeners found")

        offenders = []

        for rtype, name, cfg in listeners:
            if _protocol(cfg) in _SECURE:
                continue
            # A plaintext HTTP listener is OK only if it redirects to HTTPS.
            redirects = any(
                str(action.get("type", "")).lower() == "redirect"
                and any(str(r.get("protocol", "")).upper() == "HTTPS" for r in block(action, "redirect"))
                for action in block(cfg, "default_action")
            )
            if not redirects:
                offenders.append("{}.{}".format(rtype, name))

        # Classic listeners must be HTTPS or SSL, TCP included (Security Hub ELB.3).
        for _, name, cfg in elbs:
            for lst in block(cfg, "listener"):
                if str(lst.get("lb_protocol", "")).lower() not in _SECURE:
                    offenders.append("aws_elb.{}".format(name))
                    break

        if offenders:
            c.fail(
                "Load balancer listeners not enforcing HTTPS/TLS: {}. Use an HTTPS/TLS "
                "listener, or redirect HTTP to HTTPS.".format(", ".join(offenders))
            )
    return c


if __name__ == "__main__":
    main()
