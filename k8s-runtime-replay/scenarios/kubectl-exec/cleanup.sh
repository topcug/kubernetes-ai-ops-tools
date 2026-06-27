#!/usr/bin/env bash
# scenarios/kubectl-exec/cleanup.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"

step "Cleaning up kubectl-exec scenario"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"
kubectl delete pod kubectl-exec-target -n "$NAMESPACE" --ignore-not-found
success "kubectl-exec cleaned up."
