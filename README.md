# kubernetes-ai-ops-tools

A collection of small CLI tools for working with Kubernetes and AI infrastructure. Each tool solves one specific operational problem and is designed to be used independently.

## Tools

| | Tool | Description |
|---|---|---|
| [![inboxr](https://raw.githubusercontent.com/topcug/inboxr/main/assets/inboxr_pipeline_overview.svg)](https://github.com/topcug/inboxr) | [inboxr](https://github.com/topcug/inboxr) | Synthetic workspace generator for training and evaluating AI agents. Produces realistic simulated digital workspaces (Gmail, Slack, Calendar, Drive) with personas and competing priorities. |
| [![k8s-runtime-replay](https://raw.githubusercontent.com/topcug/k8s-runtime-replay/main/k8s-runtime-replay.png)](https://github.com/topcug/k8s-runtime-replay) | [k8s-runtime-replay](https://github.com/topcug/k8s-runtime-replay) | Repeatable Kubernetes runtime behavior scenarios for testing detections, validating Falco rules, and running security workshops. |
| [![kubectl-triage](https://raw.githubusercontent.com/topcug/kubectl-triage/main/kubectl-triage.png)](https://github.com/topcug/kubectl-triage) | [kubectl-triage](https://github.com/topcug/kubectl-triage) | Collapses the first 60 seconds of Kubernetes incident triage into a single command. |
| [![secclear-cli](https://raw.githubusercontent.com/topcug/secclear-cli/main/assets/secclear-report.gif)](https://github.com/topcug/secclear-cli) | [secclear-cli](https://github.com/topcug/secclear-cli) | Aggregates output from multiple Kubernetes security scanners into a single clean report. |
| [![sockscope](https://raw.githubusercontent.com/topcug/sockscope/main/sockscope.png)](https://github.com/topcug/sockscope) | [sockscope](https://github.com/topcug/sockscope) | Shows what a Linux process is actually talking to at the socket level. |

## Design approach

Each tool in this collection does one thing. None of them require the others. They are built for the terminal, designed to be composable with existing workflows, and kept small enough to read and understand quickly.

The tools sit at the intersection of Kubernetes operations and security research. Some are useful for day-to-day cluster work, some for detection engineering, and some for AI workload testing. What they share is a focus on making behavior observable and problems easier to diagnose.

## Language and dependencies

- `inboxr` is written in Python
- `k8s-runtime-replay`, `kubectl-triage`, `secclear-cli`, and `sockscope` are written in Go

Each tool manages its own dependencies. See the individual repositories for installation instructions.

## License

Each tool is licensed separately. See the LICENSE file in each repository. All are MIT or Apache 2.0.
