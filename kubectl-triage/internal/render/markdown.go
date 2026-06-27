package render

import (
	"fmt"
	"io"
	"strings"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// Markdown renders the TriageReport in GitHub-flavoured markdown.
// Suitable for pasting into issues, incident docs, Slack, or Notion.
func Markdown(w io.Writer, r *types.TriageReport) {
	fmt.Fprintf(w, "# kubectl-triage: `%s/%s` [%s]\n\n", r.Target.Namespace, r.Target.Name, r.Target.Kind)
	fmt.Fprintf(w, "_Generated at %s_\n\n", r.GeneratedAt.Format("2006-01-02 15:04:05 UTC"))

	// Workload
	fmt.Fprintln(w, "## Workload")
	fmt.Fprintln(w, "| Field | Value |")
	fmt.Fprintln(w, "|-------|-------|")
	fmt.Fprintf(w, "| Name | `%s` |\n", r.Workload.Name)
	fmt.Fprintf(w, "| Namespace | `%s` |\n", r.Workload.Namespace)
	fmt.Fprintf(w, "| Kind | `%s` |\n", r.Workload.Kind)
	if r.Workload.Phase != "" {
		fmt.Fprintf(w, "| Phase | `%s` |\n", r.Workload.Phase)
	}
	if r.Workload.NodeName != "" {
		fmt.Fprintf(w, "| Node | `%s` |\n", r.Workload.NodeName)
	}
	if r.Workload.Replicas != nil {
		rep := r.Workload.Replicas
		fmt.Fprintf(w, "| Replicas | desired=%d ready=%d available=%d |\n", rep.Desired, rep.Ready, rep.Available)
	}
	fmt.Fprintln(w)

	// Images
	fmt.Fprintln(w, "## Images")
	fmt.Fprintln(w, "| Container | Image | Flags |")
	fmt.Fprintln(w, "|-----------|-------|-------|")
	for _, img := range r.Images {
		flags := ""
		if img.IsLatest {
			flags += "⚠ :latest"
		}
		if img.IsInit {
			flags += " [init]"
		}
		fmt.Fprintf(w, "| `%s` | `%s` | %s |\n", img.Container, img.Image, strings.TrimSpace(flags))
	}
	fmt.Fprintln(w)

	// Security
	fmt.Fprintln(w, "## Security Context")
	fmt.Fprintln(w, "| Container | Privileged | NonRoot | ReadOnlyFS | PrivEsc | Caps |")
	fmt.Fprintln(w, "|-----------|------------|---------|------------|---------|------|")
	for _, c := range r.Security.Containers {
		fmt.Fprintf(w, "| `%s` | %v | %s | %s | %s | %s |\n",
			c.Name,
			c.Privileged,
			fmtBoolPtr(c.RunAsNonRoot),
			fmtBoolPtr(c.ReadOnlyRootFS),
			fmtBoolPtr(c.AllowPrivilegeEsc),
			strings.Join(c.Capabilities, ","),
		)
	}
	fmt.Fprintln(w)

	// Service Account
	fmt.Fprintln(w, "## Service Account")
	amsa := "true (default)"
	if r.ServiceAccount.AutomountServiceAccountToken != nil {
		amsa = fmt.Sprintf("%v", *r.ServiceAccount.AutomountServiceAccountToken)
	}
	fmt.Fprintf(w, "- **Name**: `%s`\n", r.ServiceAccount.Name)
	fmt.Fprintf(w, "- **Exists**: %v\n", r.ServiceAccount.Exists)
	fmt.Fprintf(w, "- **AutomountToken**: %s\n\n", amsa)

	// Owner Chain
	if len(r.Ownership.Entries) > 0 {
		fmt.Fprintln(w, "## Owner Chain")
		for i, e := range r.Ownership.Entries {
			fmt.Fprintf(w, "%s`%s/%s`", strings.Repeat("→ ", i), e.Kind, e.Name)
		}
		fmt.Fprintln(w, "")
	}

	// Events
	fmt.Fprintln(w, "## Recent Events")
	if len(r.RecentEvents) == 0 {
		fmt.Fprintln(w, "_No events found._")
	} else {
		fmt.Fprintln(w, "| Type | Reason | Count | Age | Message |")
		fmt.Fprintln(w, "|------|--------|-------|-----|---------|")
		for _, e := range r.RecentEvents {
			fmt.Fprintf(w, "| %s | %s | %d | %s | %s |\n",
				e.Type, e.Reason, e.Count, e.Age,
				strings.ReplaceAll(truncate(e.Message, 100), "|", "\\|"))
		}
		fmt.Fprintln(w)
	}

	// Logs
	fmt.Fprintf(w, "## Log Tail (`%s`)\n\n", r.Logs.Container)
	if r.Logs.Error != "" {
		fmt.Fprintf(w, "> ⚠ %s\n\n", r.Logs.Error)
	} else {
		fmt.Fprintln(w, "```")
		for _, line := range r.Logs.Lines {
			fmt.Fprintln(w, line)
		}
		if r.Logs.Truncated {
			fmt.Fprintln(w, "... (truncated)")
		}
		fmt.Fprintln(w, "```")
	}

	// Network
	fmt.Fprintln(w, "## Network")
	npStatus := "✓ present"
	if !r.Network.HasNetworkPolicy {
		npStatus = "⚠ none — unrestricted"
	}
	fmt.Fprintf(w, "- **NetworkPolicy**: %s\n", npStatus)
	if len(r.Network.Policies) > 0 {
		fmt.Fprintf(w, "- **Matching Policies**: %s\n", strings.Join(r.Network.Policies, ", "))
	}
	if len(r.Network.Services) > 0 {
		fmt.Fprintln(w, "- **Services**:")
		for _, svc := range r.Network.Services {
			fmt.Fprintf(w, "  - `%s` ports: %s\n", svc.Name, strings.Join(svc.Ports, ", "))
		}
	}
	fmt.Fprintln(w)

	// RBAC
	fmt.Fprintln(w, "## RBAC")
	if len(r.RBAC.Bindings) > 0 {
		fmt.Fprintln(w, "| Binding | Role | Kind | Cluster-Wide |")
		fmt.Fprintln(w, "|---------|------|------|--------------|")
		for _, b := range r.RBAC.Bindings {
			fmt.Fprintf(w, "| `%s` | `%s` | %s | %v |\n", b.BindingName, b.RoleName, b.RoleKind, b.IsCluster)
		}
		fmt.Fprintln(w)
	} else {
		fmt.Fprintln(w, "_No role bindings found._")
	}
	for _, warning := range r.RBAC.Warnings {
		fmt.Fprintf(w, "> ⚠ %s\n", warning)
	}
	fmt.Fprintln(w)

	// Recommendations
	fmt.Fprintln(w, "## What to Check Next")
	for _, rec := range r.Recommendations {
		fmt.Fprintf(w, "- %s\n", rec)
	}
	fmt.Fprintln(w)
}

func fmtBoolPtr(b *bool) string {
	if b == nil {
		return "unset"
	}
	return fmt.Sprintf("%v", *b)
}
