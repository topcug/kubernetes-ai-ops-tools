package fixtures

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// CrashLoopingPod returns a pod that is CrashLoopBackOff on its primary container.
func CrashLoopingPod(name, ns string) *corev1.Pod {
	return &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: ns,
			Labels:    map[string]string{"app": name},
		},
		Spec: corev1.PodSpec{
			ServiceAccountName: "default",
			Containers: []corev1.Container{
				{
					Name:  "app",
					Image: "docker.io/myapp:latest",
				},
			},
		},
		Status: corev1.PodStatus{
			Phase: corev1.PodRunning,
			Conditions: []corev1.PodCondition{
				{Type: corev1.PodReady, Status: corev1.ConditionFalse},
			},
			ContainerStatuses: []corev1.ContainerStatus{
				{
					Name:         "app",
					RestartCount: 14,
					State: corev1.ContainerState{
						Waiting: &corev1.ContainerStateWaiting{
							Reason:  "CrashLoopBackOff",
							Message: "back-off 5m0s restarting failed container=app",
						},
					},
				},
			},
		},
	}
}

// HealthyPod returns a pod that is Running and Ready with good security defaults.
func HealthyPod(name, ns string) *corev1.Pod {
	nonRoot := true
	readOnly := true
	noPrivEsc := false
	return &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: ns,
			Labels:    map[string]string{"app": name},
		},
		Spec: corev1.PodSpec{
			ServiceAccountName:           "dedicated-sa",
			AutomountServiceAccountToken: boolPtr(false),
			Containers: []corev1.Container{
				{
					Name:  "app",
					Image: "docker.io/myapp:v1.2.3",
					SecurityContext: &corev1.SecurityContext{
						RunAsNonRoot:             &nonRoot,
						ReadOnlyRootFilesystem:   &readOnly,
						AllowPrivilegeEscalation: &noPrivEsc,
					},
				},
			},
		},
		Status: corev1.PodStatus{
			Phase: corev1.PodRunning,
			Conditions: []corev1.PodCondition{
				{Type: corev1.PodReady, Status: corev1.ConditionTrue},
			},
			ContainerStatuses: []corev1.ContainerStatus{
				{Name: "app", RestartCount: 0, Ready: true},
			},
		},
	}
}

// PendingPod returns a pod stuck in Pending phase.
func PendingPod(name, ns string) *corev1.Pod {
	return &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: ns,
			Labels:    map[string]string{"app": name},
		},
		Spec: corev1.PodSpec{
			ServiceAccountName: "default",
			Containers: []corev1.Container{
				{Name: "app", Image: "docker.io/myapp:v1.0.0"},
			},
		},
		Status: corev1.PodStatus{
			Phase: corev1.PodPending,
			Conditions: []corev1.PodCondition{
				{
					Type:    corev1.PodScheduled,
					Status:  corev1.ConditionFalse,
					Reason:  "Unschedulable",
					Message: "0/3 nodes are available: insufficient memory",
				},
			},
		},
	}
}

func boolPtr(b bool) *bool { return &b }
