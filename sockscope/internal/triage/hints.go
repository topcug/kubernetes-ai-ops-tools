package triage

import (
	"fmt"
	"strings"

	"github.com/topcug/sockscope/internal/model"
)

// Hints produces a small list of human-readable notes about a
// process and its sockets. The goal is first-response context, not
// verdicts. We never say "malicious" or "suspicious"; we say "review"
// or "worth checking" so the output is useful on both the security
// and platform sides.
func Hints(p model.ProcessSummary, sockets []model.SocketSummary) []string {
	var hints []string

	var (
		externals    []string
		loopbackOnly = true
		hasListening bool
		hasUnix      bool
	)

	for _, s := range sockets {
		switch {
		case s.IsExternal():
			externals = append(externals, s.RemoteAddress)
			loopbackOnly = false
		case s.IsListening():
			hasListening = true
			loopbackOnly = false
		case s.Kind == model.KindUnix:
			hasUnix = true
		default:
			if s.RemoteAddress != "" && !s.IsLoopback() {
				loopbackOnly = false
			}
			if s.Kind == model.KindTCP || s.Kind == model.KindUDP {
				if !s.IsLoopback() {
					loopbackOnly = false
				}
			}
		}
	}

	if len(sockets) == 0 {
		hints = append(hints, "No sockets currently owned by this process")
	}

	if len(externals) == 1 {
		hints = append(hints, fmt.Sprintf("1 external TCP connection: review whether %s is an expected outbound destination", externals[0]))
	} else if len(externals) > 1 {
		hints = append(hints, fmt.Sprintf("%d external TCP connections: review whether each destination is expected", len(externals)))
	}

	if loopbackOnly && len(sockets) > 0 {
		hints = append(hints, "Local-only communication (loopback)")
	}

	if hasListening {
		hints = append(hints, "Process is listening on one or more sockets: confirm exposure scope")
	}

	// Count UNIX sockets for a more informative hint
	var unixCount int
	for _, s := range sockets {
		if s.Kind == model.KindUnix {
			unixCount++
		}
	}
	if hasUnix {
		hints = append(hints, fmt.Sprintf("%d UNIX IPC socket(s) present", unixCount))
	}

	if p.UID == 0 {
		hints = append(hints, "Process is running as root: review whether elevated privileges are required")
	}

	if p.ContainerID == "" && strings.Contains(p.CgroupPath, "kubepods") {
		hints = append(hints, "Running inside a Kubernetes pod but container ID could not be resolved")
	}

	if isShell(p.Command) {
		hints = append(hints, "Process looks like an interactive shell: worth checking who started it and why")
	}

	return hints
}

func isShell(cmd string) bool {
	shells := []string{"bash", "sh", "zsh", "ash", "dash", "fish", "ksh"}
	// cmd may be a full command line; take the first token's basename.
	first := cmd
	if i := strings.IndexByte(cmd, ' '); i >= 0 {
		first = cmd[:i]
	}
	if i := strings.LastIndexByte(first, '/'); i >= 0 {
		first = first[i+1:]
	}
	for _, sh := range shells {
		if first == sh {
			return true
		}
	}
	return false
}
