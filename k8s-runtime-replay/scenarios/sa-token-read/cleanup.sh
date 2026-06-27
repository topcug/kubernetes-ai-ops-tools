#!/usr/bin/env bash
# scenarios/sa-token-read/cleanup.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"

step "Cleaning up sa-token-read scenario"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"
kubectl delete pod sa-token-read-target -n "$NAMESPACE" --ignore-not-found
kubectl delete serviceaccount replay-sa -n "$NAMESPACE" --ignore-not-found
success "sa-token-read cleaned up."
