package proc

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// ProcRoot is the path to the proc filesystem. It is a variable so
// tests can point it at a fixture directory.
var ProcRoot = "/proc"

// ListPIDs returns every numeric PID currently present under /proc.
// Non-numeric entries (like "self", "net", "stat") are ignored.
func ListPIDs() ([]int, error) {
	entries, err := os.ReadDir(ProcRoot)
	if err != nil {
		return nil, fmt.Errorf("read proc root: %w", err)
	}
	pids := make([]int, 0, len(entries))
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		pids = append(pids, pid)
	}
	return pids, nil
}

// FindPIDsByName returns every PID whose /proc/<pid>/comm matches the
// given name exactly. Matching /comm (rather than the full cmdline)
// keeps results predictable; the kernel truncates comm to 15 chars,
// so callers passing longer names should be aware of that limit.
func FindPIDsByName(name string) ([]int, error) {
	pids, err := ListPIDs()
	if err != nil {
		return nil, err
	}
	var matches []int
	for _, pid := range pids {
		comm, err := readComm(pid)
		if err != nil {
			// Process may have exited between ListPIDs and now.
			continue
		}
		if comm == name {
			matches = append(matches, pid)
		}
	}
	return matches, nil
}

// FindPIDsByContainerID returns every PID whose cgroup path contains
// the given container ID substring. This is a best-effort match that
// works for Docker, containerd and most Kubernetes runtimes because
// they all embed the container ID in the cgroup path.
func FindPIDsByContainerID(containerID string) ([]int, error) {
	if containerID == "" {
		return nil, fmt.Errorf("container id is empty")
	}
	pids, err := ListPIDs()
	if err != nil {
		return nil, err
	}
	var matches []int
	for _, pid := range pids {
		cg, err := readCgroup(pid)
		if err != nil {
			continue
		}
		if strings.Contains(cg, containerID) {
			matches = append(matches, pid)
		}
	}
	return matches, nil
}

func readComm(pid int) (string, error) {
	data, err := os.ReadFile(filepath.Join(ProcRoot, strconv.Itoa(pid), "comm"))
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(data)), nil
}

func readCgroup(pid int) (string, error) {
	data, err := os.ReadFile(filepath.Join(ProcRoot, strconv.Itoa(pid), "cgroup"))
	if err != nil {
		return "", err
	}
	return string(data), nil
}
