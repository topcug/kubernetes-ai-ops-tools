# Advanced usage

This document covers JSON output, CI integration, dry-run mode, timeout and retry configuration, custom scenarios, and plugin support.

---

## JSON output

Every scenario supports structured JSON output via the `JSON=1` flag:

```bash
make scenario-shell-spawn JSON=1
```

Output:

```json
{
  "scenario": "shell-spawn",
  "context": "kind-k8s-replay",
  "environment_check": "pass",
  "deploy": "pass",
  "ready": "pass",
  "trigger": "pass",
  "behavior_verification": "pass",
  "detection_backend": "Falco",
  "detection_verification": "pass",
  "overall": "scenario_passed_detection_verified",
  "failure_reason": ""
}
```

The JSON schema is stable. The `overall` field values are:

| Value | Meaning |
|-------|---------|
| `scenario_passed_detection_verified` | Exit 0 |
| `scenario_passed_detection_skipped` | Exit 10 |
| `scenario_passed_detection_not_verified` | Exit 11 |
| `preflight_failed` | Exit 20 |
| `deploy_failed` | Exit 21 |
| `ready_timeout` | Exit 22 |
| `trigger_failed` | Exit 23 |
| `behavior_not_observed` | Exit 24 |

---

## Dry-run mode

Print exactly what a scenario would do without making any cluster changes:

```bash
make scenario-shell-spawn DRY_RUN=1
```

In dry-run mode, `kubectl apply`, `kubectl exec`, and `kubectl delete` calls are printed but not executed. Preflight checks still run.

---

## CI integration

### Basic CI run

```yaml
- name: Run scenario
  run: |
    make scenario-shell-spawn JSON=1
    # exit 0 = pass + detection verified
    # exit 10 = pass + no detection backend
    # exit 11 = pass + detection not verified
    # exit >= 20 = failure
```

### Treating detection-skipped as success

The Makefile already normalizes exit codes 10 and 11 to 0 for all scenario targets. If you call `trigger.sh` directly, handle exit codes explicitly:

```bash
bash scenarios/shell-spawn/trigger.sh JSON=1
code=$?
[ $code -le 11 ] && echo "scenario passed" || { echo "scenario failed with $code"; exit $code; }
```

### Parallel scenario runs

```yaml
strategy:
  matrix:
    scenario: [shell-spawn, sa-token-read, kubectl-exec, curl-egress, secret-enumeration]
steps:
  - run: make scenario-${{ matrix.scenario }} JSON=1
```

---

## Timeout and retry configuration

Timeouts are set per scenario via environment variables:

| Variable | Default | Effect |
|----------|---------|--------|
| `FALCO_VERIFY_TIMEOUT` | 20 | Seconds to wait for a Falco alert after trigger |
| Pod ready timeout | 60s | Set in `scenario.yaml` under `timeouts.ready_seconds` |

To extend the Falco verification window:

```bash
FALCO_VERIFY_TIMEOUT=60 make scenario-shell-spawn
```

There is no automatic retry at the scenario level. For flaky network-dependent scenarios (`curl-egress`), retry at the CI job level.

---

## Error handling

Every trigger script uses `set -euo pipefail`. Errors in any phase cause immediate exit with a structured exit code. The `failure_reason` field in JSON output provides a machine-readable cause.

Common failure reasons:

| Reason | Meaning |
|--------|---------|
| `exec_not_confirmed` | `kubectl exec` returned non-zero or no output |
| `network_request_failed` | Outbound request failed (NetworkPolicy or no internet) |
| `api_call_not_confirmed` | Kubernetes API call from container failed |
| `no_matching_alert_in_window` | Falco running but no alert matched in verification window |

---

## Custom scenarios

To add a scenario without modifying the repository, create the directory structure and run `trigger.sh` directly:

```bash
mkdir -p scenarios/my-scenario/manifests
# Create scenario.yaml, trigger.sh, cleanup.sh, README.md
bash scenarios/my-scenario/trigger.sh
```

See [scenario-authoring.md](scenario-authoring.md) for the full spec and 7-phase trigger pattern.

---

## Plugin / detection adapter support

Detection adapters live in `lib/detection/`. The current adapter is Falco (`lib/detection/falco.sh`). Each adapter must implement:

- `adapter_available()` — returns 0 if the backend is running
- `adapter_verify <trigger_time> <pattern> [namespace] [timeout]` — sets `DETECTION_RESULT=pass|fail|skip`
- `adapter_stream_alerts` — follows live output
- `adapter_raw_logs [lines]` — dumps recent raw output
- `adapter_list_rules` — best-effort rule name inference

To add a new adapter (e.g., Tetragon):

1. Create `lib/detection/tetragon.sh` implementing the interface above
2. Source it in your scenario's `trigger.sh` instead of (or alongside) `falco.sh`
3. Call `adapter_verify` after the trigger phase

No central registration is needed. Adapters are sourced directly by scenario scripts.
