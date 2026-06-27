package fixtures

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"time"
)

// CrashLoopEvents returns a typical CrashLoopBackOff event list.
func CrashLoopEvents(podName, ns string) *corev1.EventList {
	now := metav1.NewTime(time.Now())
	return &corev1.EventList{
		Items: []corev1.Event{
			{
				ObjectMeta: metav1.ObjectMeta{Name: "backoff-1", Namespace: ns},
				InvolvedObject: corev1.ObjectReference{
					Kind: "Pod", Name: podName, Namespace: ns,
				},
				Type:          "Warning",
				Reason:        "BackOff",
				Message:       "Back-off restarting failed container (CrashLoopBackOff)",
				Count:         14,
				LastTimestamp: now,
			},
			{
				ObjectMeta: metav1.ObjectMeta{Name: "policy-1", Namespace: ns},
				InvolvedObject: corev1.ObjectReference{
					Kind: "Pod", Name: podName, Namespace: ns,
				},
				Type:          "Warning",
				Reason:        "PolicyViolation",
				Message:       "require-run-as-non-root",
				Count:         1,
				LastTimestamp: now,
			},
		},
	}
}

// OOMKilledEvents returns an OOMKilled event list.
func OOMKilledEvents(podName, ns string) *corev1.EventList {
	now := metav1.NewTime(time.Now())
	return &corev1.EventList{
		Items: []corev1.Event{
			{
				ObjectMeta: metav1.ObjectMeta{Name: "oom-1", Namespace: ns},
				InvolvedObject: corev1.ObjectReference{
					Kind: "Pod", Name: podName, Namespace: ns,
				},
				Type:          "Warning",
				Reason:        "OOMKilled",
				Message:       "Container app exceeded memory limit",
				Count:         3,
				LastTimestamp: now,
			},
		},
	}
}

// NoEvents returns an empty event list.
func NoEvents(ns string) *corev1.EventList {
	return &corev1.EventList{}
}
