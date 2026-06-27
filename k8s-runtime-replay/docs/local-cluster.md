# Local cluster setup

The fastest way to run k8s-runtime-replay locally is with [kind](https://kind.sigs.k8s.io/) (Kubernetes IN Docker).

## Install kind

```bash
# macOS
brew install kind

# Linux
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64
chmod +x ./kind
mv ./kind /usr/local/bin/kind
```

## Create a cluster

```bash
make setup-kind
```

This creates a single-node kind cluster named `k8s-replay`.

Or manually:

```bash
kind create cluster --name k8s-replay
kubectl cluster-info --context kind-k8s-replay
```

## Verify

```bash
kubectl get nodes
kubectl get namespaces
```

## Tear down

```bash
kind delete cluster --name k8s-replay
```

## Notes

- kind runs Kubernetes inside Docker containers — no VMs needed.
- All scenarios are tested against kind v0.22+ with Kubernetes 1.29+.
- For Falco to work with kind, see [docs/falco-setup.md](falco-setup.md).
