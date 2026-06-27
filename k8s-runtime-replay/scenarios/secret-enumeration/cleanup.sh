#!/usr/bin/env bash
# scenarios/secret-enumeration/cleanup.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_ROOT}/lib/common.sh"

step "Cleaning up secret-enumeration scenario"
NAMESPACE="${REPLAY_NAMESPACE:-k8s-replay}"
kubectl delete pod secret-enum-target -n "$NAMESPACE" --ignore-not-found
kubectl delete rolebinding secret-enum-rolebinding -n "$NAMESPACE" --ignore-not-found
kubectl delete role secret-enum-role -n "$NAMESPACE" --ignore-not-found
kubectl delete serviceaccount secret-enum-sa -n "$NAMESPACE" --ignore-not-found
kubectl delete secret replay-dummy-secret -n "$NAMESPACE" --ignore-not-found
success "secret-enumeration cleaned up."
