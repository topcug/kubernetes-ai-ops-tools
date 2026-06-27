package main

import "github.com/topcug/kubectl-triage/cmd"

// version, commit, and date are set at build time via ldflags.
var (
	version = "dev"
	commit  = "none"
	date    = "unknown"
)

func main() {
	cmd.SetVersion(version, commit, date)
	cmd.Execute()
}
