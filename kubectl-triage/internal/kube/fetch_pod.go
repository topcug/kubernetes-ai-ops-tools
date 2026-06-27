package kube

import (
	"context"
	"fmt"
	"strings"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// FetchPod retrieves a pod and populates workload, image, and security summaries.
func FetchPod(ctx context.Context, cs kubernetes.Interface, name, ns string) (
	*corev1.Pod,
	types.WorkloadSummary,
	[]types.ImageSummary,
	types.SecuritySummary,
	types.ServiceAccountSummary,
	error,
) {
	pod, err := cs.CoreV1().Pods(ns).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return nil, types.WorkloadSummary{}, nil, types.SecuritySummary{}, types.ServiceAccountSummary{}, fmt.Errorf("get pod: %w", err)
	}

	workload := types.WorkloadSummary{
		Name:      pod.Name,
		Namespace: pod.Namespace,
		Kind:      "Pod",
		Phase:     string(pod.Status.Phase),
		NodeName:  pod.Spec.NodeName,
		Labels:    pod.Labels,
	}
	for _, c := range pod.Status.Conditions {
		workload.Conditions = append(workload.Conditions, fmt.Sprintf("%s=%s", c.Type, c.Status))
		if c.Type == "Ready" {
			workload.IsReady = c.Status == "True"
		}
	}
	// Detect restart loop from container statuses
	for _, cs := range pod.Status.ContainerStatuses {
		if cs.RestartCount > 2 || (cs.State.Waiting != nil &&
			(cs.State.Waiting.Reason == "CrashLoopBackOff" || cs.State.Waiting.Reason == "Error")) {
			workload.IsRestarting = true
		}
	}

	var images []types.ImageSummary
	for _, c := range pod.Spec.InitContainers {
		images = append(images, types.ImageSummary{
			Container: c.Name,
			Image:     c.Image,
			IsLatest:  isLatestTag(c.Image),
			IsInit:    true,
		})
	}
	for _, c := range pod.Spec.Containers {
		images = append(images, types.ImageSummary{
			Container: c.Name,
			Image:     c.Image,
			IsLatest:  isLatestTag(c.Image),
		})
	}

	security := buildPodSecurity(pod)

	automount := pod.Spec.AutomountServiceAccountToken
	saName := pod.Spec.ServiceAccountName
	sa := types.ServiceAccountSummary{
		Name:                         saName,
		AutomountServiceAccountToken: automount,
		IsDefault:                    saName == "default" || saName == "",
	}
	_, err2 := cs.CoreV1().ServiceAccounts(ns).Get(ctx, sa.Name, metav1.GetOptions{})
	sa.Exists = err2 == nil

	return pod, workload, images, security, sa, nil
}

func isLatestTag(image string) bool {
	if !strings.Contains(image, ":") {
		return true // no tag implies latest
	}
	parts := strings.SplitN(image, ":", 2)
	return parts[1] == "latest"
}

func buildPodSecurity(pod *corev1.Pod) types.SecuritySummary {
	sec := types.SecuritySummary{}
	if psc := pod.Spec.SecurityContext; psc != nil {
		sec.RunAsNonRoot = psc.RunAsNonRoot
		sec.RunAsUser = psc.RunAsUser
		if psc.SeccompProfile != nil {
			sec.SeccompProfile = string(psc.SeccompProfile.Type)
		}
	}

	for _, c := range pod.Spec.Containers {
		cs := types.ContainerSec{Name: c.Name}
		if csc := c.SecurityContext; csc != nil {
			if csc.Privileged != nil {
				cs.Privileged = *csc.Privileged
				if cs.Privileged {
					sec.Privileged = csc.Privileged
				}
			}
			cs.RunAsNonRoot = csc.RunAsNonRoot
			cs.ReadOnlyRootFS = csc.ReadOnlyRootFilesystem
			cs.AllowPrivilegeEsc = csc.AllowPrivilegeEscalation
			if csc.Capabilities != nil {
				for _, cap := range csc.Capabilities.Add {
					cs.Capabilities = append(cs.Capabilities, string(cap))
				}
			}
		}
		sec.Containers = append(sec.Containers, cs)
	}
	return sec
}
