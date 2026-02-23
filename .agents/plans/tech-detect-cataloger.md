# Tech-Detect Cataloger — Plan

Cataloger plugin that scans component repos and applies tags based on detected technology patterns.

---

## Plugin: `tech-detect`

- Single plugin, 5 sub-catalogers (one per detection category)
- All use `hook: component-repo` — runs on every component repo push
- Each sub-cataloger is its own script — users can `include`/`exclude` individually
- Output: `lunar catalog component --tag <tag>` (no Component JSON, just Catalog tags)
- No custom container needed — file detection is pure bash + grep/find
- Default image: `earthly/lunar-scripts:1.0.0` should suffice

---

## Sub-cataloger 1: `traffic` — HTTP/gRPC detection

**Tags applied:** `http`, `grpc`

**Signals to scan (any match = tag):**

- **Dockerfiles**: `EXPOSE` directives (ports 80, 443, 8080, 8443, 3000, 5000, 9090 etc.)
- **Proto files** (`.proto`): presence of `service` + `rpc` definitions → tag `grpc`
- **Go**: imports of `net/http`, `github.com/gin-gonic`, `github.com/go-chi`, `github.com/labstack/echo`, `github.com/gofiber/fiber`, `google.golang.org/grpc`
- **Node.js**: dependencies in `package.json` — `express`, `fastify`, `koa`, `@nestjs/core`, `hapi`, `@grpc/grpc-js`
- **Python**: dependencies — `flask`, `django`, `fastapi`, `uvicorn`, `gunicorn`, `grpcio`
- **Java**: dependencies in `pom.xml`/`build.gradle` — `spring-boot-starter-web`, `spring-boot-starter-webflux`, `io.grpc`, `javax.ws.rs`, `jakarta.ws.rs`, `micronaut-http-server`, `quarkus-resteasy`
- **Rust**: dependencies in `Cargo.toml` — `actix-web`, `axum`, `rocket`, `warp`, `tonic`
- **K8s manifests**: `Service` resources, `containerPort` definitions, `Ingress` resources

**Design notes:**
- Tag `http` if any HTTP framework/server detected
- Tag `grpc` if proto service defs or gRPC libraries detected
- A component can get both tags
- Don't tag just because a library appears as a transitive dep — check direct dependencies only (top-level `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`/`build.gradle`)

---

## Sub-cataloger 2: `docker-img` — Docker image production

**Tag applied:** `docker-img`

**Signals to scan (any match = tag):**

- **CI configs** (`.github/workflows/*.yml`): `docker push`, `docker/build-push-action`, `docker buildx --push`, `kaniko`, `buildah push`
- **BuildKite pipelines** (`.buildkite/*.yml`): docker push commands
- **Makefile / scripts**: `docker push` commands

**Design notes:**
- Dockerfile existence alone is NOT sufficient — many repos have Dockerfiles purely for local dev/testing that never get pushed to a registry
- The key signal is **push to a registry**, not image creation
- `docker build` without push is not enough — look for `push` specifically

---

## Sub-cataloger 3: `library` — Artifact publishing

**Tag applied:** `library`

**Signals to scan — focus on actual publish/push commands (any match = tag):**

- **CI configs / build scripts**: `npm publish`, `yarn publish`, `twine upload`, `flit publish`, `poetry publish`, `mvn deploy`, `gradle publish`, `cargo publish`, `gem push`, `nuget push`
- **GitHub Actions**: `pypa/gh-action-pypi-publish`, `JS-DevTools/npm-publish`, `gradle/actions/setup-gradle` with publish step
- **Makefile / shell scripts**: any of the above publish commands

**Design notes:**
- Package manifest fields (e.g. `private: true`, `<distributionManagement>`, build-system sections) are unreliable — many repos have these configured but never actually publish
- The reliable signal is **actual publish commands** in CI or build scripts
- If the pipeline pushes an artifact to a registry, it's a library — that's the ground truth

---

## Sub-cataloger 4: `deploy` — Deployment detection

**Tags applied:** `k8s`, `iac`

**Signals to scan:**

