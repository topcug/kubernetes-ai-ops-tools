#!/usr/bin/env bash
# lib/common.sh — shared utilities for all k8s-runtime-replay scenarios

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[info]${RESET}  $*"; }
success() { echo -e "${GREEN}[ok]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*"; }
error()   { echo -e "${RED}[error]${RESET} $*" >&2; }
step()    { echo -e "\n${BOLD}▸ $*${RESET}"; }

# ── Safety banner ─────────────────────────────────────────────────
safety_banner() {
  local scenario="${1:-unknown}"
  echo -e ""
  # Inner visible width = 52. "  Scenario : " = 13 chars, leaving 39 for value + padding.
  local slen=${#scenario}
  local pad=$(( 41 - slen ))
  [[ $pad -lt 0 ]] && pad=0
  local spaces
  spaces="$(printf '%*s' "$pad" '')"
  echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${RESET}"
  echo -e "${YELLOW}║  k8s-runtime-replay — safety notice                 ║${RESET}"
  echo -e "${YELLOW}╠══════════════════════════════════════════════════════╣${RESET}"
  echo -e "${YELLOW}║  Scenario : ${scenario}${spaces}║${RESET}"
  echo -e "${YELLOW}║  Purpose  : detection demo / rule validation         ║${RESET}"
  echo -e "${YELLOW}║  Run on   : test clusters only — never production    ║${RESET}"
  echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${RESET}"
  echo -e ""
}

# ── Prerequisite checks ───────────────────────────────────────────
require_cmd() {
  for cmd in "$@"; do
    if ! command -v "$cmd" &>/dev/null; then
      error "Required command not found: $cmd"
      exit 1
    fi
  done
}

require_kubectl() {
  require_cmd kubectl
  if ! kubectl cluster-info &>/dev/null; then
    error "kubectl cannot reach a cluster. Check your KUBECONFIG."
    exit 1
  fi
}

# ── Namespace helpers ─────────────────────────────────────────────
REPLAY_NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"

ensure_namespace() {
  local ns="${1:-$REPLAY_NAMESPACE}"
  if ! kubectl get namespace "$ns" &>/dev/null; then
    info "Creating namespace: $ns"
    kubectl create namespace "$ns"
  else
    info "Namespace already exists: $ns"
  fi
}

delete_namespace() {
  local ns="${1:-$REPLAY_NAMESPACE}"
  if kubectl get namespace "$ns" &>/dev/null; then
    info "Deleting namespace: $ns"
    kubectl delete namespace "$ns" --ignore-not-found
  fi
}

# ── Apply / delete manifests ──────────────────────────────────────
apply_manifests() {
  local dir="$1"
  local ns="${2:-$REPLAY_NAMESPACE}"
  step "Applying manifests from $dir"
  kubectl apply -n "$ns" -f "$dir"
}

delete_manifests() {
  local dir="$1"
  local ns="${2:-$REPLAY_NAMESPACE}"
  step "Deleting manifests from $dir"
  kubectl delete -n "$ns" -f "$dir" --ignore-not-found
}

# ── Wait helpers ──────────────────────────────────────────────────
wait_for_pod() {
  local label="$1"
  local ns="${2:-$REPLAY_NAMESPACE}"
  local timeout="${3:-60s}"
  info "Waiting for pod with label $label in $ns (timeout: $timeout)..."
  if ! kubectl wait pod \
    --for=condition=Ready \
    --selector="$label" \
    -n "$ns" \
    --timeout="$timeout" 2>&1; then
    error "Pod readiness timeout after $timeout — label: $label, namespace: $ns"
    info "Pod status:"
    kubectl get pods -n "$ns" -l "$label" 2>/dev/null || true
    info "Recent events:"
    kubectl get events -n "$ns" --sort-by='.lastTimestamp' 2>/dev/null | tail -10 || true
    return 1
  fi
}

# ── Retry helper ──────────────────────────────────────────────────
# Retries a command up to N times with a fixed delay between attempts.
# Usage: retry <max_attempts> <delay_seconds> <command...>
retry() {
  local max="${1:-3}"
  local delay="${2:-5}"
  shift 2
  local attempt=1
  while [[ $attempt -le $max ]]; do
    if "$@"; then
      return 0
    fi
    warn "Attempt $attempt/$max failed — retrying in ${delay}s..."
    sleep "$delay"
    attempt=$(( attempt + 1 ))
  done
  error "All $max attempts failed for: $*"
  return 1
}

# ── Timeout wrapper ───────────────────────────────────────────────
# Runs a command with a wall-clock timeout (uses bash built-in SECONDS).
# Usage: with_timeout <seconds> <command...>
with_timeout() {
  local timeout_secs="$1"
  shift
  local start="$SECONDS"
  "$@" &
  local pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    if [[ $(( SECONDS - start )) -ge $timeout_secs ]]; then
      kill "$pid" 2>/dev/null || true
      error "Command timed out after ${timeout_secs}s: $*"
      return 1
    fi
    sleep 1
  done
  wait "$pid"
}

# ── Dry-run mode ──────────────────────────────────────────────────
# When DRY_RUN=1 is set, kubectl and trigger commands are printed but not run.
DRY_RUN="${DRY_RUN:-0}"

kube_apply() {
  if [[ "$DRY_RUN" == "1" ]]; then
    info "[dry-run] kubectl apply $*"
  else
    kubectl apply "$@"
  fi
}

kube_exec() {
  if [[ "$DRY_RUN" == "1" ]]; then
    info "[dry-run] kubectl exec $*"
  else
    kubectl exec "$@"
  fi
}

kube_delete() {
  if [[ "$DRY_RUN" == "1" ]]; then
    info "[dry-run] kubectl delete $*"
  else
    kubectl delete "$@"
  fi
}

# ── Scenario root detection ───────────────────────────────────────
# When sourced, SCENARIO_DIR is the directory of the calling script
SCENARIO_DIR="$(cd "$(dirname "${BASH_SOURCE[1]:-$0}")" && pwd)"
export MANIFESTS_DIR="${SCENARIO_DIR}/manifests"
