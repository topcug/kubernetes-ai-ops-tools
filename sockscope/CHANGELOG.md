# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-04-07

### Added
- Socket summary block in table and markdown output: per-type counts (TCP/UDP/UNIX), external, loopback, abstract/named UNIX breakdown.
- Mini ASCII bar chart in table output visualising socket type distribution.
- Inode numbers shown per socket in table and markdown output.
- `SocketMix` struct in the JSON output (`socket_mix` field) with all counts.

### Changed
- Triage notes are now numerical: "1 external TCP connection", "11 UNIX IPC socket(s) present".
- UNIX socket hints now include the socket count.

## [0.1.2] - 2026-04-07

### Fixed
- `sockscope --version` now shows the correct module version (e.g. `v0.1.2`) when installed via `go install` instead of `dev`.

## [0.1.1] - 2026-04-07

### Fixed
- Permission denied errors now show an actionable hint: `try: sudo sockscope inspect --pid <pid>`.

## [0.1.0] - 2026-04-07

### Added
- Initial release.
- `sockscope inspect --pid <pid>` — inspect a specific process.
- `sockscope inspect --name <comm>` — inspect processes by `/proc/<pid>/comm` name.
- `sockscope inspect --container-id <id>` — inspect processes inside a given container.
- TCP, UDP, and UNIX socket resolution via `/proc/net/{tcp,tcp6,udp,udp6,unix}`.
- Process context: PID, PPID, command, UID, cgroup, container ID extraction.
- Table, JSON, and Markdown output formats (`-o table|json|markdown`).
- Triage notes layer with human-readable hints (no risk scores).
- Apache-2.0 license, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.
- GitHub Actions CI (build, vet, test, golangci-lint) and release workflow via GoReleaser.

[Unreleased]: https://github.com/topcug/sockscope/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/topcug/sockscope/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/topcug/sockscope/releases/tag/v0.1.0
