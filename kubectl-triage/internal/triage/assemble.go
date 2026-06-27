package triage

import (
	"context"
	"fmt"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"

	"github.com/topcug/kubectl-triage/internal/kube"
	"github.com/topcug/kubectl-triage/pkg/types"
)

// AssemblePod collects all sections of a TriageReport for a pod.
func AssemblePod(ctx context.Context, cs kubernetes.Interface, name, ns string) (*types.TriageReport, error) {
	pod, workload, images, security, sa, err := kube.FetchPod(ctx, cs, name, ns)
	if err != nil {
		return nil, fmt.Errorf("fetch pod: %w", err)
	}

	ownership := kube.BuildOwnerChain(pod)

	events, err := kube.FetchEvents(ctx, cs, "Pod", name, ns)
	if err != nil {
		events = []types.EventSummary{{Reason: "error", Message: err.Error()}}
	}

	logs := kube.FetchLogs(ctx, cs, name, ns, pod.Spec.Containers)

	network, err := kube.FetchNetwork(ctx, cs, ns, pod.Labels)
	if err != nil {
		network = types.NetworkSummary{}
	}

	rbac, err := kube.FetchRBAC(ctx, cs, sa.Name, ns)
	if err != nil {
		rbac = types.RBACSummary{Warnings: []string{err.Error()}}
	}

	r := &types.TriageReport{
		Target:         types.TargetRef{Kind: "Pod", Name: name, Namespace: ns},
		Workload:       workload,
		Images:         images,
		Security:       security,
		ServiceAccount: sa,
		Ownership:      ownership,
		RecentEvents:   events,
		Logs:           logs,
		Network:        network,
		RBAC:           rbac,
		GeneratedAt:    time.Now().UTC(),
	}
	r.SummaryBullets = BuildSummaryBullets(r)
	r.Recommendations = Recommend(r)
	r.TriageReadout = BuildTriageReadout(r)
	return r, nil
}

// AssembleDeployment collects triage data for a deployment by resolving its pods.
func AssembleDeployment(ctx context.Context, cs kubernetes.Interface, name, ns string) (*types.TriageReport, error) {
	dep, err := cs.AppsV1().Deployments(ns).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return nil, fmt.Errorf("get deployment: %w", err)
	}

	var images []types.ImageSummary
	for _, c := range dep.Spec.Template.Spec.Containers {
		images = append(images, types.ImageSummary{
			Container: c.Name,
			Image:     c.Image,
			IsLatest:  isLatestTag(c.Image),
		})
	}

	ready := dep.Status.ReadyReplicas
	avail := dep.Status.AvailableReplicas
	desired := *dep.Spec.Replicas

	workload := types.WorkloadSummary{
		Name:      dep.Name,
		Namespace: dep.Namespace,
		Kind:      "Deployment",
		Labels:    dep.Labels,
		Replicas: &types.ReplicaStatus{
			Desired:   desired,
			Ready:     ready,
			Available: avail,
		},
	}

	fakeSec := types.SecuritySummary{}
	if psc := dep.Spec.Template.Spec.SecurityContext; psc != nil {
		fakeSec.RunAsNonRoot = psc.RunAsNonRoot
		fakeSec.RunAsUser = psc.RunAsUser
	}

	saName := dep.Spec.Template.Spec.ServiceAccountName
	automount := dep.Spec.Template.Spec.AutomountServiceAccountToken
	sa := types.ServiceAccountSummary{
		Name:                         saName,
		AutomountServiceAccountToken: automount,
	}
	_, err2 := cs.CoreV1().ServiceAccounts(ns).Get(ctx, saName, metav1.GetOptions{})
	sa.Exists = err2 == nil

	events, _ := kube.FetchEvents(ctx, cs, "Deployment", name, ns)
	network, _ := kube.FetchNetwork(ctx, cs, ns, dep.Spec.Template.Labels)
	rbac, _ := kube.FetchRBAC(ctx, cs, saName, ns)
	ownership := kube.BuildOwnerChain(dep)

	r := &types.TriageReport{
		Target:         types.TargetRef{Kind: "Deployment", Name: name, Namespace: ns},
		Workload:       workload,
		Images:         images,
		Security:       fakeSec,
		ServiceAccount: sa,
		Ownership:      ownership,
		RecentEvents:   events,
		Network:        network,
		RBAC:           rbac,
		GeneratedAt:    time.Now().UTC(),
	}
	r.SummaryBullets = BuildSummaryBullets(r)
	r.Recommendations = Recommend(r)
	r.TriageReadout = BuildTriageReadout(r)
	return r, nil
}

// AssembleJob collects triage data for a job.
func AssembleJob(ctx context.Context, cs kubernetes.Interface, name, ns string) (*types.TriageReport, error) {
	job, err := cs.BatchV1().Jobs(ns).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return nil, fmt.Errorf("get job: %w", err)
	}

	var images []types.ImageSummary
	for _, c := range job.Spec.Template.Spec.Containers {
		images = append(images, types.ImageSummary{
			Container: c.Name,
			Image:     c.Image,
			IsLatest:  isLatestTag(c.Image),
		})
	}

	conditions := []string{}
	for _, c := range job.Status.Conditions {
		conditions = append(conditions, fmt.Sprintf("%s=%s", c.Type, c.Status))
	}

	workload := types.WorkloadSummary{
		Name:       job.Name,
		Namespace:  job.Namespace,
		Kind:       "Job",
		Labels:     job.Labels,
		Conditions: conditions,
	}

	saName := job.Spec.Template.Spec.ServiceAccountName
	sa := types.ServiceAccountSummary{Name: saName}
	_, err2 := cs.CoreV1().ServiceAccounts(ns).Get(ctx, saName, metav1.GetOptions{})
	sa.Exists = err2 == nil

	events, _ := kube.FetchEvents(ctx, cs, "Job", name, ns)
	network, _ := kube.FetchNetwork(ctx, cs, ns, job.Spec.Template.Labels)
	rbac, _ := kube.FetchRBAC(ctx, cs, saName, ns)

	r := &types.TriageReport{
		Target:         types.TargetRef{Kind: "Job", Name: name, Namespace: ns},
		Workload:       workload,
		Images:         images,
		ServiceAccount: sa,
		RecentEvents:   events,
		Network:        network,
		RBAC:           rbac,
		GeneratedAt:    time.Now().UTC(),
	}
	r.SummaryBullets = BuildSummaryBullets(r)
	r.Recommendations = Recommend(r)
	r.TriageReadout = BuildTriageReadout(r)
	return r, nil
}

func isLatestTag(image string) bool {
	for i := len(image) - 1; i >= 0; i-- {
		if image[i] == ':' {
			return image[i+1:] == "latest"
		}
	}
	return true // no tag
}
