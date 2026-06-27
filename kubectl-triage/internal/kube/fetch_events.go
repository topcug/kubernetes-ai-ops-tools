package kube

import (
	"context"
	"fmt"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// FetchEvents returns recent events for a named object of the given kind.
func FetchEvents(ctx context.Context, cs kubernetes.Interface, kind, name, ns string) ([]types.EventSummary, error) {
	fieldSelector := fmt.Sprintf("involvedObject.kind=%s,involvedObject.name=%s", kind, name)
	list, err := cs.CoreV1().Events(ns).List(ctx, metav1.ListOptions{
		FieldSelector: fieldSelector,
	})
	if err != nil {
		return nil, fmt.Errorf("list events: %w", err)
	}

	var events []types.EventSummary
	for _, e := range list.Items {
		events = append(events, types.EventSummary{
			Type:    e.Type,
			Reason:  e.Reason,
			Message: e.Message,
			Count:   e.Count,
			Age:     humanAge(e.LastTimestamp.Time),
		})
	}
	return events, nil
}

func humanAge(t time.Time) string {
	if t.IsZero() {
		return "unknown"
	}
	d := time.Since(t)
	switch {
	case d < time.Minute:
		return fmt.Sprintf("%ds", int(d.Seconds()))
	case d < time.Hour:
		return fmt.Sprintf("%dm", int(d.Minutes()))
	case d < 24*time.Hour:
		return fmt.Sprintf("%dh", int(d.Hours()))
	default:
		return fmt.Sprintf("%dd", int(d.Hours()/24))
	}
}
