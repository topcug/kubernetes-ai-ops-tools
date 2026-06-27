# When Not to Use kubectl-triage

kubectl-triage is a first-response tool. It collapses the first 60 seconds of
triage into a single command — it is not a replacement for deeper investigation.

## Don't use it as a compliance scanner

kubectl-triage reports what it sees. It does not audit against CIS benchmarks,
PSS/PSA policies, or custom OPA/Kyverno rules. Use dedicated tools for that:

- [kube-bench](https://github.com/aquasecurity/kube-bench) — CIS Kubernetes Benchmark
- [Polaris](https://github.com/FairwindsOps/polaris) — best-practice auditing
- [Trivy](https://github.com/aquasecurity/trivy) — vulnerability scanning
- [Falco](https://falco.org) — runtime threat detection

## Don't use it for namespace-wide or cluster-wide sweeps

kubectl-triage targets a single named resource. For fleet-wide visibility use:

- `kubectl get pods -A --field-selector=status.phase!=Running`
- [Lens](https://k8slens.dev) or [k9s](https://k9scli.io) for cluster-wide views

Namespace-wide triage (`kubectl triage namespace <n>`) is planned for v0.3.

## Don't rely on it for RBAC completeness

The RBAC section shows RoleBindings and ClusterRoleBindings that reference the
service account by name. It does not evaluate aggregated roles, group memberships,
or impersonation chains. Use `kubectl auth can-i --list` for full permission checks.

## Don't use it as a replacement for `kubectl logs`

The log tail shows the last 30 lines of the primary container only.
For full logs, previous container logs, or multi-container pods use:

```bash
kubectl logs <pod> -c <container> --previous
kubectl logs <pod> --all-containers
```

## Don't use it if the cluster is unreachable

kubectl-triage requires an active kubeconfig with read access to the target
namespace. It will fail fast (8-second timeout) with a clear error if the
cluster is unreachable or credentials are expired.
