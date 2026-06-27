package model

// ProcessSummary holds the minimal context we need about a process
// for a single triage report. It is intentionally small and flat so
// that table, JSON and markdown renderers can consume it directly.
type ProcessSummary struct {
	PID         int    `json:"pid"`
	PPID        int    `json:"ppid"`
	Command     string `json:"command"`
	Executable  string `json:"executable"`
	UID         int    `json:"uid"`
	StartTime   string `json:"start_time"`
	CgroupPath  string `json:"cgroup_path"`
	ContainerID string `json:"container_id,omitempty"`
}
