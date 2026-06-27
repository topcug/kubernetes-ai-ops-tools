# Output Format Reference

## Table (default)

Coloured terminal output. Sections printed in order:

1. Header — `namespace/name [Kind]` + timestamp
2. Summary — risk bullet list (always first)
3. Workload — name, namespace, kind, phase, node, ready/restarting, replicas
4. Image — container name → image, `:latest` flag
5. Security — per-container: privileged, runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation, capabilities
6. Service Account — name, default SA detection, automount token status
7. Key Events — top 5 (warnings prioritised); `--verbose` shows all
8. Log Tail — last 30 lines of the primary container
9. Network — NetworkPolicy coverage, bound Services
10. RBAC — RoleBindings and ClusterRoleBindings for the service account
11. Suggested Next Checks — action-oriented next steps
12. Triage Readout — single-sentence situational summary

Use `--verbose` to additionally show:
- Owner Chain (Pod → ReplicaSet → Deployment)
- Full event list (not capped at 5)

Use `--quiet` to show only:
- Summary bullets
- Triage Readout

## JSON (`-o json`)

Stable, machine-readable output. Suitable for `jq`, CI scripts, and monitoring pipelines.

Top-level schema:

```json
{
  "target": {
    "kind": "Pod",
    "name": "suspicious-pod",
    "namespace": "payments"
  },
  "workload": {
    "name": "suspicious-pod",
    "namespace": "payments",
    "kind": "Pod",
    "phase": "Running",
    "nodeName": "node-1",
    "isReady": false,
    "isRestarting": true
  },
  "images": [
    { "container": "app", "image": "docker.io/myapp:latest", "isLatest": true, "isInit": false }
  ],
  "security": {
    "containers": [
      {
        "name": "app",
        "privileged": false,
        "runAsNonRoot": null,
        "readOnlyRootFS": null,
        "allowPrivilegeEscalation": null,
        "capabilities": []
      }
    ]
  },
  "serviceAccount": {
    "name": "default",
    "automountServiceAccountToken": true,
    "exists": true,
    "isDefault": true
  },
  "ownership": {
    "entries": [{ "kind": "ReplicaSet", "name": "suspicious-rs", "uid": "..." }]
  },
  "recentEvents": [
    { "type": "Warning", "reason": "BackOff", "message": "...", "count": 14, "age": "5m" }
  ],
  "logs": {
    "container": "app",
    "lines": ["..."],
    "truncated": false,
    "error": ""
  },
  "network": {
    "hasNetworkPolicy": false,
    "policies": [],
    "services": []
  },
  "rbac": {
    "bindings": [],
    "canExec": false,
    "canGetSecrets": false,
    "isOverbroad": false,
    "warnings": []
  },
  "summaryBullets": ["pod is not ready", "restart loop indicators present"],
  "recommendations": ["inspect container command and entrypoint — pod is restarting"],
  "triageReadout": "This looks like a restart-looping pod with weak security defaults.",
  "generatedAt": "2026-04-05T17:00:00Z"
}
```

### Null vs false vs "not set"

Security context fields (`runAsNonRoot`, `readOnlyRootFS`, `allowPrivilegeEscalation`) are `*bool` in Go.
In JSON output:
- `null` — field not set in the manifest (missing, not inherited)
- `true` / `false` — explicitly set

## Markdown (`-o markdown`)

GitHub-flavoured markdown. Suitable for GitHub issues, Notion, Confluence, and Slack (with rendering).

Sections rendered as:
- `## Workload` — table
- `## Images` — table
- `## Security Context` — table
- `## Service Account` — bullet list
- `## Owner Chain` — chained backtick references
- `## Recent Events` — table
- `## Log Tail` — fenced code block
- `## Network` — bullet list
- `## RBAC` — table or `_No role bindings found._`
- `## What to Check Next` — bullet list

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Triage complete — no risk signals detected |
| `1`  | Error — resource not found, permission denied, timeout, or kubeconfig issue |
| `2`  | Triage complete — one or more risk signals detected |
