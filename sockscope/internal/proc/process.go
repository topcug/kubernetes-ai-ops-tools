package proc

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/topcug/sockscope/internal/model"
)

// ReadProcess gathers a ProcessSummary for the given PID by reading
// /proc/<pid>/status, /proc/<pid>/cmdline, /proc/<pid>/stat and
// /proc/<pid>/cgroup. Missing individual fields are tolerated; only
// a completely vanished process causes an error.
func ReadProcess(pid int) (model.ProcessSummary, error) {
	base := filepath.Join(ProcRoot, strconv.Itoa(pid))
	if _, err := os.Stat(base); err != nil {
		return model.ProcessSummary{}, fmt.Errorf("process %d: %w", pid, err)
	}

	ps := model.ProcessSummary{PID: pid}

	if status, err := os.ReadFile(filepath.Join(base, "status")); err == nil {
		for _, line := range strings.Split(string(status), "\n") {
			switch {
			case strings.HasPrefix(line, "Name:"):
				ps.Command = strings.TrimSpace(strings.TrimPrefix(line, "Name:"))
			case strings.HasPrefix(line, "PPid:"):
				if v, err := strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(line, "PPid:"))); err == nil {
					ps.PPID = v
				}
			case strings.HasPrefix(line, "Uid:"):
				// Format: Uid: <real> <effective> <saved> <fs>
				fields := strings.Fields(strings.TrimPrefix(line, "Uid:"))
				if len(fields) > 0 {
					if v, err := strconv.Atoi(fields[0]); err == nil {
						ps.UID = v
					}
				}
			}
		}
	}

	if cmdline, err := os.ReadFile(filepath.Join(base, "cmdline")); err == nil {
		// /proc/<pid>/cmdline uses NUL separators.
		parts := strings.Split(strings.TrimRight(string(cmdline), "\x00"), "\x00")
		if len(parts) > 0 && parts[0] != "" {
			ps.Executable = parts[0]
			ps.Command = strings.Join(parts, " ")
		}
	}

	if stat, err := os.ReadFile(filepath.Join(base, "stat")); err == nil {
		// Field 22 is starttime in clock ticks since boot. We keep
		// it as a raw string in v1 to avoid pulling in uptime math.
		fields := strings.Fields(string(stat))
		if len(fields) >= 22 {
			ps.StartTime = fields[21]
		}
	}

	if cg, err := os.ReadFile(filepath.Join(base, "cgroup")); err == nil {
		ps.CgroupPath = strings.TrimSpace(string(cg))
		ps.ContainerID = extractContainerID(ps.CgroupPath)
	}

	return ps, nil
}

// extractContainerID pulls a 64-character hex container ID out of a
// cgroup path if one is present. It returns an empty string when no
// container ID is found, which is the normal case on bare metal.
func extractContainerID(cgroupPath string) string {
	// Look for a 64-char hex run, optionally preceded by "docker-"
	// or "cri-containerd-" and optionally followed by ".scope".
	for _, line := range strings.Split(cgroupPath, "\n") {
		segments := strings.FieldsFunc(line, func(r rune) bool {
			return r == '/' || r == ':'
		})
		for _, seg := range segments {
			seg = strings.TrimSuffix(seg, ".scope")
			seg = strings.TrimPrefix(seg, "docker-")
			seg = strings.TrimPrefix(seg, "cri-containerd-")
			seg = strings.TrimPrefix(seg, "crio-")
			if len(seg) == 64 && isHex(seg) {
				return seg
			}
		}
	}
	return ""
}

func isHex(s string) bool {
	for _, r := range s {
		if !((r >= '0' && r <= '9') || (r >= 'a' && r <= 'f') || (r >= 'A' && r <= 'F')) {
			return false
		}
	}
	return true
}