**For `k8s` tag (any match):**
- K8s manifest files with `kind: Deployment`, `kind: StatefulSet`, `kind: DaemonSet`, `kind: Service`, `kind: Ingress`
- Helm charts: `Chart.yaml` exists
- Kustomize: `kustomization.yaml` / `kustomization.yml` exists
- ArgoCD: `kind: Application` or `kind: ApplicationSet` in YAML files
- `skaffold.yaml` exists

**For `iac` tag (any match):**
- Terraform: `.tf` files exist
- Pulumi: `Pulumi.yaml` exists
- CloudFormation: YAML/JSON files with `AWSTemplateFormatVersion`
- CDK: `cdk.json` exists
- Ansible: `playbook.yml` or `ansible.cfg` or `roles/` directory

**Design notes:**
- A component can get both `k8s` and `iac` (e.g. Terraform that deploys to K8s)
- Exclude common false positives: K8s client libraries (just importing `k8s.io/client-go` doesn't mean this repo deploys to K8s)
- Look for manifest files in typical directories: `deploy/`, `k8s/`, `kubernetes/`, `infra/`, `terraform/`, `helm/`, `charts/`, `argocd/`

---

## Sub-cataloger 5: `language` — Programming language detection

**Tags applied:** `go`, `javascript`, `typescript`, `python`, `java`, `rust`, `ruby`, `csharp`, `kotlin`, `swift`, etc.

**Signals to scan:**

- **Go**: `go.mod` exists
- **JavaScript**: `package.json` exists (without `tsconfig.json`)
- **TypeScript**: `package.json` + `tsconfig.json` (or `tsconfig*.json`) exists
- **Python**: `pyproject.toml`, `requirements.txt`, `setup.py`, `Pipfile`, or `.python-version` exists
- **Java**: `pom.xml`, `build.gradle`, or `build.gradle.kts` exists
- **Rust**: `Cargo.toml` exists
- **Ruby**: `Gemfile` or `.gemspec` exists
- **C#**: `*.csproj` or `*.sln` files exist
- **Kotlin**: `build.gradle.kts` with kotlin plugin, or `*.kt` files in `src/`
- **Swift**: `Package.swift` exists

**Design notes:**
- A component can get multiple language tags (e.g. a Go backend with a TypeScript frontend)
- Detect based on primary dependency/project files, not by scanning for individual source files (avoids tagging `python` just because of a one-off script)
- TypeScript is tagged instead of (not in addition to) JavaScript when `tsconfig.json` is present
- Kotlin vs Java: `build.gradle.kts` alone isn't enough for Kotlin (Java projects use it too) — look for Kotlin plugin or `.kt` source files

---

## Plugin structure

```
catalogers/tech-detect/
├── lunar-cataloger.yml
├── traffic.sh          # Sub-cataloger: HTTP/gRPC detection
├── docker-img.sh       # Sub-cataloger: Docker image production
├── library.sh          # Sub-cataloger: Artifact publishing
├── deploy.sh           # Sub-cataloger: Deployment detection
├── language.sh         # Sub-cataloger: Language detection
├── assets/tech-detect.svg
├── README.md
└── Earthfile           # If custom image needed (maybe not)
```

---

## Open questions

1. **Tag prefix?** Should tags be prefixed (e.g. `tech-http`, `tech-grpc`) to distinguish auto-detected tags from manually assigned ones? The github-org cataloger uses a configurable prefix (`gh-`). Leaning toward no prefix — these are meant to be the canonical component-type tags.

2. **Confidence / override?** Should there be a way for repos to opt out of a detected tag? E.g. a repo has a Dockerfile but it's only for local dev, not production. Could use a `lunar.yml` override or an input for exclude patterns. Probably a v2 concern.

3. **Depth of dependency scanning?** For traffic detection, how deep do we go? Just top-level dependency files, or also scan source code for import statements? Top-level dependency files are faster and more reliable. Source code scanning catches more but risks false positives. Leaning toward dependency files only for v1.

---

## Implementation order

1. **`language.sh`** — simplest detection (project file existence), easiest to test
2. **`deploy.sh`** — simple detection (file existence checks)
3. **`docker-img.sh`** — fairly simple (CI config scanning for push commands)
4. **`traffic.sh`** — moderate complexity (multi-language dependency parsing)
5. **`library.sh`** — most nuanced (CI config scanning for publish commands)
