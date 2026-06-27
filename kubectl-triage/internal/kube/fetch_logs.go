package kube

import (
	"context"
	"fmt"
	"io"
	"strings"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/client-go/kubernetes"

	"github.com/topcug/kubectl-triage/pkg/types"
)

const logTailLines = 30

// FetchLogs retrieves the last N lines from the first non-init container of a pod.
func FetchLogs(ctx context.Context, cs kubernetes.Interface, podName, ns string, containers []corev1.Container) types.LogSnippet {
	if len(containers) == 0 {
		return types.LogSnippet{Error: "no containers found"}
	}
	target := containers[0]
	tail := int64(logTailLines)

	req := cs.CoreV1().Pods(ns).GetLogs(podName, &corev1.PodLogOptions{
		Container: target.Name,
		TailLines: &tail,
	})
	rc, err := req.Stream(ctx)
	if err != nil {
		return types.LogSnippet{Container: target.Name, Error: fmt.Sprintf("stream logs: %v", err)}
	}
	defer func() { _ = rc.Close() }()

	raw, err := io.ReadAll(rc)
	if err != nil {
		return types.LogSnippet{Container: target.Name, Error: fmt.Sprintf("read logs: %v", err)}
	}

	lines := strings.Split(strings.TrimRight(string(raw), "\n"), "\n")
	return types.LogSnippet{
		Container: target.Name,
		Lines:     lines,
		Truncated: len(lines) >= logTailLines,
	}
}
