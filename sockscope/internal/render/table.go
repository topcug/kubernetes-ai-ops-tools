package render

import (
	"fmt"
	"io"
	"strings"

	"github.com/topcug/sockscope/internal/model"
)

// Table writes a human-readable, terminal-friendly report. We
// deliberately do not pull in a table library: the layout is stable
// enough that plain Fprintf keeps the binary small and the output
// copy-pasteable into incident notes.
func Table(w io.Writer, r model.Report) error {
	fmt.Fprintln(w, "Process")
	fmt.Fprintf(w, "  PID:              %d\n", r.Process.PID)
	fmt.Fprintf(w, "  Name:             %s\n", firstWord(r.Process.Command))
	fmt.Fprintf(w, "  Command:          %s\n", r.Process.Command)
	fmt.Fprintf(w, "  PPID:             %d\n", r.Process.PPID)
	fmt.Fprintf(w, "  UID:              %d\n", r.Process.UID)
	if r.Process.ContainerID != "" {
		fmt.Fprintf(w, "  Container:        %s\n", shortID(r.Process.ContainerID))
	}
	if r.Process.CgroupPath != "" {
		fmt.Fprintf(w, "  Cgroup:           %s\n", firstLine(r.Process.CgroupPath))
	}

	fmt.Fprintln(w)
	fmt.Fprintln(w, "Sockets")
	if len(r.Sockets) == 0 {
		fmt.Fprintln(w, "  (none)")
	}
	for _, s := range r.Sockets {
		switch s.Kind {
		case model.KindTCP:
			inode := ""
			if s.Inode != "" {
				inode = fmt.Sprintf(" [inode:%s]", s.Inode)
			}
			fmt.Fprintf(w, "  TCP   %-22s -> %-22s %s%s\n", s.LocalAddress, s.RemoteAddress, s.State, inode)
		case model.KindUDP:
			inode := ""
			if s.Inode != "" {
				inode = fmt.Sprintf(" [inode:%s]", s.Inode)
			}
			fmt.Fprintf(w, "  UDP   %-22s -> %s%s\n", s.LocalAddress, s.RemoteAddress, inode)
		case model.KindUnix:
			path := s.Path
			if path == "" {
				path = "(abstract or unnamed)"
			}
			inode := ""
			if s.Inode != "" {
				inode = fmt.Sprintf(" [inode:%s]", s.Inode)
			}
			fmt.Fprintf(w, "  UNIX  %s%s\n", path, inode)
		}
	}

	if len(r.Sockets) > 0 {
		fmt.Fprintln(w)
		fmt.Fprintln(w, "Socket summary")
		m := r.Mix
		total := m.TCP + m.UDP + m.Unix
		fmt.Fprintf(w, "  TCP   %s %d\n", miniBar(m.TCP, total, 12), m.TCP)
		fmt.Fprintf(w, "  UDP   %s %d\n", miniBar(m.UDP, total, 12), m.UDP)
		fmt.Fprintf(w, "  UNIX  %s %d\n", miniBar(m.Unix, total, 12), m.Unix)
		fmt.Fprintln(w)
		fmt.Fprintf(w, "  External:              %d\n", m.External)
		fmt.Fprintf(w, "  Loopback:              %d\n", m.Loopback)
		fmt.Fprintf(w, "  Abstract/unnamed UNIX: %d\n", m.Abstract)
		fmt.Fprintf(w, "  Named UNIX:            %d\n", m.Named)
	}

	if len(r.Hints) > 0 {
		fmt.Fprintln(w)
		fmt.Fprintln(w, "Triage notes")
		for _, h := range r.Hints {
			fmt.Fprintf(w, "  - %s\n", h)
		}
	}
	return nil
}

// miniBar renders a small ASCII bar like [###......] scaled to width.
func miniBar(val, total, width int) string {
	if total == 0 || width == 0 {
		return "[" + strings.Repeat(".", width) + "]"
	}
	filled := val * width / total
	if filled == 0 && val > 0 {
		filled = 1
	}
	return "[" + strings.Repeat("#", filled) + strings.Repeat(".", width-filled) + "]"
}

func firstWord(s string) string {
	if i := strings.IndexByte(s, ' '); i >= 0 {
		return s[:i]
	}
	return s
}

func firstLine(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i]
	}
	return s
}

func shortID(id string) string {
	if len(id) > 12 {
		return id[:12]
	}
	return id
}
