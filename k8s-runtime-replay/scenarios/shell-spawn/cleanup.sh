#!/usr/bin/env bash
# scenarios/shell-spawn/cleanup.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"

step "Cleaning up shell-spawn scenario"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"
kubectl delete pod shell-spawn-target -n "$NAMESPACE" --ignore-not-found
success "shell-spawn cleaned up."
