package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var (
	kubeconfig   string
	kubecontext  string
	outputFormat string
	namespace    string
	verbose      bool
	quiet        bool

	buildVersion = "dev"
	buildCommit  = "none"
	buildDate    = "unknown"
)

// SetVersion is called from main() with values injected via ldflags.
func SetVersion(version, commit, date string) {
	buildVersion = version
	buildCommit = commit
	buildDate = date
}

var rootCmd = &cobra.Command{
	Use:   "kubectl-triage",
	Short: "First-response context for suspicious Kubernetes workloads",
	Long: `kubectl-triage is a read-only kubectl plugin that collects the most useful
first checks for a pod, deployment, or job — without jumping between ten commands.

It is safe to run in production clusters. It never modifies cluster state.

Exit codes:
  0  triage complete, no risk signals detected
  1  error (resource not found, permission denied, timeout)
  2  triage complete, risk signals detected`,
	SilenceUsage: true,
}

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print kubectl-triage version",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("kubectl-triage %s (commit %s, built %s)\n", buildVersion, buildCommit, buildDate)
	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().StringVar(&kubeconfig, "kubeconfig", "", "path to kubeconfig file (default: $KUBECONFIG or ~/.kube/config)")
	rootCmd.PersistentFlags().StringVar(&kubecontext, "context", "", "kubernetes context to use")
	rootCmd.PersistentFlags().StringVarP(&namespace, "namespace", "n", "default", "namespace of the target resource")
	rootCmd.PersistentFlags().StringVarP(&outputFormat, "output", "o", "table", "output format: table | json | markdown")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "show full event list and owner chain")
	rootCmd.PersistentFlags().BoolVarP(&quiet, "quiet", "q", false, "output summary bullets and triage readout only")

	rootCmd.AddCommand(podCmd)
	rootCmd.AddCommand(deploymentCmd)
	rootCmd.AddCommand(jobCmd)
	rootCmd.AddCommand(versionCmd)
}

// validateOutputFormat returns an error for unrecognised -o values.
func validateOutputFormat(f string) error {
	switch f {
	case "table", "json", "markdown", "md":
		return nil
	default:
		return fmt.Errorf("unknown output format %q — valid values: table, json, markdown", f)
	}
}
