# sa-token-read

## Goal

Read the mounted Kubernetes service account token from inside a container to validate detections for sensitive file access patterns.

## Safety

Safe. The service account created (`replay-sa`) has no RBAC permissions and cannot call the Kubernetes API. Token is read for observation only. Runs in an isolated namespace. Designed for test clusters only.

## What gets deployed

A minimal pod (`sa-token-read-target`) in the `k8s-replay` namespace with a bound service account that has no permissions. The token is mounted at the standard path.

## What gets triggered

A shell command inside the container reads the service account token file at `/var/run/secrets/kubernetes.io/serviceaccount/token`.

## Expected runtime evidence

The token file is readable inside the container. The `kubectl exec` call exits 0 and prints the token length. No API calls are made with the token.

## Detection semantics

This scenario produces a sensitive file read event inside a container. If a runtime detection tool is installed, it should alert on access to the service account token path. The exact alert name depends on the loaded ruleset and version.

## Known backend-specific variants

Rule names vary by detection tool, ruleset version, and configuration:

- Falco: `Read sensitive file untrusted`, `Read sensitive file by trusted program`
- Audit-based: token path access visible in audit log

Use this scenario to validate event visibility first, then map it to your local rule names.

## Deploy and trigger

```bash
make scenario-sa-token-read
```

Clean state is enforced by default. To reuse an existing pod:

```bash
make scenario-sa-token-read FAST=1
```

JSON output:

```bash
make scenario-sa-token-read JSON=1
```

## Cleanup

```bash
make cleanup-sa-token-read
```

## Failure modes

| Symptom | Likely cause |
|---------|--------------|
| Pod stays in `Pending` | Image pull issue or resource constraints on node |
| `behavior: FAIL` | Token file path not readable — check service account mount |
| `detection: NOT VERIFIED` | Ruleset does not include a matching sensitive file rule, or search pattern does not match Falco output text |
| `detection: SKIP` | Falco is not installed — run `make setup-falco` to install |

For detection issues, run `make logs-falco-raw` to inspect actual Falco output and compare against expected patterns in `scenario.yaml`.
