package triage

import (
	"fmt"
	"strings"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// Recommend produces action-oriented "suggested next checks" — not compliance verdicts.
func Recommend(r *types.TriageReport) []string {
	var recs []string

	// Restart / crash
	if r.Workload.IsRestarting {
		recs = append(recs, "inspect container command and entrypoint — pod is restarting")
	}
	for _, e := range r.RecentEvents {
		if strings.Contains(e.Reason, "CrashLoopBackOff") || strings.Contains(e.Message, "CrashLoopBackOff") {
			recs = append(recs, fmt.Sprintf("check logs for crash cause — CrashLoopBackOff detected (%dx)", e.Count))
			break
		}
	}
	for _, e := range r.RecentEvents {
		if strings.Contains(e.Reason, "OOMKilled") || strings.Contains(e.Message, "OOMKilled") {
			recs = append(recs, fmt.Sprintf("review memory limits — OOMKilled detected (%dx)", e.Count))
			break
		}
	}

	// Service account
	if r.ServiceAccount.AutomountServiceAccountToken == nil || *r.ServiceAccount.AutomountServiceAccountToken {
		recs = append(recs, "confirm whether the workload actually needs Kubernetes API access — automount token is enabled")
	}
	if r.ServiceAccount.IsDefault {
		recs = append(recs, "consider using a dedicated service account instead of the default one")
	}

	// Security
	nonRootSet := false
	for _, c := range r.Security.Containers {
		if c.RunAsNonRoot != nil && *c.RunAsNonRoot {
			nonRootSet = true
		}
	}
	if r.Security.RunAsNonRoot != nil && *r.Security.RunAsNonRoot {
		nonRootSet = true
	}
	if !nonRootSet {
		recs = append(recs, "review pod securityContext — runAsNonRoot is not set")
	}
	for _, c := range r.Security.Containers {
		if c.Privileged {
			recs = append(recs, fmt.Sprintf("investigate why container %q needs privileged mode — full host access risk", c.Name))
		}
	}
	for _, c := range r.Security.Containers {
		if c.ReadOnlyRootFS == nil || !*c.ReadOnlyRootFS {
			recs = append(recs, "set readOnlyRootFilesystem to reduce writable attack surface")
			break
		}
	}

	// Images
	for _, img := range r.Images {
		if img.IsLatest {
			recs = append(recs, fmt.Sprintf("pin image %q to a fixed version — :latest may change unexpectedly", img.Image))
			break
		}
	}

	// Network
	if !r.Network.HasNetworkPolicy {
		recs = append(recs, "add a NetworkPolicy — ingress/egress are currently unrestricted")
	}

	// RBAC
	if r.RBAC.IsOverbroad {
		recs = append(recs, "review ClusterRole bindings — service account has broad permissions")
	}
	if r.RBAC.CanGetSecrets {
		recs = append(recs, "verify Secret access is intentional — service account can read Secrets")
	}

	// Remaining warning events
	for _, e := range r.RecentEvents {
		if e.Type == "Warning" && strings.Contains(e.Reason, "Failed") {
			recs = append(recs, fmt.Sprintf("investigate %s event: %s", e.Reason, truncate(e.Message, 70)))
			break
		}
	}

	if len(recs) == 0 {
		recs = append(recs, "no immediate concerns — continue with deeper investigation if needed")
	}
	return recs
}

// BuildSummaryBullets returns the short risk bullets shown at the top of the report.
func BuildSummaryBullets(r *types.TriageReport) []string {
	var bullets []string

	if !r.Workload.IsReady {
		bullets = append(bullets, "pod is not ready")
	}
	if r.Workload.IsRestarting {
		bullets = append(bullets, "restart loop indicators present")
	}
	for _, e := range r.RecentEvents {
		if strings.Contains(e.Message, "CrashLoopBackOff") || strings.Contains(e.Reason, "CrashLoopBackOff") {
			bullets = append(bullets, "CrashLoopBackOff events present")
			break
		}
	}
	for _, img := range r.Images {
		if img.IsLatest {
			bullets = append(bullets, fmt.Sprintf("image uses :latest (%s)", img.Image))
			break
		}
	}
	if r.ServiceAccount.AutomountServiceAccountToken == nil || *r.ServiceAccount.AutomountServiceAccountToken {
		bullets = append(bullets, "service account token is auto-mounted")
	}
	if r.ServiceAccount.IsDefault {
		bullets = append(bullets, "uses default service account")
	}
	if !r.Network.HasNetworkPolicy {
		bullets = append(bullets, "no NetworkPolicy selects this workload")
	}
	if r.RBAC.IsOverbroad {
		bullets = append(bullets, "service account has broad RBAC permissions")
	}
	nonRootSet := false
	for _, c := range r.Security.Containers {
		if c.RunAsNonRoot != nil && *c.RunAsNonRoot {
			nonRootSet = true
		}
	}
	if r.Security.RunAsNonRoot != nil && *r.Security.RunAsNonRoot {
		nonRootSet = true
	}
	if !nonRootSet {
		bullets = append(bullets, "runAsNonRoot is not set")
	}

	if len(bullets) == 0 {
		bullets = append(bullets, "no obvious risk signals detected")
	}
	return bullets
}

// BuildTriageReadout returns a single-sentence situational summary.
func BuildTriageReadout(r *types.TriageReport) string {
	var parts []string

	if r.Workload.IsRestarting {
		parts = append(parts, "restart-looping pod")
	} else if !r.Workload.IsReady {
		parts = append(parts, "pod not yet ready")
	} else {
		parts = append(parts, "running pod")
	}

	hasWeakSec := false
	for _, c := range r.Security.Containers {
		if c.RunAsNonRoot == nil || c.ReadOnlyRootFS == nil {
			hasWeakSec = true
			break
		}
	}
	if hasWeakSec {
		parts = append(parts, "weak security defaults")
	}
	if !r.Network.HasNetworkPolicy {
		parts = append(parts, "unrestricted network scope")
	}
	if r.RBAC.IsOverbroad {
		parts = append(parts, "overprivileged service account")
	}

	if len(parts) == 1 {
		return fmt.Sprintf("This looks like a %s with no obvious risk signals.", parts[0])
	}
	return fmt.Sprintf("This looks like a %s with %s.", parts[0], strings.Join(parts[1:], " and "))
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
