package cmd

import (
	"github.com/spf13/cobra"
	"github.com/topcug/sockscope/pkg/version"
)

// NewRootCmd builds the top-level `sockscope` command. The root
// itself does nothing; it only wires up subcommands.
func NewRootCmd() *cobra.Command {
	root := &cobra.Command{
		Use:   "sockscope",
		Short: "Process-to-socket inspection for Linux and containers",
		Long: `sockscope is a small CLI that helps engineers understand which
sockets a process owns, where those connections go, and what to
check first during runtime triage.

It is not a packet capture tool, a port scanner, or a SIEM. It
answers one question: given a process, what is it talking to and
what should I look at first?`,
		Version:       version.Version,
		SilenceUsage:  true,
		SilenceErrors: false,
	}

	root.AddCommand(newInspectCmd())
	return root
}
