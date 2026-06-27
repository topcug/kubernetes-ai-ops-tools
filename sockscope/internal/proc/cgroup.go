package proc

// This file is intentionally thin. Cgroup parsing in v1 lives next to
// the process reader in process.go, because we only need one thing
// from the cgroup path: the container ID. If cgroup handling grows
// in v1.1 (namespaces, unified vs legacy hierarchies, pod metadata),
// it should move here.
