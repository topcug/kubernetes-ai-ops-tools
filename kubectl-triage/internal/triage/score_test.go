package triage_test

import (
	"strings"
	"testing"

	"github.com/topcug/kubectl-triage/internal/triage"
	"github.com/topcug/kubectl-triage/pkg/types"
)

func boolPtr(b bool) *bool { return &b }

func TestRecommend_AutomountWarning(t *testing.T) {
	r := &types.TriageReport{
		ServiceAccount: types.ServiceAccountSummary{
			AutomountServiceAccountToken: boolPtr(true),
		},
	}
	recs := triage.Recommend(r)
	requireContains(t, recs, "automount token is enabled")
}

func TestRecommend_PrivilegedWarning(t *testing.T) {
	r := &types.TriageReport{
		Security: types.SecuritySummary{
			Containers: []types.ContainerSec{
				{Name: "app", Privileged: true},
			},
		},
		ServiceAccount: types.ServiceAccountSummary{
			AutomountServiceAccountToken: boolPtr(false),
		},
		Network: types.NetworkSummary{HasNetworkPolicy: true},
	}
	recs := triage.Recommend(r)
	requireContains(t, recs, "privileged")
}

func TestRecommend_LatestImageWarning(t *testing.T) {
	r := &types.TriageReport{
		Images: []types.ImageSummary{
			{Container: "app", Image: "nginx:latest", IsLatest: true},
		},
		ServiceAccount: types.ServiceAccountSummary{
			AutomountServiceAccountToken: boolPtr(false),
		},
		Network: types.NetworkSummary{HasNetworkPolicy: true},
	}
	recs := triage.Recommend(r)
	requireContains(t, recs, ":latest")
}

func TestRecommend_NoNetworkPolicy(t *testing.T) {
	r := &types.TriageReport{
		ServiceAccount: types.ServiceAccountSummary{
			AutomountServiceAccountToken: boolPtr(false),
		},
		Network: types.NetworkSummary{HasNetworkPolicy: false},
	}
	recs := triage.Recommend(r)
	requireContains(t, recs, "NetworkPolicy")
}

func TestRecommend_CrashLoopBackOff(t *testing.T) {
	r := &types.TriageReport{
		ServiceAccount: types.ServiceAccountSummary{
			AutomountServiceAccountToken: boolPtr(false),
		},
		Network: types.NetworkSummary{HasNetworkPolicy: true},
		RecentEvents: []types.EventSummary{
			{Type: "Warning", Reason: "BackOff", Message: "Back-off restarting failed container (CrashLoopBackOff)", Count: 5},
		},
	}
	recs := triage.Recommend(r)
	requireContains(t, recs, "CrashLoopBackOff")
}

func TestRecommend_AllClear(t *testing.T) {
	nonRoot := true
	readonly := true
	noPrivEsc := false
	r := &types.TriageReport{
		ServiceAccount: types.ServiceAccountSummary{
			AutomountServiceAccountToken: boolPtr(false),
		},
		Network: types.NetworkSummary{HasNetworkPolicy: true},
		Security: types.SecuritySummary{
			RunAsNonRoot: &nonRoot,
			Containers: []types.ContainerSec{
				{
					Name:              "app",
					RunAsNonRoot:      &nonRoot,
					ReadOnlyRootFS:    &readonly,
					AllowPrivilegeEsc: &noPrivEsc,
				},
			},
		},
		Images: []types.ImageSummary{
			{Container: "app", Image: "nginx:1.25", IsLatest: false},
		},
	}
	recs := triage.Recommend(r)
	requireContains(t, recs, "no immediate concerns")
}

func requireContains(t *testing.T, recs []string, fragment string) {
	t.Helper()
	for _, r := range recs {
		if strings.Contains(r, fragment) {
			return
		}
	}
	t.Errorf("expected a recommendation containing %q, got: %v", fragment, recs)
}
