# kubectl-exec

## Goal

Trigger a `kubectl exec` into a running pod to generate an audit event and validate detections for interactive access to containers.

## Safety

Safe. Only a non-destructive read command is run inside the container. No data is written or modified. Runs in an isolated namespace. Designed for test clusters only.

## What gets deployed

A minimal pod (`kubectl-exec-target`) in the `k8s-replay` namespace running a base image with no privileged settings.

## What gets triggered

A `kubectl exec` command runs a shell inside the container, producing both a Kubernetes audit event and a runtime process event.

## Expected runtime evidence

The `kubectl exec` call exits 0 and produces output. A shell process is started inside the container and visible in the audit log as a `pods/exec` event.

## Detection semantics

This scenario produces a `kubectl exec` event against a running container. If a runtime detection tool is installed, it should alert on exec or attach activity to a container. The exact alert name depends on the loaded ruleset and version.

## Known backend-specific variants

Rule names vary by detection tool, ruleset version, and configuration:

- Falco: `Attach/Exec Pod`
- Audit-based: `pods/exec` subresource in Kubernetes audit log

Use this scenario to validate event visibility first, then map it to your local rule names.

## Deploy and trigger

```bash
make scenario-kubectl-exec
```

Clean state is enforced by default. To reuse an existing pod:

```bash
make scenario-kubectl-exec FAST=1
```

JSON output:

```bash
make scenario-kubectl-exec JSON=1
```

## Cleanup

```bash
make cleanup-kubectl-exec
```

## Failure modes

| Symptom | Likely cause |
|---------|--------------|
| Pod stays in `Pending` | Image pull issue or resource constraints on node |
| `behavior: FAIL` | `kubectl exec` returned non-zero or produced no output |
| `detection: NOT VERIFIED` | Ruleset does not include a matching exec rule, or search pattern does not match Falco output text |
| `detection: SKIP` | Falco is not installed — run `make setup-falco` to install |

For detection issues, run `make logs-falco-raw` to inspect actual Falco output and compare against expected patterns in `scenario.yaml`.
