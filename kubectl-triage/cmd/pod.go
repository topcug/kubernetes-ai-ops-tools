package cmd

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/spf13/cobra"
	"github.com/topcug/kubectl-triage/internal/kube"
	"github.com/topcug/kubectl-triage/internal/render"
	"github.com/topcug/kubectl-triage/internal/triage"
)

var podCmd = &cobra.Command{
	Use:   "pod <n>",
	Short: "Triage a pod",
	Long:  "Collect first-response context for a suspicious or misbehaving pod.",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		name := args[0]

		if err := validateOutputFormat(outputFormat); err != nil {
			return err
		}

		cs, err := kube.NewClient(kubeconfig, kubecontext)
		if err != nil {
			return fmt.Errorf("cannot connect to cluster: %w", err)
		}

		ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
		defer cancel()

		report, err := triage.AssemblePod(ctx, cs, name, namespace)
		if err != nil {
			return fmt.Errorf("pod %q not found in namespace %q: %w", name, namespace, err)
		}

		switch outputFormat {
		case "json":
			if err := render.JSON(os.Stdout, report); err != nil {
				return err
			}
		case "markdown", "md":
			render.Markdown(os.Stdout, report)
		default:
			render.Table(os.Stdout, report, verbose, quiet)
		}

		if len(report.SummaryBullets) > 0 && report.SummaryBullets[0] != "no obvious risk signals detected" {
			os.Exit(2)
		}
		return nil
	},
}
