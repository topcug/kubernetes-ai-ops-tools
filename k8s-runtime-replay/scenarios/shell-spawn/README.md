# shell-spawn

## Goal

Trigger a shell execution inside a running container to validate runtime detections for shell process events.

## Safety

Safe. No persistent changes are made to the cluster. Runs in an isolated namespace. Designed for test clusters only.

## What gets deployed

A minimal pod (`shell-spawn-target`) in the `k8s-replay` namespace running a base image with no privileged settings.

## What gets triggered

A shell command is executed inside the running container via `kubectl exec`.

## Expected runtime evidence

A `/bin/sh` process visible in the container process tree during execution. The `kubectl exec` call exits 0 and produces output.

## Detection semantics

This scenario produces a shell execution event inside a container. If a runtime detection tool is installed, it should alert on shell execution inside a container. The exact alert name depends on the loaded ruleset and version.

## Known backend-specific variants

Rule names vary by detection tool, ruleset version, and configuration:

- Falco: `Terminal shell in container`, `Shell Spawned in a Container`
- Audit-based: `Attach/Exec Pod`

Use this scenario to validate event visibility first, then map it to your local rule names.

## Deploy and trigger

```bash
make scenario-shell-spawn
```

Clean state is enforced by default. To reuse an existing pod:

```bash
make scenario-shell-spawn FAST=1
```

JSON output:

```bash
make scenario-shell-spawn JSON=1
```

## Cleanup

```bash
make cleanup-shell-spawn
```

## Failure modes

| Symptom | Likely cause |
|---------|--------------|
| Pod stays in `Pending` | Image pull issue or resource constraints on node |
| `exec` fails | Pod not yet ready — increase `ready_seconds` timeout |
| `behavior: FAIL` | `kubectl exec` returned non-zero or produced no output |
| `detection: NOT VERIFIED` | Ruleset does not include a matching rule, or search pattern does not match Falco output text |
| `detection: SKIP` | Falco is not installed — run `make setup-falco` to install |

For detection issues, run `make logs-falco-raw` to inspect actual Falco output and compare against expected patterns in `scenario.yaml`.
