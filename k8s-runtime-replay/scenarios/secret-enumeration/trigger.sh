#!/usr/bin/env bash
# scenarios/secret-enumeration/trigger.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"
source "${REPO_ROOT}/lib/checks.sh"
source "${REPO_ROOT}/lib/result.sh"
source "${REPO_ROOT}/lib/behavior.sh"
source "${REPO_ROOT}/lib/output.sh"
source "${REPO_ROOT}/lib/detection/falco.sh"

RESULT_SCENARIO="secret-enumeration"
RESULT_CONTEXT="$(kubectl config current-context 2>/dev/null || echo 'unknown')"

OBSERVED_BEHAVIOR="Kubernetes API call to list secrets from inside container"
EXPECTED_DETECTION="contact to Kubernetes API server from inside container"
SEARCH_PATTERN="K8S API"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"

if [[ "${FAST:-0}" != "1" ]] && [[ "${DRY_RUN:-0}" != "1" ]]; then
  kubectl delete pod secret-enum-target -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
fi

safety_banner "secret-enumeration"
require_kubectl
check_not_production
check_falco
result_set ENVIRONMENT_CHECK pass

adapter_available && result_set DETECTION_BACKEND Falco || result_set DETECTION_BACKEND "NOT INSTALLED"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  info "[dry-run] Would deploy: rbac.yaml, dummy-secret.yaml, workload.yaml"
  info "[dry-run] Would trigger: curl https://kubernetes.default.svc/api/v1/namespaces/$NAMESPACE/secrets"
  info "[dry-run] Would verify: API response from secret-enum-target"
  info "[dry-run] No cluster changes made."
  exit 0
fi

step "Deploying secret-enumeration workload"
kubectl apply -n "$NAMESPACE" -f "${REPO_ROOT}/scenarios/secret-enumeration/manifests/rbac.yaml"
kubectl apply -n "$NAMESPACE" -f "${REPO_ROOT}/scenarios/secret-enumeration/manifests/dummy-secret.yaml"
kubectl apply -n "$NAMESPACE" -f "${REPO_ROOT}/scenarios/secret-enumeration/manifests/workload.yaml"
result_set DEPLOY pass

step "Waiting for pod to be ready"
if wait_for_pod "scenario=secret-enumeration" "$NAMESPACE" 90s; then
  result_set READY pass
else
  warn "Pod did not become ready within timeout"
  result_set READY fail
fi

step "Calling Kubernetes API server from inside container"
TRIGGER_TIME="$(date +%s)"
verify_api_call "$NAMESPACE" secret-enum-target \
  "/api/v1/namespaces/${NAMESPACE}/secrets"
if [[ "$BEHAVIOR_VERIFIED" == "true" ]]; then
  result_set TRIGGER pass
  result_set BEHAVIOR pass
else
  warn "API call could not be verified — RBAC or network policy may be blocking"
  result_set TRIGGER pass
  result_set BEHAVIOR fail
  result_set OVERALL behavior_not_observed
  result_set FAILURE_REASON api_call_not_confirmed
  print_summary; print_detail "$OBSERVED_BEHAVIOR" "$EXPECTED_DETECTION"
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
