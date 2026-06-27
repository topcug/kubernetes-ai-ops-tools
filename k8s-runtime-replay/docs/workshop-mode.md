# Workshop mode

This guide helps you run k8s-runtime-replay as a structured workshop for a team or conference session.

## Recommended flow (60 minutes)

| Time | Activity |
|------|----------|
| 0–10m | Cluster setup (`make setup-kind`) |
| 10–20m | Falco install and verification (`make setup-falco`) |
| 20–30m | Shell spawn scenario + discussion |
| 30–40m | SA token read + RBAC discussion |
| 40–50m | Secret enumeration + audit log walk |
| 50–60m | Curl egress + NetworkPolicy demo |

## Pre-workshop checklist

```bash
# 1. Verify cluster is reachable
kubectl cluster-info

# 2. List available scenarios
make list-scenarios

# 3. Verify Falco is running (optional)
kubectl get pods -n falco

# 4. Test a quick scenario end-to-end
make scenario-shell-spawn
make cleanup-shell-spawn
```

## Running all scenarios in sequence

```bash
make scenario-shell-spawn
make scenario-sa-token-read
make scenario-kubectl-exec
make scenario-curl-egress
make scenario-secret-enumeration
```

## Full reset

```bash
make reset
```

This deletes the `k8s-replay` namespace and all resources inside it.

## Tips for live demos

- Use `--verbose` in kubectl commands to show what is happening.
- Keep a second terminal open streaming Falco logs: `make logs-falco`
- Use `make list-scenarios` to show the audience what is available.
- Each scenario README has the expected Falco rule output — share it before triggering.
