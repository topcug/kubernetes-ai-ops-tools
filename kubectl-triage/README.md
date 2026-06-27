# kubectl-triage

**Collapse the first 60 seconds of Kubernetes incident triage into a single command.**

<p align="center">
  <img src="kubectl-triage.png" alt="kubectl-triage" width="200" />
</p>

[![CI](https://github.com/topcug/kubectl-triage/actions/workflows/ci.yml/badge.svg)](https://github.com/topcug/kubectl-triage/actions/workflows/ci.yml)
[![Go Report Card](https://goreportcard.com/badge/github.com/topcug/kubectl-triage)](https://goreportcard.com/report/github.com/topcug/kubectl-triage)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Before kubectl-triage

```bash
kubectl describe pod payment-api-7d9f8b-xkp2q -n payments
kubectl get events -n payments --field-selector involvedObject.name=payment-api-7d9f8b-xkp2q
kubectl logs payment-api-7d9f8b-xkp2q -n payments --tail=30
kubectl get networkpolicy -n payments
kubectl get rolebindings -n payments
```

## After kubectl-triage

```bash
kubectl triage pod payment-api-7d9f8b-xkp2q -n payments
```

---

## What you see in 60 seconds

```
══ kubectl-triage: payments/payment-api-7d9f8b-xkp2q [Pod] ══
   2026-04-05 17:00:00 UTC

▸ Summary
  - pod is not ready
  - restart loop indicators present
  - image uses :latest (app)
  - service account token is auto-mounted
  - uses default service account
  - no NetworkPolicy selects this workload
  - runAsNonRoot is not set

▸ Workload
  Name                         payment-api-7d9f8b-xkp2q
  Namespace                    payments
  Kind                         Pod
  Phase                        Running
  Node                         node-1
  Ready                        no
  Restarting                   yes

▸ Image
  app → docker.io/myapp:latest  ⚠ :latest

▸ Security
  privileged                   no
  runAsNonRoot                 not set
  readOnlyRootFilesystem       not set
  allowPrivilegeEscalation     not set
  added capabilities           none

▸ Service Account
  name                         default  (default SA)
  automount token              enabled

▸ Key Events
  ⚠ Warning BackOff: Back-off restarting failed container (CrashLoopBackOff)
  ⚠ Warning PolicyViolation: require-run-as-non-root

▸ Log Tail [app]
  container is restarting too quickly to return a stable log tail

▸ Network
  NetworkPolicy                ✗ none — unrestricted
                               ingress/egress may be unrestricted depending on cluster defaults

▸ RBAC
  no direct RoleBinding/ClusterRoleBinding match found for this service account in current lookup

▸ Suggested Next Checks
  - inspect container command and entrypoint — pod is restarting
  - check logs for crash cause — CrashLoopBackOff detected (14x)
  - confirm whether the workload actually needs Kubernetes API access — automount token is enabled
  - consider using a dedicated service account instead of the default one
  - review pod securityContext — runAsNonRoot is not set
  - pin image "app" to a fixed version — :latest may change unexpectedly
  - add a NetworkPolicy — ingress/egress are currently unrestricted

▸ Triage Readout
  This looks like a restart-looping pod with weak security defaults and unrestricted network scope.
```

---

## Install

### Quickstart — go install

```bash
go install github.com/topcug/kubectl-triage@latest
# Binary lands in $(go env GOPATH)/bin
export PATH="$PATH:$(go env GOPATH)/bin"

# Verify
kubectl plugin list | grep triage
kubectl triage --help
```

### Pre-built binary

Download from [GitHub Releases](https://github.com/topcug/kubectl-triage/releases):

```bash
# Linux amd64
curl -L https://github.com/topcug/kubectl-triage/releases/latest/download/kubectl-triage_linux_amd64.tar.gz \
  | tar -xz kubectl-triage
chmod +x kubectl-triage
mv kubectl-triage ~/.local/bin/

# macOS arm64 (Apple Silicon)
curl -L https://github.com/topcug/kubectl-triage/releases/latest/download/kubectl-triage_darwin_arm64.tar.gz \
  | tar -xz kubectl-triage
chmod +x kubectl-triage
mv kubectl-triage /usr/local/bin/
```

Verify the install:

```bash
kubectl plugin list | grep triage
kubectl triage --help
```

### Krew _(planned v1.1)_

```bash
kubectl krew install triage
```

### Build from source

```bash
git clone https://github.com/topcug/kubectl-triage.git
cd kubectl-triage
make install   # installs to $(go env GOPATH)/bin
```

> **How kubectl plugins work:** kubectl discovers any executable on your `$PATH` whose name starts with `kubectl-`. No registration needed — place the binary and run `kubectl triage`.

---

## Usage

### Real-world scenarios

```bash
# Pod is CrashLoopBackOff — what's happening?
kubectl triage pod payment-api-7d9f8b-xkp2q -n payments

# Deployment is stuck — replicas not coming up
kubectl triage deployment payment-api -n payments

# Batch job failed silently — why?
kubectl triage job nightly-reconcile -n finance

# Quick summary only — no full report
kubectl triage pod payment-api-7d9f8b-xkp2q -n payments --quiet

# Full report with owner chain and all events
kubectl triage pod payment-api-7d9f8b-xkp2q -n payments --verbose

# Pipe to jq in a CI script
kubectl triage pod payment-api-7d9f8b-xkp2q -n payments -o json \
  | jq '.summaryBullets[]'

# Paste into a GitHub incident issue
kubectl triage pod payment-api-7d9f8b-xkp2q -n payments -o markdown

# Use a non-default context or kubeconfig
kubectl triage pod payment-api -n payments --context staging
kubectl triage pod payment-api -n payments --kubeconfig ~/.kube/other.yaml
```

### Aliases

`deployment` can be shortened to `deploy` or `dep`:

```bash
kubectl triage deploy payment-api -n payments
```

---

## Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--namespace` | `-n` | `default` | Namespace of the target resource |
| `--output` | `-o` | `table` | Output format: `table`, `json`, `markdown` |
| `--verbose` | `-v` | `false` | Show full event list and owner chain |
| `--quiet` | `-q` | `false` | Show summary bullets and triage readout only |
| `--context` | | current context | Kubernetes context to use |
| `--kubeconfig` | | `$KUBECONFIG` or `~/.kube/config` | Path to kubeconfig file |

---

## Output formats

| Format | Flag | Use case |
|--------|------|----------|
| `table` | default | Terminal, on-call response |
| `json` | `-o json` | `jq` pipelines, CI scripts, monitoring |
| `markdown` | `-o markdown` | GitHub issues, Notion, Slack, incident docs |

See [docs/output-format.md](docs/output-format.md) for the full JSON schema and exit code reference.

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Triage complete — no risk signals detected |
| `1` | Error — resource not found, permission denied, or timeout |
| `2` | Triage complete — risk signals detected |

---

## What it collects

| Section | Details |
|---------|---------|
| **Summary** | Short risk bullet list — shown first, always |
| **Workload** | Name, namespace, phase, node, ready/restarting status |
| **Image** | All containers + init containers, `:latest` flag |
| **Security** | privileged, runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation, capabilities |
| **Service Account** | Name, default SA detection, automount token status |
| **Key Events** | Top 5 events, warnings prioritised — `--verbose` for full list |
| **Log Tail** | Last 30 lines of the primary container |
| **Network** | NetworkPolicy coverage, bound Services |
| **RBAC** | RoleBindings and ClusterRoleBindings for the service account |
| **Suggested Next Checks** | Action-oriented next steps |
| **Triage Readout** | Single-sentence situational summary |

---

## Required permissions

kubectl-triage is **read-only**. It never modifies cluster state.

```
pods, pods/log      — get
events              — list
deployments         — get
jobs                — get
serviceaccounts     — get
networkpolicies     — list
services            — list
rolebindings        — list
clusterrolebindings — list
clusterroles        — get
```

If a permission is missing, the affected section shows a graceful warning and the rest of the report still renders.

---

## Config file

Create `.kubectl-triage.yaml` in your project directory or `$HOME`:

```yaml
defaultNamespace: production
outputFormat: table
timeoutSeconds: 15
verbose: false
quiet: false
```

---

## Design principles

- **Summary first** — risk bullets and triage readout appear before details on every report.
- **Read-only** — never modifies cluster state. No `exec`, `patch`, `cordon`, or `delete`.
- **Fast** — 8-second total timeout. Partial results on permission errors.
- **Scriptable** — `-o json` produces stable output for `jq` or CI pipelines.
- **Kubernetes-native** — respects `KUBECONFIG`, `--context`, and `--namespace` like any kubectl command.
- **Action-oriented** — every recommendation tells you what to do, not just what's wrong.

---

## When not to use

kubectl-triage is a first-response tool, not a compliance scanner or cluster-wide audit tool. See [docs/when-not-to-use.md](docs/when-not-to-use.md) for details.

---

## Development

```bash
make fmt      # format code
make test     # run tests with race detector
make build    # produces ./bin/kubectl-triage
make install  # installs to $(go env GOPATH)/bin
make lint     # run golangci-lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

---

## Roadmap

- [x] v0.1 — pod, deployment, job triage (table / json / markdown)
- [x] v0.1 — CI pipeline, GoReleaser, Krew manifest
- [ ] v0.2 — pre-built binaries on GitHub Releases
- [ ] v0.3 — `kubectl triage namespace <n>` for namespace-wide summary
- [ ] v1.1 — Krew index submission
- [ ] v1.2 — configurable rules via `.kubectl-triage.yaml`
- [ ] v2.0 — `--diff` mode to compare two reports over time

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
