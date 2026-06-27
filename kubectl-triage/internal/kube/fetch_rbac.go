package kube

import (
	"context"
	"fmt"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// FetchRBAC inspects RoleBindings and ClusterRoleBindings for the given service account.
func FetchRBAC(ctx context.Context, cs kubernetes.Interface, saName, ns string) (types.RBACSummary, error) {
	summary := types.RBACSummary{}

	// RoleBindings
	rbs, err := cs.RbacV1().RoleBindings(ns).List(ctx, metav1.ListOptions{})
	if err != nil {
		summary.Warnings = append(summary.Warnings, fmt.Sprintf("cannot list rolebindings: %v", err))
	} else {
		for _, rb := range rbs.Items {
			for _, subj := range rb.Subjects {
				if subj.Kind == "ServiceAccount" && subj.Name == saName {
					summary.Bindings = append(summary.Bindings, types.RoleBindingEntry{
						BindingName: rb.Name,
						RoleName:    rb.RoleRef.Name,
						RoleKind:    rb.RoleRef.Kind,
						IsCluster:   false,
					})
				}
			}
		}
	}

	// ClusterRoleBindings
	crbs, err := cs.RbacV1().ClusterRoleBindings().List(ctx, metav1.ListOptions{})
	if err != nil {
		summary.Warnings = append(summary.Warnings, fmt.Sprintf("cannot list clusterrolebindings: %v", err))
	} else {
		for _, crb := range crbs.Items {
			for _, subj := range crb.Subjects {
				if subj.Kind == "ServiceAccount" && subj.Name == saName && subj.Namespace == ns {
					summary.Bindings = append(summary.Bindings, types.RoleBindingEntry{
						BindingName: crb.Name,
						RoleName:    crb.RoleRef.Name,
						RoleKind:    crb.RoleRef.Kind,
						IsCluster:   true,
					})
					// Inspect the referenced ClusterRole for overbroad rules
					cr, err := cs.RbacV1().ClusterRoles().Get(ctx, crb.RoleRef.Name, metav1.GetOptions{})
					if err == nil {
						for _, rule := range cr.Rules {
							if verbsContain(rule.Verbs, "*") || resourcesContain(rule.Resources, "secrets") {
								summary.IsOverbroad = true
								summary.CanGetSecrets = true
								summary.Warnings = append(summary.Warnings,
									fmt.Sprintf("ClusterRole %q grants broad access: verbs=%v resources=%v",
										cr.Name, rule.Verbs, rule.Resources))
							}
						}
					}
				}
			}
		}
	}

	return summary, nil
}

func verbsContain(verbs []string, target string) bool {
	for _, v := range verbs {
		if v == target {
			return true
		}
	}
	return false
}

func resourcesContain(resources []string, target string) bool {
	for _, r := range resources {
		if r == target || r == "*" {
			return true
		}
	}
	return false
}
