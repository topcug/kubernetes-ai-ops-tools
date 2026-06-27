# Changelog

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- `DRY_RUN=1` flag: prints planned actions without making cluster changes
- `docs/advanced-usage.md`: JSON output, CI integration, dry-run, custom scenarios
- `CONTRIBUTING.md`: contribution guide
- `CHANGELOG.md`: this file
- `.github/ISSUE_TEMPLATE/`: bug report and feature request templates
- `.github/pull_request_template.md`: PR template
- `docs/scenario-authoring.md`: full scenario authoring guide
- Prebuilt binary release pipeline via GitHub Actions
- `scenario.yaml` per-scenario machine-readable spec (standardized)
- `lib/common.sh`: `kube_apply`, `kube_exec`, `kube_delete` dry-run wrappers
- `lib/common.sh`: `DRY_RUN` environment variable support

### Changed
- README restructured: problem statement first, replay concept in one paragraph, quick start reduced to two commands
- README: scenario catalog table with run commands
- README: working diagram added
- README: limitations section added
- README: install section covers binary, Docker, and direct clone
- README: deterministic run guarantee documented
- README: output format stabilized and documented
- README: log verbosity table added
- README: `how to extend scenarios` section added
- README: sample detection use-case added
- Makefile: `DRY_RUN` variable added to all scenario targets
- `docs/scenario-authoring.md`: scenario authoring guide expanded

---

## [0.1.0] — 2024-01-01

### Added
- Initial release
- 5 core scenarios: `shell-spawn`, `sa-token-read`, `kubectl-exec`, `curl-egress`, `secret-enumeration`
- 7-phase execution engine per scenario
- Behavior verification independent of detection backend
- JSON output via `JSON=1`
- Exit code model (0, 10, 11, 20–24)
- Falco detection adapter (`lib/detection/falco.sh`)
- Production cluster guard
- Safety banner on every trigger
- `make setup-kind`, `make setup-falco`, `make doctor`
- `make list-scenarios`
- Docs: `local-cluster.md`, `falco-setup.md`, `workshop-mode.md`
- CI: shellcheck lint + YAML manifest dry-run validation
