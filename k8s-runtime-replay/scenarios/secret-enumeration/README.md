# secret-enumeration

## Goal

List Kubernetes Secrets from inside a container using the mounted service account token to validate detections for in-cluster API access.

## Safety

Safe. The secret created (`replay-dummy-secret`) contains no real credentials. The service account (`secret-enum-sa`) is scoped to `k8s-replay` namespace only. All RBAC resources are removed by cleanup. Designed for test clusters only.

## What gets deployed

A pod (`secret-enum-target`) in the `k8s-replay` namespace, a service account with list-secrets permission scoped to the namespace, and a dummy secret with placeholder values.

## What gets triggered

A `curl` command inside the container authenticates to the Kubernetes API server using the mounted service account token and lists secrets in the `k8s-replay` namespace.

## Expected runtime evidence

The API call returns a response (secrets list or permission error). The connection to `kubernetes.default.svc` is visible in the container's network activity.

## Detection semantics

This scenario produces an in-cluster Kubernetes API call from inside a container. If a runtime detection tool is installed, it should alert on contact to the Kubernetes API server from a container. The exact alert name depends on the loaded ruleset and version.

## Known backend-specific variants

Rule names vary by detection tool, ruleset version, and configuration:

- Falco: `Contact K8S API Server From Container`, `Kubernetes Client Tool Launched in Container`
- Audit-based: `secrets/list` verb visible in Kubernetes audit log

Use this scenario to validate event visibility first, then map it to your local rule names.

## Deploy and trigger

```bash
make scenario-secret-enumeration
```

Clean state is enforced by default. To reuse an existing pod:

```bash
make scenario-secret-enumeration FAST=1
```

JSON output:

```bash
make scenario-secret-enumeration JSON=1
```

## Cleanup

```bash
make cleanup-secret-enumeration
```

## Failure modes

| Symptom | Likely cause |
|---------|--------------|
| Pod stays in `Pending` | Image pull issue or resource constraints on node |
| `behavior: FAIL` | API call returned no output — RBAC may be blocking or API server unreachable from pod network |
| `detection: NOT VERIFIED` | Ruleset does not include a matching API server contact rule, or search pattern does not match Falco output text |
| `detection: SKIP` | Falco is not installed — run `make setup-falco` to install |
| `403 Forbidden` from API | Service account RBAC not applied — check `manifests/rbac.yaml` was deployed |

For detection issues, run `make logs-falco-raw` to inspect actual Falco output and compare against expected patterns in `scenario.yaml`.
