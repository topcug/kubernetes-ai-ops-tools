#!/usr/bin/env bash
# scenarios/curl-egress/cleanup.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"

step "Cleaning up curl-egress scenario"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"
kubectl delete pod curl-egress-target -n "$NAMESPACE" --ignore-not-found
success "curl-egress cleaned up."
