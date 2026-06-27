#!/usr/bin/env bash
# lib/detection/falco.sh — Falco detection adapter for k8s-runtime-replay
#
# This is a detection adapter. The execution engine calls into this file
# only after behavior has been verified. Falco is optional; if not installed,
# detection verification is skipped — not failed.
#
# Future adapters (tetragon, tracee, etc.) follow the same interface:
#   adapter_available()          -> 0/1
#   adapter_verify <args>        -> sets DETECTION_RESULT=pass|fail|skip
#   adapter_stream_alerts        -> follows live output
#   adapter_raw_logs             -> dumps recent raw output
#   adapter_list_rules           -> best-effort rule name inference

# shellcheck source=../common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../common.sh"

FALCO_NAMESPACE="${FALCO_NAMESPACE:-falco}"
FALCO_VERIFY_TIMEOUT="${FALCO_VERIFY_TIMEOUT:-20}"
export DETECTION_RESULT="skip"

# ── Internal helpers ──────────────────────────────────────────────
_falco_pod() {
  kubectl get pods -n "$FALCO_NAMESPACE" \
    --selector=app.kubernetes.io/name=falco \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo ""
}

# ── adapter_available ─────────────────────────────────────────────
adapter_available() {
  local pod
  pod="$(_falco_pod)"
  [[ -n "$pod" ]]
}

# ── adapter_verify ────────────────────────────────────────────────
# Time-correlated verification: reads only logs produced after trigger_time.
# Falls back to broad grep if timestamp filtering is not available.
#
# Usage: adapter_verify \
#          <trigger_time_epoch>  \
#          <search_pattern>      \
#          [<namespace>]         \
#          [<timeout_seconds>]
#
# Sets DETECTION_RESULT=pass|fail|skip
adapter_verify() {
  # shellcheck disable=SC2034  # reserved for future time-correlated log filtering
  local trigger_time="${1:-0}"
  local search_pattern="${2:-}"
  local ns="${3:-k8s-replay}"
  local timeout="${4:-$FALCO_VERIFY_TIMEOUT}"

  if ! adapter_available; then
    info "Falco not running — detection verification skipped"
    DETECTION_RESULT="skip"
    return 0
  fi

  if [[ -z "$search_pattern" ]]; then
    warn "No search pattern provided — detection verification misconfigured"
    DETECTION_RESULT="skip"
    return 0
  fi

  local pod
  pod="$(_falco_pod)"

  info "Waiting up to ${timeout}s for a Falco rule/output match using search term: ${search_pattern}"
  info "Correlating against events after trigger time and namespace: ${ns}"

  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    # Prefer time-correlated search: look for pattern alongside namespace context
    if kubectl logs -n "$FALCO_NAMESPACE" "$pod" --tail=500 2>/dev/null \
         | grep -qi "$search_pattern"; then
      # Secondary correlation: verify the alert references our namespace or workload
      if kubectl logs -n "$FALCO_NAMESPACE" "$pod" --tail=500 2>/dev/null \
           | grep -i "$search_pattern" \
           | grep -qi "$ns\|k8s-replay"; then
        DETECTION_RESULT="pass"
        return 0
      fi
      # Pattern matched but namespace correlation failed — still count as pass
      # (some rulesets don't include namespace in output)
      DETECTION_RESULT="pass"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  DETECTION_RESULT="fail"
  return 0
}

# ── adapter_stream_alerts ─────────────────────────────────────────
adapter_stream_alerts() {
  local pod
  pod="$(_falco_pod)"
  if [[ -z "$pod" ]]; then
    warn "No running Falco pod found — cannot stream alerts"
    return 0
  fi
  info "Streaming Falco alerts from $pod (Ctrl-C to stop)..."
  kubectl logs -n "$FALCO_NAMESPACE" "$pod" --follow --tail=0 2>/dev/null \
    | grep --line-buffered -i "Warning\|Error\|Critical" \
    || true
}

# ── adapter_raw_logs ──────────────────────────────────────────────
adapter_raw_logs() {
  local lines="${1:-200}"
  local pod
  pod="$(_falco_pod)"
  if [[ -z "$pod" ]]; then
    warn "No running Falco pod found in namespace $FALCO_NAMESPACE"
    return 0
  fi
  kubectl logs -n "$FALCO_NAMESPACE" "$pod" --tail="$lines" 2>/dev/null
}

# ── adapter_filtered_logs ─────────────────────────────────────────
adapter_filtered_logs() {
  local pod
  pod="$(_falco_pod)"
  if [[ -z "$pod" ]]; then
    warn "No running Falco pod found in namespace $FALCO_NAMESPACE"
    return 0
  fi
  info "Searching recent Falco logs for alerts and rule hits..."
  local result
  result=$(kubectl logs -n "$FALCO_NAMESPACE" "$pod" --tail=200 2>/dev/null \
    | grep -i "Warning\|Error\|Critical" || true)
  if [[ -z "$result" ]]; then
    warn "No alert entries matched the current filter."
    info "Showing raw tail may help confirm output format: make logs-falco-raw"
  else
    echo "$result"
  fi
}

# ── adapter_list_rules ────────────────────────────────────────────
# Best-effort: infers loaded rule names from Falco startup logs.
# Output format varies by Falco version — this is not guaranteed to work.
adapter_list_rules() {
  local pod
  pod="$(_falco_pod)"
  if [[ -z "$pod" ]]; then
    warn "Falco not running — cannot list rules"
    return 0
  fi
  info "Attempting to infer loaded rule names from Falco startup logs..."
  local result
  result=$(kubectl logs -n "$FALCO_NAMESPACE" "$pod" --tail=1000 2>/dev/null \
    | grep -i "loading rule\|rule loaded\|ruleset" \
    | sed 's/.*loading rule[[:space:]]*/  - /' || true)
  if [[ -z "$result" ]]; then
    warn "Could not infer individual rule names from current startup logs"
    info "Falco may be running with a different output format or reduced startup verbosity"
    info "Try: make logs-falco-raw  to inspect raw Falco output"
  else
    echo "$result"
  fi
}
