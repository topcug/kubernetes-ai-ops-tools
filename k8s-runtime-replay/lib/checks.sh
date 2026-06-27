#!/usr/bin/env bash
# lib/checks.sh — pre-flight checks for k8s-runtime-replay

set -euo pipefail
# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# ── check_not_production ──────────────────────────────────────────
# Refuses to run if the current cluster context looks like production.
check_not_production() {
  local ctx
  ctx="$(kubectl config current-context 2>/dev/null || echo '')"

  local prod_patterns=("prod" "production" "prd" "live" "staging-prod")
  for pattern in "${prod_patterns[@]}"; do
    if echo "$ctx" | grep -qi "$pattern"; then
      error "Current context looks like a production cluster: $ctx"
      error "k8s-runtime-replay is designed for test clusters only."
      error "Override this check by setting REPLAY_ALLOW_ANY_CLUSTER=true (not recommended)."
      if [[ "${REPLAY_ALLOW_ANY_CLUSTER:-false}" != "true" ]]; then
        exit 1
      fi
      warn "REPLAY_ALLOW_ANY_CLUSTER=true — proceeding anyway."
    fi
  done

  info "Current context: $ctx (looks safe)"
}

# ── check_falco ───────────────────────────────────────────────────
# Reports whether Falco is available. Never fails — Falco is optional.
check_falco() {
  if kubectl get pods -n falco --selector=app.kubernetes.io/name=falco \
       --field-selector=status.phase=Running -o name 2>/dev/null | grep -q pod; then
    success "Falco is running — expected rule hits will be visible in Falco logs"
    return 0
  else
    warn "Falco not detected — scenario will still run, but no runtime alerts will fire"
    warn "Run 'make setup-falco' to install Falco  |  See docs/falco-setup.md"
    return 0
  fi
}

# ── check_kind ────────────────────────────────────────────────────
# Reports whether kind is available. Never fails — kind is optional.
check_kind() {
  if command -v kind &>/dev/null; then
    success "kind is available"
  else
    warn "kind not found — install from https://kind.sigs.k8s.io for local cluster setup"
  fi
}

# ── check_namespace ───────────────────────────────────────────────
# Warns if the replay namespace does not exist yet (it will be created on deploy).
check_namespace() {
  local ns="${1:-${REPLAY_NAMESPACE:-k8s-replay}}"
  if kubectl get namespace "$ns" &>/dev/null; then
    info "Namespace exists: $ns"
  else
    info "Namespace $ns will be created during deploy"
  fi
}

# ── check_api_server ─────────────────────────────────────────────
# Verifies the API server is reachable and prints the server URL.
check_api_server() {
  local url
  url="$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null || echo '')"
  if kubectl cluster-info &>/dev/null; then
    info "API server reachable: ${url:-<unknown>}"
  else
    error "API server unreachable — check KUBECONFIG and cluster status"
    if [[ -n "${url:-}" ]]; then
      error "Configured server: $url"
    fi
    exit 1
  fi
}
