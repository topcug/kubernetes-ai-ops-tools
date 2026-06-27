#!/usr/bin/env bash
# lib/result.sh — result model, exit codes, and JSON output for k8s-runtime-replay

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# ── Exit codes ────────────────────────────────────────────────────
# 0   scenario passed, detection verified
# 10  scenario passed, detection skipped (no backend)
# 11  scenario passed, detection not verified
# 20  environment/preflight failed
# 21  deploy failed
# 22  readiness timeout
# 23  trigger failed
# 24  behavior not observed
# 30  detection backend unavailable
# 31  detection verification misconfigured

export EXIT_SCENARIO_DETECTION_VERIFIED=0
export EXIT_SCENARIO_DETECTION_SKIPPED=10
export EXIT_SCENARIO_DETECTION_NOT_VERIFIED=11
export EXIT_PREFLIGHT_FAILED=20
export EXIT_DEPLOY_FAILED=21
export EXIT_READY_TIMEOUT=22
export EXIT_TRIGGER_FAILED=23
export EXIT_BEHAVIOR_NOT_OBSERVED=24
export EXIT_BACKEND_UNAVAILABLE=30
export EXIT_DETECTION_MISCONFIGURED=31

# ── Result state (set by execution engine) ────────────────────────
RESULT_SCENARIO=""
RESULT_CONTEXT=""
RESULT_ENVIRONMENT_CHECK="pending"
RESULT_DEPLOY="pending"
RESULT_READY="pending"
RESULT_TRIGGER="pending"
RESULT_BEHAVIOR="pending"
RESULT_DETECTION_BACKEND="none"
RESULT_DETECTION="pending"
RESULT_OVERALL="pending"
RESULT_FAILURE_REASON=""

# ── result_set ────────────────────────────────────────────────────
# Sets a single result field.
result_set() {
  local field="$1"
  local value="$2"
  eval "RESULT_${field}=\"${value}\""
}

# ── result_to_json ────────────────────────────────────────────────
result_to_json() {
  cat <<EOF
{
  "scenario": "$RESULT_SCENARIO",
  "context": "$RESULT_CONTEXT",
  "environment_check": "$RESULT_ENVIRONMENT_CHECK",
  "deploy": "$RESULT_DEPLOY",
  "ready": "$RESULT_READY",
  "trigger": "$RESULT_TRIGGER",
  "behavior_verification": "$RESULT_BEHAVIOR",
  "detection_backend": "$RESULT_DETECTION_BACKEND",
  "detection_verification": "$RESULT_DETECTION",
  "overall": "$RESULT_OVERALL",
  "failure_reason": "$RESULT_FAILURE_REASON"
}
EOF
}

# ── result_exit_code ──────────────────────────────────────────────
result_exit_code() {
  case "$RESULT_OVERALL" in
    scenario_passed_detection_verified)     return $EXIT_SCENARIO_DETECTION_VERIFIED ;;
    scenario_passed_detection_skipped)      return $EXIT_SCENARIO_DETECTION_SKIPPED ;;
    scenario_passed_detection_not_verified) return $EXIT_SCENARIO_DETECTION_NOT_VERIFIED ;;
    preflight_failed)                       return $EXIT_PREFLIGHT_FAILED ;;
    deploy_failed)                          return $EXIT_DEPLOY_FAILED ;;
    ready_timeout)                          return $EXIT_READY_TIMEOUT ;;
    trigger_failed)                         return $EXIT_TRIGGER_FAILED ;;
    behavior_not_observed)                  return $EXIT_BEHAVIOR_NOT_OBSERVED ;;
    *)                                      return $EXIT_SCENARIO_DETECTION_NOT_VERIFIED ;;
  esac
}

# ── result_fail_and_exit ──────────────────────────────────────────
# Convenience: set overall + failure_reason, print summary, then exit.
# Usage: result_fail_and_exit <overall_state> <failure_reason>
result_fail_and_exit() {
  local overall="$1"
  local reason="$2"
  result_set OVERALL "$overall"
  result_set FAILURE_REASON "$reason"
  if [[ "${JSON:-0}" == "1" ]]; then
    result_to_json
  else
    # print_summary and print_detail sourced from output.sh in each trigger script
    if declare -f print_summary &>/dev/null; then
      print_summary
    fi
  fi
  result_exit_code || exit $?
}
