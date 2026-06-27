#!/usr/bin/env bash
# scenarios/sa-token-read/trigger.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"
source "${REPO_ROOT}/lib/checks.sh"
source "${REPO_ROOT}/lib/result.sh"
source "${REPO_ROOT}/lib/behavior.sh"
source "${REPO_ROOT}/lib/output.sh"
source "${REPO_ROOT}/lib/detection/falco.sh"

RESULT_SCENARIO="sa-token-read"
RESULT_CONTEXT="$(kubectl config current-context 2>/dev/null || echo 'unknown')"

OBSERVED_BEHAVIOR="service account token file read inside container"
EXPECTED_DETECTION="sensitive file read inside container"
SEARCH_PATTERN="sensitive file"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"
TOKEN_PATH="/var/run/secrets/kubernetes.io/serviceaccount/token"

if [[ "${FAST:-0}" != "1" ]] && [[ "${DRY_RUN:-0}" != "1" ]]; then
  kubectl delete pod sa-token-read-target -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
fi

safety_banner "sa-token-read"
require_kubectl
check_not_production
check_falco
result_set ENVIRONMENT_CHECK pass

adapter_available && result_set DETECTION_BACKEND Falco || result_set DETECTION_BACKEND "NOT INSTALLED"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  info "[dry-run] Would deploy: serviceaccount.yaml, workload.yaml"
  info "[dry-run] Would trigger: kubectl exec sa-token-read-target -- sh -c 'cat /var/run/secrets/...'"
  info "[dry-run] Would verify: token file readable at $TOKEN_PATH"
  info "[dry-run] No cluster changes made."
  exit 0
fi

step "Deploying sa-token-read workload"
kubectl apply -n "$NAMESPACE" -f "${REPO_ROOT}/scenarios/sa-token-read/manifests/serviceaccount.yaml"
kubectl apply -n "$NAMESPACE" -f "${REPO_ROOT}/scenarios/sa-token-read/manifests/workload.yaml"
result_set DEPLOY pass

step "Waiting for pod to be ready"
if wait_for_pod "scenario=sa-token-read" "$NAMESPACE" 60s; then
  result_set READY pass
else
  warn "Pod did not become ready within timeout"
  result_set READY fail
fi

step "Reading service account token from within the container"
TRIGGER_TIME="$(date +%s)"
kubectl exec -n "$NAMESPACE" sa-token-read-target -- sh -c \
  'TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token); \
   echo "Token length: ${#TOKEN} chars"; \
   echo "Namespace:    $(cat /var/run/secrets/kubernetes.io/serviceaccount/namespace)"; \
   echo "CA present:   $(test -f /var/run/secrets/kubernetes.io/serviceaccount/ca.crt && echo yes || echo no)"'
result_set TRIGGER pass

step "Verifying behavior"
verify_file_read "$NAMESPACE" sa-token-read-target "$TOKEN_PATH"
if [[ "$BEHAVIOR_VERIFIED" == "true" ]]; then
  result_set BEHAVIOR pass
else
  warn "Behavior verification could not confirm token file was readable"
  result_set BEHAVIOR fail
  result_set OVERALL behavior_not_observed
  result_set FAILURE_REASON token_file_not_readable
  print_summary
  print_detail "$OBSERVED_BEHAVIOR" "$EXPECTED_DETECTION"
  result_exit_code; exit $?
fi

step "Verifying detection"
adapter_verify "$TRIGGER_TIME" "$SEARCH_PATTERN" "$NAMESPACE"

case "$DETECTION_RESULT" in
  pass) result_set DETECTION pass; result_set OVERALL scenario_passed_detection_verified ;;
  skip) result_set DETECTION skip; result_set OVERALL scenario_passed_detection_skipped ;;
  *)    result_set DETECTION fail; result_set OVERALL scenario_passed_detection_not_verified
        result_set FAILURE_REASON no_matching_alert_in_window ;;
esac

if [[ "${JSON:-0}" == "1" ]]; then result_to_json
else print_summary; print_detail "$OBSERVED_BEHAVIOR" "$EXPECTED_DETECTION"; fi

result_exit_code || exit $?
