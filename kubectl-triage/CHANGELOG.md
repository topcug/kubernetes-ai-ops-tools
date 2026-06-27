# Changelog

All notable changes to kubectl-triage are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- `--quiet` / `-q` flag: outputs summary bullets and triage readout only
- Exit code semantics: `0` = clean, `1` = error, `2` = risk signals detected
- `SummaryBullets` stored on `TriageReport` struct (available in `-o json`)
- `internal/config` package: loads `.kubectl-triage.yaml` from cwd or `$HOME`
- `make fmt` target
- GitHub issue templates (bug report, feature request)
- GitHub pull request template
- `CONTRIBUTING.md`
- `docs/` directory: advanced usage, output format reference, when not to use

---

## [v0.1.0] — 2026-04-05

### Added
- `kubectl triage pod` — full pod triage: workload, images, security, SA, events, logs, network, RBAC, recommendations
- `kubectl triage deployment` — deployment triage with replica status
- `kubectl triage job` — job triage with condition reporting
- Output formats: `table` (default, coloured), `json`, `markdown`
- `--verbose` flag: full event list and owner chain
- `--context` and `--kubeconfig` flags
- 8-second total timeout with partial results on permission errors
- GoReleaser pipeline for cross-platform binaries (linux/darwin/windows, amd64/arm64)
- CI pipeline: test + lint + release on version tags
- Krew plugin manifest (`kubectl-triage.yaml`)
