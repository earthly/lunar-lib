## 1\. Repository & Code Quality Standards

### Documentation & Ownership

* README exists and follows "good" format (able to assert a “\#\#” section within the README)  
  * **Easy \- grep might be enough for this, depending on what kind of assertions are needed**  
  * **Idea: We could “collect” all of the section headings into an array and then have policies assert that expected sections exist**  
* CODEOWNERS file exists and is valid  
  * **Easy. We could use something like this for validation: [https://github.com/mszostok/codeowners-validator](https://github.com/mszostok/codeowners-validator)**   
* Service ownership documented in `catalog-info.yaml` (able to assert a key:value in file)  
  * **Easy**  
* Runbook exists in blessed format/location (maybe dir assertion in repo, or existence of content in README or catalog-info file)  
  * **Easy**

### Code Standards

* Language/build version compliance (assert `>=` language version)  
  * **Q: something like ruby runtime version? go runtime version?**  
* .gitignore present  
  * **Easy**  
* .dockerignore present  
  * **Easy \- maybe make conditional on Dockerfile presence**

### Dependency Management

* No EOL dependencies (interesting idea to compare dependencies against [https://endoflife.date/](https://endoflife.date/))  
  * **Best done with the help of the SBOM**  
  * **Lunar can cross-reference with the endoflife API**  
* Critical security vulnerabilities addressed (would confirm Snyk, etc. are ☑️)  
  * **Doable \- we'd need to assume a specific vendor (or set of vendors) and collect scan results into component JSON**  
* Pull from approved repositories/registries only  
  * `FROM [valid options]` in `Dockerfile`  
  * Valid registries from 3rd party deps  
  * **Easy**  
* SBOM (Software Bill of Materials) present (confirm an SBOM was generated in CI)  
  * **Option 1: Would validate that one of the blessed SBOM generator was run, and collect the resulting SBOM based on instrumenting that kind of SBOM generator in their CI/CD**  
  * **Option 2: Require the team to declare their SBOM somehow (e.g. output as artifact), and pick that up.**  
* No restricted libraries (confirm the absence of a dependency)  
  * **Also possibly best done via the SBOM \+ a hardcoded not-allowed list**  
  * **Option 2: Use lock file in Lunar**

## 2\. Build & CI/CD Standards

### Build Requirements

* Service can build locally  
  * **TODO: How can we check this? We can enforce perhaps a standard way to build locally. (e.g. make build, or ./hack/[build.sh](http://build.sh))**  
  * **Or section in readme that documents the local build process?**  
* Service can start locally  
  * **TODO: How can we check this? We can enforce perhaps a standard way to start locally. (e.g. make run or ./hack/[build.sh](http://build.sh))**  
  * **Or section in readme that documents local dev process?**  
* Push artifacts to approved repositories only  
  * **This is likely ecosystem-dependent. E.g. for maven, check X, for Go check Y, for docker, check Z, etc.**  
* No downloading from internet during build  
  * **Q: What do you mean by this exactly? Builds have at least some dependencies. Would those come from an internal artifactory instead?**  
  * **Idea 1: track IP addresses via Lunar CI agent, and have an allow-list**  
  * **Idea 2: Check the build configuration (e.g. look in pom.xml, package.json etc) to ensure it uses the right artifactory**

### Testing Standards

* Unit/integration test failures addressed  
  * **Q: Need more info: e.g. do we merely enforce that CI is passing on main? Are integration tests in a different repo? Something else?**  
* CodeCov check presence  
  * Minimum code coverage requirements  
  * **Doable**  
* Performance test results available  
  * **Q: Need more info \- is every service expected to have this? If they do, where do these results typically live? How would we check this?**  
* Load test results documented (README \#\#? Or standard repo location of .md)  
  * **Easy \- file presence or README grep**

### CI/CD Pipeline

* Reasonable build/CI times (gather \+ report CI times with an opinioned acceptable range)  
  * **Doable \- based on Lunar CI agent data**  
* Yaml schema validation  
  * **There is no buildkite pipeline validator online that I can see. Lunar can at least help lint the YAML. Would this be enough?**  
  * **Q: Is there something specific that needs to be validated?**

## 3\. Deployment & Infrastructure Standards

### Deployment Practices

* Canary deployments implemented (specific key in yaml expected)  
  * **Easy**  
* Gradual rollout strategy (specific key in yaml expected)  
  * **Easy**  
* Last deployment within 30 days (check an API for a result)  
  * **Easy \- via cron collector**  
* Multi-cell deployment capability (specific key in yaml expected)  
  * **Easy**

### Container & Kubernetes Standards

* Proper container image labels showing lineage (assert `LABEL` in `Dockerfile`)  
  * **Doable**  
* Container health checks reflect true service health  
  * **Easy: Make sure that there is a health check declared in the k8s manifest**  
  * **Advanced: Cron collector: Hit the health endpoint in production, and ensure it can contains fields X, Y, Z in the health JSON**  
* Proper handling of Linux signals (SIGTERM handling detection)  
  * **Require that the source location and/or behavior of SIGTERM is documented in a specific .md file**  
  * **AI option: Use an LLM (e.g. Claude) in a Lunar collector \- if Claude finds SIGTERM, then the check passes. Require manual docs if it doesn't pass.**  
* Non-root container execution  
  * **Doable: check that Dockerfile has the USER command (or that the base image that it uses)**  
  * **Alternative: Inspect every container image pushed (docker inspect or curl the registry for the config), and detect that the user config of the image is non-root.**  
  * **Bonus: prevent privileged from being used in k8s manifests**  
* Minimum 3 replicas for high availability (yaml inspection)  
  * **K8s manifest validation \- easy**  
* Pod disruption budget configured (yaml inspection)  
  * **K8s manifest validation \- easy**  
* Defined CPU/memory requirements (yaml inspection)  
  * **K8s manifest validation \- easy**  
* Correct use of Kubernetes primitives (yaml inspection?)  
  * **K8s manifest validation \- should be easy, depends on what exactly**

### Infrastructure Configuration (checks on `*.tf` files)

* Repeatable infrastructure deployment  
  * **Check that they actually use Terraform? (files exist in certain scenarios)**  
  * **Advanced: terraform apply is present in some CI/CD script**  
* Data stores have deletion protection  
  * **Doable: Specific resource types (e.g. EC2, S3) have the setting in TF that have the lifecycle prevent\_destroy set to true**  
* WAF for publicly exposed HTTP services  
  * **When component is tagged as internet-accessible, expect WAF resource exists in TF**  
  * **Also, make sure the service assigns only private VPC addresses (such that only the WAF is exposed, not the service itself)**  
* DDoS protection enabled  
  * **Q: Is this typically configured in TF? What product are you using for ddos?**  
  * **if e.g. using AWS Shield, then can check that this is configured in TF, if exposed on the internet**  
* API gateway integration where necessary  
  * **Q: How would "where necessary" be defined?**

## 4\. Security & Compliance Standards

### Vulnerability Management

* No critical security vulnerabilities  
  * **Integration with specific vendor(s). Which one(s)?**  
  * **Option 1: Detection of scan in CI**  
  * **Option 2: Integration with the vendor via the vendor's REST API. Note that the version of the code (e.g. git sha) needs to be correlated somehow in this case.**  
* Regular vulnerability scans  
  * **Same as above**  
* OWASP Top 10 compliance  
  * **Some of these are covered by vendors (e.g. vuln scanners typically pick up on injection). Lunar can help ensure that those vendors are used correctly by all relevant projects: e.g. SAST, SCA, SonarQube, etc.**  
  * **Things that are not (usually) covered by other vendors, but Lunar can help with:**  
    * **access control (e.g. branch protection, GH access settings)**  
    * **security misconfiguration (technology-specific): [https://owasp.org/Top10/A05\_2021-Security\_Misconfiguration/](https://owasp.org/Top10/A05_2021-Security_Misconfiguration/)**  
    * **software and data integrity failures (e.g. ensure artifacts are signed): [https://owasp.org/Top10/A08\_2021-Software\_and\_Data\_Integrity\_Failures/](https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/)**  
* Dockerfile security scanning  
  * **Q: Is this container image scanning?**  
  * **We can make sure that stuff like Aqua is used in CI/CD.**  
* Passive runtime protection (FIM)  
  * **FIM \= file integrity monitoring. e.g. [https://www.wiz.io/blog/a-hybrid-approach-to-file-integrity-monitoring-agentless-and-runtime-fim](https://www.wiz.io/blog/a-hybrid-approach-to-file-integrity-monitoring-agentless-and-runtime-fim)**  
  * **Q: which solution do you use? How is it installed in production? What's the best way for Lunar to detect use of a FIM? In IaC for the EC2? In the EC2 image?**

### Access & Authentication

* JIT access to production configured  
  * **Q: Is JIT access related to temporary access to prod resources on-demand based on manual approvals?**  
  * **Q: How is this typically configured?**  
* Defined and reviewed JIT approvers  
  * **Check static list of reviewers is declared in their repo**  
  * **Ask them to document review timestamps in some specific location**  
* Proper secrets management  
  * **Q: What's the corporate recommended way?**  
* No secrets in container images  
  * **Now: Trigger on docker push in CI/CD**  
  * **Future: Trigger on ECR new image push**  
  * **Insert an open-source secret scanner (e.g. [https://github.com/deepfence/SecretScanner](https://github.com/deepfence/SecretScanner)) via Lunar**

### Compliance & Privacy

* GDPR region compliance  
  * **TODO(Vlad): Research specific controls.**  
* PCI/SOX compliance where applicable  
  * **TODO(Vlad): Research specific controls.**  
* PII removed from telemetry  
  * **Q: Usually vendors like SonarQube check things like this. Should Lunar enforce the use of such a vendor?**  
* Threat model updated with recent features  
  * **Q: Could use a specific example of an "update" / "threat model" to showcase.**  
* Backstage annotations for compliance regimes  
  * **Doable.**

## 5\. Observability & Monitoring Standards

### Logging & Metrics

* Well-structured logs  
  * **Option 1: Check based on usage of pre-approved list of open-source logging libraries**  
  * **Option 2: Use a specific internal corporate logging library**  
* Golden signals monitored  
  * **Latency, Traffic, Errors, Saturation**  
  * **Idea: ensure that there is a monitoring dashboard (e.g. declare Grafana link in catalog yaml)**  
  * **Possibly include information about what alerts are configured, and require at least 1\.**  
* Request tracing enabled  
  * **Heuristics based on popular technologies. E.g in Ruby, for this framework, ensure that the setting is turned on. Another e.g. a certain dependency is imported.**  
* Service dashboard exists  
  * **Idea: Link in catalog yaml exists**  
* Performance profile change detection  
  * **I imagine this would only be needed for a few performance-critical services. These could be labeled correctly in backstage.**  
  * **Q: Is there a common way in which this detection would be implemented? Lunar could check for that.**

### Health & Reliability

* Proper health probes configured  
  * **See also k8s-based verification above.**  
  * **Advanced: Cron collector on production: Hit the health endpoint in production, and ensure it can contains X fields in the health JSON**  
* SLOs/SLAs defined  
  * **Entry in backstage yaml or README?**  
* Circuit breakers established  
  * **Idea: Check for a certain library existence when there's a catalog API dependency on something critical**  
  * **Idea 2: LLM-based**  
* Deployment time anomaly detection  
  * **Q: Is there a common technology that Twilio uses for this? e.g. Splunk?**

## 6\. Operational Readiness Standards

### On-Call & Incident Management

* Minimum on-call heads defined  
  * **Declared PagerDuty schedule in backstage yaml \+ hit the PD API to check \# of heads**  
* On-call policy established  
  * **Declared PagerDuty schedule in backstage yaml \+ hit the PD API to check status**  
* FireHydrant \+ PagerDuty integration  
  * **Q: Make sure that each team has set up alerts with FH/PD?**  
* Incident readiness validated  
  * **Q: Need more details about what would be validated.**

### Disaster Recovery & Backup

* Data backup/restore mechanism  
  * **Enforce a location to document this (e.g. specific .md file).**  
* Backup testing validated  
  * **Enforce a location to document this (e.g. specific .md file), with timestamp.**  
* Last snapshot findable within X days  
  * **Enforce a location to document this (e.g. specific .md file), with timestamp.**  
* Disaster recovery drills conducted  
  * **Enforce a location to document this (e.g. specific .md file), with timestamp.**  
* Game day exercises (N days since last)  
  * **Enforce a location to document this (e.g. specific .md file), with timestamp.**

### Capacity Planning

* Load projections factored into provisioning  
  * **Enforce a location to document this (e.g. specific .md file).**  
* Scaling factors understood  
  * **Enforce a location to document this (e.g. specific .md file).**  
* Minimum deployment size requirements  
  * **Enforce a location to document this (e.g. specific .md file).**  
* Resource utilization monitoring  
  * **Enforce a location to document this (e.g. specific .md file).**

## 7\. Architecture & Design Standards

### Service Design

* Backstage producer/consumer APIs defined  
  * **Catalog yaml validation**  
* Service catalog referential integrity  
  * **Catalog yaml validation \+ Backstage API call**  
* Blueprint re-review within N months  
  * **Require review timestamp be documented in some .md file**  
* Graceful shutdown implementation  
  * **Enforce a location to document this (e.g. specific .md file).**  
  * **Another idea: LLM-based**

### Integration Standards

* Backstage teams correlate to other systems  
  * **Integration with "other systems" (e.g. Okta? Workday?). Check against those DBs regularly.**  
* Catalog-info matches CODEOWNERS  
  * **Doable**  
  * **Note that catalog info has work emails vs GH has GH users.**  
  * **Call into GH API to fetch user emails, and enforce that everyone includes a twilio email**  
* Inter-region data transfer compliance  
  * **Enforce a location to document this (e.g. specific .md file).**  
* Heightened Awareness Period tracking  
  * **Q: What needs to be tracked specifically here? How would this be surfaced / enforced?**
