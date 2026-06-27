package kube

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// BuildOwnerChain walks the ownerReferences of a metav1.Object to build the chain.
func BuildOwnerChain(obj metav1.Object) types.OwnerChain {
	chain := types.OwnerChain{}
	for _, ref := range obj.GetOwnerReferences() {
		chain.Entries = append(chain.Entries, types.OwnerEntry{
			Kind: ref.Kind,
			Name: ref.Name,
			UID:  string(ref.UID),
		})
	}
	return chain
}
