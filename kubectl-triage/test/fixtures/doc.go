// Package fixtures provides fake Kubernetes objects for use in unit tests.
//
// Available helpers:
//   - CrashLoopingPod — pod stuck in CrashLoopBackOff
//   - HealthyPod      — pod Running/Ready with good security defaults
//   - PendingPod      — pod stuck in Pending / Unschedulable
//   - CrashLoopEvents — Warning events for a CrashLooping pod
//   - OOMKilledEvents — OOMKilled warning events
//   - NoEvents        — empty event list
package fixtures
