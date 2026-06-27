package render_test

import (
	"bytes"
	"strings"
	"testing"
	"time"

	"github.com/topcug/kubectl-triage/internal/render"
	"github.com/topcug/kubectl-triage/pkg/types"
)

func sampleReport() *types.TriageReport {
	nonRoot := true
	automount := true
	return &types.TriageReport{
		Target:      types.TargetRef{Kind: "Pod", Name: "suspicious-pod", Namespace: "payments"},
		GeneratedAt: time.Date(2024, 1, 15, 10, 0, 0, 0, time.UTC),
		Workload: types.WorkloadSummary{
			Name:      "suspicious-pod",
			Namespace: "payments",
			Kind:      "Pod",
			Phase:     "Running",
			NodeName:  "node-1",
		},
		Images: []types.ImageSummary{
			{Container: "app", Image: "nginx:latest", IsLatest: true},
		},
		Security: types.SecuritySummary{
			RunAsNonRoot: &nonRoot,
			Containers: []types.ContainerSec{
				{Name: "app", RunAsNonRoot: &nonRoot},
			},
		},
		ServiceAccount: types.ServiceAccountSummary{
			Name:                         "default",
			Exists:                       true,
			AutomountServiceAccountToken: &automount,
		},
		Ownership: types.OwnerChain{
			Entries: []types.OwnerEntry{{Kind: "ReplicaSet", Name: "suspicious-rs", UID: "abc-123"}},
		},
		RecentEvents: []types.EventSummary{
			{Type: "Warning", Reason: "BackOff", Message: "CrashLoopBackOff", Count: 3, Age: "5m"},
		},
		Logs: types.LogSnippet{
			Container: "app",
			Lines:     []string{"error: connection refused", "panic: nil pointer"},
		},
		Network: types.NetworkSummary{HasNetworkPolicy: false},
		RBAC:    types.RBACSummary{},
		Recommendations: []string{
			"⚠ automountServiceAccountToken is enabled",
			"⚠ container \"app\" uses :latest image",
		},
	}
}

func TestTableRender_ContainsKeyFields(t *testing.T) {
	var buf bytes.Buffer
	render.Table(&buf, sampleReport(), false, false)
	out := buf.String()

	checks := []string{
		"suspicious-pod",
		"payments",
		"nginx:latest",
		"CrashLoopBackOff",
		"automountServiceAccountToken",
	}
	for _, check := range checks {
		if !strings.Contains(out, check) {
			t.Errorf("table output missing expected string %q", check)
		}
	}
}

func TestMarkdownRender_ContainsKeyFields(t *testing.T) {
	var buf bytes.Buffer
	render.Markdown(&buf, sampleReport())
	out := buf.String()

	checks := []string{
		"# kubectl-triage",
		"suspicious-pod",
		"## Images",
		"## What to Check Next",
		"nginx:latest",
	}
	for _, check := range checks {
		if !strings.Contains(out, check) {
			t.Errorf("markdown output missing expected string %q", check)
		}
	}
}
