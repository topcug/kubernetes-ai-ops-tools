package render

import (
	"fmt"
	"io"

	"github.com/topcug/sockscope/internal/model"
)

// Markdown writes the report in a shape that pastes cleanly into
// GitHub issues, incident docs, Slack (in a code fence) or internal
// wiki pages. Keep sections short and headings stable so downstream
// templates can rely on them.
func Markdown(w io.Writer, r model.Report) error {
	fmt.Fprintf(w, "# sockscope report: pid %d\n\n", r.Process.PID)
	fmt.Fprintf(w, "_Generated at %s_\n\n", r.GeneratedAt.Format("2006-01-02 15:04:05 MST"))

	fmt.Fprintln(w, "## Process")
	fmt.Fprintln(w, "| Field | Value |")
	fmt.Fprintln(w, "|---|---|")
	fmt.Fprintf(w, "| PID | %d |\n", r.Process.PID)
	fmt.Fprintf(w, "| PPID | %d |\n", r.Process.PPID)
	fmt.Fprintf(w, "| Command | `%s` |\n", r.Process.Command)
	fmt.Fprintf(w, "| UID | %d |\n", r.Process.UID)
	if r.Process.ContainerID != "" {
		fmt.Fprintf(w, "| Container | `%s` |\n", shortID(r.Process.ContainerID))
	}
	if r.Process.CgroupPath != "" {
		fmt.Fprintf(w, "| Cgroup | `%s` |\n", firstLine(r.Process.CgroupPath))
	}
	fmt.Fprintln(w)

	fmt.Fprintln(w, "## Sockets")
	if len(r.Sockets) == 0 {
		fmt.Fprintln(w, "_No sockets currently owned by this process._")
	} else {
		fmt.Fprintln(w, "| Kind | Local | Remote | State | Inode | Path |")
		fmt.Fprintln(w, "|---|---|---|---|---|---|")
		for _, s := range r.Sockets {
			fmt.Fprintf(w, "| %s | %s | %s | %s | %s | %s |\n",
				s.Kind, s.LocalAddress, s.RemoteAddress, s.State, s.Inode, s.Path)
		}
	}
	fmt.Fprintln(w)

	if len(r.Sockets) > 0 {
		m := r.Mix
		fmt.Fprintln(w, "## Socket summary")
		fmt.Fprintln(w, "| Type | Count |")
		fmt.Fprintln(w, "|---|---|")
		fmt.Fprintf(w, "| TCP | %d |\n", m.TCP)
		fmt.Fprintf(w, "| UDP | %d |\n", m.UDP)
		fmt.Fprintf(w, "| UNIX | %d |\n", m.Unix)
		fmt.Fprintf(w, "| External | %d |\n", m.External)
		fmt.Fprintf(w, "| Loopback | %d |\n", m.Loopback)
		fmt.Fprintf(w, "| Abstract/unnamed UNIX | %d |\n", m.Abstract)
		fmt.Fprintf(w, "| Named UNIX | %d |\n", m.Named)
		fmt.Fprintln(w)
	}

	if len(r.Hints) > 0 {
		fmt.Fprintln(w, "## Triage notes")
		for _, h := range r.Hints {
			fmt.Fprintf(w, "- %s\n", h)
		}
		fmt.Fprintln(w)
	}

	return nil
}
