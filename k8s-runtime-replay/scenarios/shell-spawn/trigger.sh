#!/usr/bin/env bash
# scenarios/shell-spawn/trigger.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"
source "${REPO_ROOT}/lib/checks.sh"
source "${REPO_ROOT}/lib/result.sh"
source "${REPO_ROOT}/lib/behavior.sh"
source "${REPO_ROOT}/lib/output.sh"
source "${REPO_ROOT}/lib/detection/falco.sh"

# ── Phase 0: init result ──────────────────────────────────────────
RESULT_SCENARIO="shell-spawn"
RESULT_CONTEXT="$(kubectl config current-context 2>/dev/null || echo 'unknown')"

OBSERVED_BEHAVIOR="shell executed inside workload container"
EXPECTED_DETECTION="shell execution inside a container"
SEARCH_PATTERN="shell"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"

# ── Clean state by default; reuse with FAST=1; skip in DRY_RUN ──
if [[ "${FAST:-0}" != "1" ]] && [[ "${DRY_RUN:-0}" != "1" ]]; then
  kubectl delete pod shell-spawn-target -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
fi

# ── Phase 1: preflight ────────────────────────────────────────────
safety_banner "shell-spawn"
require_kubectl
check_not_production
check_falco
result_set ENVIRONMENT_CHECK pass

if adapter_available; then
  result_set DETECTION_BACKEND Falco
else
  result_set DETECTION_BACKEND "NOT INSTALLED"
fi

# ── Phase 2: deploy ───────────────────────────────────────────────
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  info "[dry-run] Would deploy: namespace.yaml, workload.yaml"
  info "[dry-run] Would trigger: kubectl exec shell-spawn-target -- /bin/sh -c '...'"
  info "[dry-run] Would verify: exec output from shell-spawn-target"
  info "[dry-run] No cluster changes made."
  exit 0
fi

step "Deploying shell-spawn workload"
kubectl apply -f "${REPO_ROOT}/scenarios/shell-spawn/manifests/namespace.yaml"
kubectl apply -n "$NAMESPACE" -f "${REPO_ROOT}/scenarios/shell-spawn/manifests/workload.yaml"
result_set DEPLOY pass

# ── Phase 3: wait ready ───────────────────────────────────────────
step "Waiting for pod to be ready"
if wait_for_pod "scenario=shell-spawn" "$NAMESPACE" 60s; then
  result_set READY pass
else
  warn "Pod did not become ready within timeout — trigger may still proceed"
  result_set READY fail
fi

# ── Phase 4: trigger ──────────────────────────────────────────────
step "Triggering shell execution inside target container"
TRIGGER_TIME="$(date +%s)"
kubectl exec -n "$NAMESPACE" shell-spawn-target -- /bin/sh -c \
  'echo "shell-spawn triggered at $(date)"; id; ps 2>/dev/null || true'
result_set TRIGGER pass

# ── Phase 5: behavior verification ───────────────────────────────
step "Verifying behavior"
verify_exec_succeeded "$NAMESPACE" shell-spawn-target \
  /bin/sh -c 'echo ok'
if [[ "$BEHAVIOR_VERIFIED" == "true" ]]; then
  result_set BEHAVIOR pass
else
  warn "Behavior verification did not confirm expected artifact"
  result_set BEHAVIOR fail
  result_set OVERALL behavior_not_observed
  result_set FAILURE_REASON exec_not_confirmed
  print_summary
  print_detail "$OBSERVED_BEHAVIOR" "$EXPECTED_DETECTION"
  result_exit_code; exit $?
fi

# ── Phase 6: detection verification (optional) ────────────────────
step "Verifying detection"
adapter_verify "$TRIGGER_TIME" "$SEARCH_PATTERN" "$NAMESPACE"

case "$DETECTION_RESULT" in
  pass)
    result_set DETECTION pass
    result_set OVERALL scenario_passed_detection_verified
    ;;
  skip)
    result_set DETECTION skip
    result_set OVERALL scenario_passed_detection_skipped
    ;;
  *)
    result_set DETECTION fail
    result_set OVERALL scenario_passed_detection_not_verified
    result_set FAILURE_REASON no_matching_alert_in_window
    ;;
esac

# ── Phase 7: output ───────────────────────────────────────────────
if [[ "${JSON:-0}" == "1" ]]; then
  result_to_json
else
  print_summary
  print_detail "$OBSERVED_BEHAVIOR" "$EXPECTED_DETECTION"
fi

result_exit_code || exit $?
