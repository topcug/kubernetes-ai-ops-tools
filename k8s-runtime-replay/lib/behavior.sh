#!/usr/bin/env bash
# lib/behavior.sh — behavior verification helpers for k8s-runtime-replay
#
# The primary success condition of a scenario is reproducing and verifying
# the intended runtime behavior — independent of any detection backend.

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

export BEHAVIOR_VERIFIED="false"

# ── verify_exec_succeeded ─────────────────────────────────────────
# Confirms that a kubectl exec command exited 0 and produced output.
# Usage: verify_exec_succeeded <namespace> <pod> <command...>
# Sets BEHAVIOR_VERIFIED=true on success.
verify_exec_succeeded() {
  local ns="$1"
  local pod="$2"
  shift 2
  local output
  if output=$(kubectl exec -n "$ns" "$pod" -- "$@" 2>&1); then
    if [[ -n "$output" ]]; then
      BEHAVIOR_VERIFIED="true"
      return 0
    fi
  fi
  BEHAVIOR_VERIFIED="false"
  return 1
}

# ── verify_file_read ──────────────────────────────────────────────
# Confirms that a file path is readable inside a container.
# Usage: verify_file_read <namespace> <pod> <file_path>
verify_file_read() {
  local ns="$1"
  local pod="$2"
  local path="$3"
  if kubectl exec -n "$ns" "$pod" -- sh -c "test -r \"$path\" && echo ok" 2>/dev/null | grep -q ok; then
    BEHAVIOR_VERIFIED="true"
    return 0
  fi
  BEHAVIOR_VERIFIED="false"
  return 1
}

# ── verify_network_request ────────────────────────────────────────
# Confirms that an outbound network request from a container completed.
# Usage: verify_network_request <namespace> <pod> <url>
verify_network_request() {
  local ns="$1"
  local pod="$2"
  local url="$3"
  if kubectl exec -n "$ns" "$pod" -- \
       curl -sS --max-time 10 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null \
       | grep -qE "^[2345][0-9]{2}$"; then
    BEHAVIOR_VERIFIED="true"
    return 0
  fi
  BEHAVIOR_VERIFIED="false"
  return 1
}

# ── verify_api_call ───────────────────────────────────────────────
# Confirms that an API server call was made from inside a container.
# Usage: verify_api_call <namespace> <pod> <api_path>
verify_api_call() {
  local ns="$1"
  local pod="$2"
  local api_path="${3:-/api/v1}"
  local result
  result=$(kubectl exec -n "$ns" "$pod" -- sh -c \
    "TOKEN=\$(cat /var/run/secrets/kubernetes.io/serviceaccount/token 2>/dev/null); \
     CA=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt; \
     curl -sS --max-time 10 --cacert \$CA \
       --header \"Authorization: Bearer \$TOKEN\" \
       https://kubernetes.default.svc${api_path} 2>/dev/null | head -1" 2>/dev/null || true)
  if [[ -n "$result" ]]; then
    BEHAVIOR_VERIFIED="true"
    return 0
  fi
  BEHAVIOR_VERIFIED="false"
  return 1
}
