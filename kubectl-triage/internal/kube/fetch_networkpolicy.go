package kube

import (
	"context"
	"fmt"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/client-go/kubernetes"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// FetchNetwork checks NetworkPolicies and Services matching the given pod labels.
func FetchNetwork(ctx context.Context, cs kubernetes.Interface, ns string, podLabels map[string]string) (types.NetworkSummary, error) {
	summary := types.NetworkSummary{}

	// NetworkPolicies
	policies, err := cs.NetworkingV1().NetworkPolicies(ns).List(ctx, metav1.ListOptions{})
	if err != nil {
		return summary, fmt.Errorf("list networkpolicies: %w", err)
	}
	for _, np := range policies.Items {
		sel, err := metav1.LabelSelectorAsSelector(&np.Spec.PodSelector)
		if err != nil {
			continue
		}
		if sel.Matches(labels.Set(podLabels)) {
			summary.HasNetworkPolicy = true
			summary.Policies = append(summary.Policies, np.Name)
		}
	}

	// Services
	services, err := cs.CoreV1().Services(ns).List(ctx, metav1.ListOptions{})
	if err != nil {
		return summary, fmt.Errorf("list services: %w", err)
	}
	for _, svc := range services.Items {
		if svc.Spec.Selector == nil {
			continue
		}
		sel := labels.Set(svc.Spec.Selector)
		if sel.AsSelector().Matches(labels.Set(podLabels)) {
			var ports []string
			for _, p := range svc.Spec.Ports {
				ports = append(ports, fmt.Sprintf("%d/%s", p.Port, p.Protocol))
			}
			summary.Services = append(summary.Services, types.ServiceBinding{
				Name:  svc.Name,
				Ports: ports,
			})
		}
	}

	return summary, nil
}
