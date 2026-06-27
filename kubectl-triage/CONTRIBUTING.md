# Contributing to kubectl-triage

## Requirements

- Go 1.22+
- `golangci-lint` (optional, for lint step)

## Getting started

```bash
git clone https://github.com/topcug/kubectl-triage.git
cd kubectl-triage
make build
make test
```

## Development workflow

```bash
make fmt       # format code
make lint      # run linter
make test      # run tests with race detector
make build     # build binary to ./bin/kubectl-triage
make install   # install to $(go env GOPATH)/bin
```

## Project layout

```
cmd/                    cobra commands (pod, deployment, job, root)
internal/
  kube/                 Kubernetes API fetchers (read-only)
  render/               output renderers: table, json, markdown
  triage/               report assembly and recommendation logic
  config/               .kubectl-triage.yaml config loader
pkg/types/              shared TriageReport struct
test/fixtures/          fake Kubernetes objects for unit tests
docs/                   extended documentation
```

## Adding a new check

1. Add the relevant field(s) to `pkg/types/report.go`.
2. Fetch data in the appropriate `internal/kube/fetch_*.go` file.
3. Populate the field in `internal/triage/assemble.go`.
4. Add a bullet rule in `internal/triage/score.go` (`BuildSummaryBullets` and/or `Recommend`).
5. Render it in `internal/render/table.go` (and `markdown.go` if applicable).
6. Add a unit test in `internal/triage/score_test.go`.

## Adding a new resource type

1. Add `AssembleXxx` in `internal/triage/assemble.go`.
2. Add `cmd/xxx.go` following the pattern of `cmd/pod.go`.
3. Register the command in `cmd/root.go`.

## Commit style

```
<type>: <short description>

types: feat, fix, docs, test, refactor, chore, ci
```

## Releasing

Releases are handled by GoReleaser via the CI pipeline. To test locally:

```bash
make release-snapshot
```

Tag a release:

```bash
git tag v0.x.0
git push origin v0.x.0
```

The CI pipeline runs GoReleaser automatically on version tags.

## Pull requests

- Keep PRs focused — one concern per PR.
- All tests must pass (`make test`).
- Update `CHANGELOG.md` with a summary of your change under `[Unreleased]`.
