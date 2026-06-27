package kube

import (
	"fmt"
	"time"

	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/clientcmd"
)

const DefaultTimeout = 8 * time.Second

// NewClient builds a Kubernetes client from the default kubeconfig chain.
// It respects KUBECONFIG env var and ~/.kube/config.
func NewClient(kubeconfig, context string) (kubernetes.Interface, error) {
	loadingRules := clientcmd.NewDefaultClientConfigLoadingRules()
	if kubeconfig != "" {
		loadingRules.ExplicitPath = kubeconfig
	}

	overrides := &clientcmd.ConfigOverrides{}
	if context != "" {
		overrides.CurrentContext = context
	}

	cfg, err := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(
		loadingRules, overrides,
	).ClientConfig()
	if err != nil {
		return nil, fmt.Errorf("build kubeconfig: %w", err)
	}

	cfg.Timeout = DefaultTimeout

	return kubernetes.NewForConfig(cfg)
}
