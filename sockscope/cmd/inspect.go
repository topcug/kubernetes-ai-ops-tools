package cmd

import (
	"errors"
	"fmt"
	"os"
	"time"

	"github.com/spf13/cobra"
	"github.com/topcug/sockscope/internal/model"
	"github.com/topcug/sockscope/internal/proc"
	"github.com/topcug/sockscope/internal/render"
	"github.com/topcug/sockscope/internal/triage"
)

type inspectOpts struct {
	pid         int
	name        string
	containerID string
	output      string
}

func newInspectCmd() *cobra.Command {
	var opts inspectOpts

	cmd := &cobra.Command{
		Use:   "inspect",
		Short: "Inspect the sockets owned by a process",
		Long: `Inspect resolves a process by PID, name, or container ID, reads
its open TCP, UDP and UNIX sockets from /proc, and prints a small
triage report.

Exactly one of --pid, --name or --container-id must be provided.`,
		RunE: func(_ *cobra.Command, _ []string) error {
			return runInspect(opts)
		},
	}

	cmd.Flags().IntVar(&opts.pid, "pid", 0, "inspect a specific PID")
	cmd.Flags().StringVar(&opts.name, "name", "", "inspect processes by comm name (exact match)")
	cmd.Flags().StringVar(&opts.containerID, "container-id", "", "inspect processes inside the given container ID")
	cmd.Flags().StringVarP(&opts.output, "output", "o", "table", "output format: table, json, markdown")

	return cmd
}

func runInspect(opts inspectOpts) error {
	pids, err := resolveTargetPIDs(opts)
	if err != nil {
		return err
	}
	if len(pids) == 0 {
		return fmt.Errorf("no matching processes found")
	}

	for i, pid := range pids {
		if i > 0 {
			fmt.Println()
		}
		if err := inspectOne(pid, opts.output); err != nil {
			fmt.Fprintf(os.Stderr, "pid %d: %v\n", pid, err)
		}
	}
	return nil
}

func resolveTargetPIDs(opts inspectOpts) ([]int, error) {
	set := 0
	if opts.pid > 0 {
		set++
	}
	if opts.name != "" {
		set++
	}
	if opts.containerID != "" {
		set++
	}
	if set == 0 {
		return nil, fmt.Errorf("one of --pid, --name or --container-id is required")
	}
	if set > 1 {
		return nil, fmt.Errorf("--pid, --name and --container-id are mutually exclusive")
	}

	switch {
	case opts.pid > 0:
		return []int{opts.pid}, nil
	case opts.name != "":
		return proc.FindPIDsByName(opts.name)
	default:
		return proc.FindPIDsByContainerID(opts.containerID)
	}
}

func inspectOne(pid int, output string) error {
	ps, err := proc.ReadProcess(pid)
	if err != nil {
		if errors.Is(err, os.ErrPermission) {
			return fmt.Errorf("permission denied — try: sudo sockscope inspect --pid %d", pid)
		}
		return err
	}
	sockets, err := proc.ReadSocketsForPID(pid)
	if err != nil {
		if errors.Is(err, os.ErrPermission) {
			return fmt.Errorf("permission denied — try: sudo sockscope inspect --pid %d", pid)
		}
		return err
	}
	hints := triage.Hints(ps, sockets)

	report := model.Report{
		Process:     ps,
		Sockets:     sockets,
		Mix:         model.ComputeMix(sockets),
		Hints:       hints,
		GeneratedAt: time.Now().UTC(),
	}

	switch output {
	case "table", "":
		return render.Table(os.Stdout, report)
	case "json":
		return render.JSON(os.Stdout, report)
	case "markdown", "md":
		return render.Markdown(os.Stdout, report)
	default:
		return fmt.Errorf("unknown output format %q (expected table, json or markdown)", output)
	}
}
