# kubernetes-ai-ops-tools

A collection of small CLI tools for working with Kubernetes and AI infrastructure. Each tool is independent, focused on one problem, and built to fit into existing terminal workflows.

## Tools

| | Tool | Description |
|---|---|---|
| [![inboxr](https://raw.githubusercontent.com/topcug/inboxr/main/assets/inboxr_pipeline_overview.svg)](https://github.com/topcug/inboxr) | [inboxr](https://github.com/topcug/inboxr) | Generates realistic simulated digital workspaces (Gmail, Slack, Calendar, Drive) with personas and competing priorities, for training and evaluating AI agents. |
| [![k8s-runtime-replay](https://raw.githubusercontent.com/topcug/k8s-runtime-replay/main/k8s-runtime-replay.png)](https://github.com/topcug/k8s-runtime-replay) | [k8s-runtime-replay](https://github.com/topcug/k8s-runtime-replay) | Catalog of well-scoped Kubernetes runtime scenarios for testing detections, validating Falco rules, and running security workshops in a repeatable way. |
| [![kubectl-triage](https://raw.githubusercontent.com/topcug/kubectl-triage/main/kubectl-triage.png)](https://github.com/topcug/kubectl-triage) | [kubectl-triage](https://github.com/topcug/kubectl-triage) | Pulls together the information you need in the first 60 seconds of a Kubernetes incident into a single command. |
| [![secclear-cli](https://raw.githubusercontent.com/topcug/secclear-cli/main/assets/secclear-report.gif)](https://github.com/topcug/secclear-cli) | [secclear-cli](https://github.com/topcug/secclear-cli) | Takes output from multiple Kubernetes security scanners and produces one clean, deduplicated report. |
| [![sockscope](https://raw.githubusercontent.com/topcug/sockscope/main/sockscope.png)](https://github.com/topcug/sockscope) | [sockscope](https://github.com/topcug/sockscope) | Shows what a Linux process is actually talking to at the socket level. |

## Design approach

The tools sit at the intersection of Kubernetes operations and security research, and the goal across all of them is the same: make behavior observable and problems easier to diagnose. Some are useful for day-to-day cluster work, some for detection engineering, and some for AI workload testing. All are built for the terminal and intended to compose with whatever workflow you already have.

## Language and dependencies

`inboxr` is written in Python. `k8s-runtime-replay`, `kubectl-triage`, `secclear-cli`, and `sockscope` are written in Go. Each tool manages its own dependencies and installation instructions are in the individual repositories.

## License

Each tool is licensed separately under MIT or Apache 2.0. See the LICENSE file in each repository for details.
