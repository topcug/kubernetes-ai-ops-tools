package render

import (
	"fmt"
	"io"
	"strings"

	"github.com/fatih/color"

	"github.com/topcug/kubectl-triage/internal/triage"
	"github.com/topcug/kubectl-triage/pkg/types"
)

var (
	bold    = color.New(color.Bold)
	warn    = color.New(color.FgYellow)
	ok      = color.New(color.FgGreen)
	faint   = color.New(color.FgHiBlack)
	heading = color.New(color.FgCyan, color.Bold)
)

// Table renders a compact, first-response triage screen.
// Pass verbose=true to show full event list and owner chain.
// Pass quiet=true to output summary bullets and triage readout only.
func Table(w io.Writer, r *types.TriageReport, verbose, quiet bool) {
	fmt.Fprintln(w)
	heading.Fprintf(w, "══ kubectl-triage: %s/%s [%s] ══\n", r.Target.Namespace, r.Target.Name, r.Target.Kind)
	faint.Fprintf(w, "   %s\n", r.GeneratedAt.Format("2006-01-02 15:04:05 UTC"))

	// ── Summary ───────────────────────────────────────────────────
	section(w, "Summary")
	bullets := r.SummaryBullets
	if len(bullets) == 0 {
		bullets = triage.BuildSummaryBullets(r)
	}
	for _, b := range bullets {
		warn.Fprintf(w, "  - %s\n", b)
	}

	if quiet {
		fmt.Fprintln(w)
		bold.Fprintln(w, "▸ Triage Readout")
		fmt.Fprintf(w, "  %s\n\n", r.TriageReadout)
		return
	}

	// ── Workload ──────────────────────────────────────────────────
	section(w, "Workload")
	kv(w, "Name", r.Workload.Name)
	kv(w, "Namespace", r.Workload.Namespace)
	kv(w, "Kind", r.Workload.Kind)
	if r.Workload.Phase != "" {
		kv(w, "Phase", r.Workload.Phase)
	}
	if r.Workload.NodeName != "" {
		kv(w, "Node", r.Workload.NodeName)
	}
	readyVal := ok.Sprint("yes")
	if !r.Workload.IsReady {
		readyVal = warn.Sprint("no")
	}
	kv(w, "Ready", readyVal)
	restartVal := faint.Sprint("no")
	if r.Workload.IsRestarting {
		restartVal = warn.Sprint("yes")
	}
	kv(w, "Restarting", restartVal)
	if r.Workload.Replicas != nil {
		rep := r.Workload.Replicas
		kv(w, "Replicas", fmt.Sprintf("desired=%d  ready=%d  available=%d", rep.Desired, rep.Ready, rep.Available))
	}

	// ── Image ─────────────────────────────────────────────────────
	section(w, "Image")
	for _, img := range r.Images {
		flags := ""
		if img.IsLatest {
			flags = "  " + warn.Sprint("⚠ :latest")
		}
		if img.IsInit {
			flags += faint.Sprint("  [init]")
		}
		fmt.Fprintf(w, "  %s → %s%s\n", img.Container, img.Image, flags)
	}

	// ── Security ──────────────────────────────────────────────────
	section(w, "Security")
	for i, c := range r.Security.Containers {
		if i > 0 {
			fmt.Fprintln(w)
		}
		if len(r.Security.Containers) > 1 {
			faint.Fprintf(w, "  [%s]\n", c.Name)
		}
		kv(w, "  privileged", formatBool(c.Privileged, true))
		kv(w, "  runAsNonRoot", formatBoolPtr(c.RunAsNonRoot, false))
		kv(w, "  readOnlyRootFilesystem", formatBoolPtr(c.ReadOnlyRootFS, false))
		kv(w, "  allowPrivilegeEscalation", formatBoolPtr(c.AllowPrivilegeEsc, true))
		if len(c.Capabilities) > 0 {
			kv(w, "  added capabilities", warn.Sprint(strings.Join(c.Capabilities, ", ")))
		} else {
			kv(w, "  added capabilities", faint.Sprint("none"))
		}
	}
	if len(r.Security.Containers) == 0 {
		faint.Fprintln(w, "  (no container security context found)")
	}

	// ── Service Account ───────────────────────────────────────────
	section(w, "Service Account")
	saName := r.ServiceAccount.Name
	if r.ServiceAccount.IsDefault {
		saName += "  " + warn.Sprint("(default SA)")
	}
	kv(w, "  name", saName)
	amVal := warn.Sprint("enabled")
	if r.ServiceAccount.AutomountServiceAccountToken != nil && !*r.ServiceAccount.AutomountServiceAccountToken {
		amVal = ok.Sprint("disabled")
	}
	kv(w, "  automount token", amVal)

	// ── Owner Chain (verbose only) ────────────────────────────────
	if verbose && len(r.Ownership.Entries) > 0 {
		section(w, "Owner Chain")
		parts := make([]string, len(r.Ownership.Entries))
		for i, e := range r.Ownership.Entries {
			parts[i] = fmt.Sprintf("%s/%s", e.Kind, e.Name)
		}
		fmt.Fprintf(w, "  %s\n", strings.Join(parts, " → "))
	}

	// ── Key Events ───────────────────────────────────────────────
	section(w, "Key Events")
	events := topEvents(r.RecentEvents, verbose)
	if len(events) == 0 {
		faint.Fprintln(w, "  (no events)")
	} else {
		for _, e := range events {
			if e.Type == "Warning" {
				warn.Fprintf(w, "  ⚠ %s %s: %s\n", e.Type, e.Reason, truncate(e.Message, 90))
			} else {
				faint.Fprintf(w, "  · %s %s: %s\n", e.Type, e.Reason, truncate(e.Message, 90))
			}
		}
		if !verbose && len(r.RecentEvents) > 5 {
			faint.Fprintf(w, "  ... %d more (use --verbose to see all)\n", len(r.RecentEvents)-5)
		}
	}

	// ── Log Tail ──────────────────────────────────────────────────
	section(w, fmt.Sprintf("Log Tail [%s]", r.Logs.Container))
	if r.Logs.Error != "" {
		warn.Fprintf(w, "  %s\n", r.Logs.Error)
	} else if len(r.Logs.Lines) == 0 || (len(r.Logs.Lines) == 1 && r.Logs.Lines[0] == "") {
		if r.Workload.IsRestarting {
			faint.Fprintln(w, "  container is restarting too quickly to return a stable log tail")
		} else {
			faint.Fprintf(w, "  no recent logs returned for container %q\n", r.Logs.Container)
		}
	} else {
		for _, line := range r.Logs.Lines {
			faint.Fprintf(w, "  %s\n", line)
		}
		if r.Logs.Truncated {
			faint.Fprintln(w, "  ... (truncated — use kubectl logs for full output)")
		}
	}

	// ── Network ───────────────────────────────────────────────────
	section(w, "Network")
	if r.Network.HasNetworkPolicy {
		kv(w, "  NetworkPolicy", ok.Sprint("✓ present")+"  "+faint.Sprint("("+strings.Join(r.Network.Policies, ", ")+")"))
	} else {
		kv(w, "  NetworkPolicy", warn.Sprint("✗ none — unrestricted"))
		faint.Fprintln(w, "                             ingress/egress may be unrestricted depending on cluster defaults")
	}
	for _, svc := range r.Network.Services {
		kv(w, "  Service", svc.Name+"  "+faint.Sprint("ports: "+strings.Join(svc.Ports, ", ")))
	}

	// ── RBAC ──────────────────────────────────────────────────────
	section(w, "RBAC")
	if len(r.RBAC.Bindings) == 0 {
		faint.Fprintln(w, "  no direct RoleBinding/ClusterRoleBinding match found for this service account in current lookup")
	} else {
		for _, b := range r.RBAC.Bindings {
			scope := ""
			if b.IsCluster {
				scope = "  " + warn.Sprint("[cluster-wide]")
			}
			fmt.Fprintf(w, "  %s → %s (%s)%s\n", b.BindingName, b.RoleName, b.RoleKind, scope)
		}
	}
	for _, w2 := range r.RBAC.Warnings {
		warn.Fprintf(w, "  ⚠ %s\n", w2)
	}

	// ── Suggested Next Checks ─────────────────────────────────────
	section(w, "Suggested Next Checks")
	for _, rec := range r.Recommendations {
		fmt.Fprintf(w, "  - %s\n", rec)
	}

	// ── Triage Readout ────────────────────────────────────────────
	fmt.Fprintln(w)
	bold.Fprintln(w, "▸ Triage Readout")
	fmt.Fprintf(w, "  %s\n\n", r.TriageReadout)
}

// ── helpers ──────────────────────────────────────────────────────

func section(w io.Writer, title string) {
	bold.Fprintf(w, "\n▸ %s\n", title)
}

func kv(w io.Writer, key, val string) {
	fmt.Fprintf(w, "  %-28s %s\n", key, val)
}

func formatBool(b bool, warnIfTrue bool) string {
	if b && warnIfTrue {
		return warn.Sprint("yes")
	}
	if b {
		return "yes"
	}
	return "no"
}

func formatBoolPtr(b *bool, warnIfTrue bool) string {
	if b == nil {
		return warn.Sprint("not set")
	}
	return formatBool(*b, warnIfTrue)
}

func topEvents(events []types.EventSummary, verbose bool) []types.EventSummary {
	if verbose || len(events) <= 5 {
		return events
	}
	var warnings, others []types.EventSummary
	for _, e := range events {
		if e.Type == "Warning" {
			warnings = append(warnings, e)
		} else {
			others = append(others, e)
		}
	}
	combined := append(warnings, others...)
	if len(combined) > 5 {
		return combined[:5]
	}
	return combined
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}
