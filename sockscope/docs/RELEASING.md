# Releasing sockscope

Releases are cut from `main`. Tags trigger the GoReleaser workflow in `.github/workflows/release.yml`, which builds the binaries, creates the GitHub release, and uploads the archives and checksums.

## Tag format

Tags follow [Semantic Versioning](https://semver.org): `vMAJOR.MINOR.PATCH`.

- `v0.x.y` — pre-1.0, minor bumps may break flags or JSON shape (documented in the changelog).
- `v1.0.0` — first stable release. After this, the CLI flags and JSON output shape are considered stable within `v1.x`.

## Cutting a release

1. Make sure `main` is green on CI.
2. Update `CHANGELOG.md`:
   - Move items from `[Unreleased]` into a new dated section.
   - Add a new empty `[Unreleased]` block at the top.
   - Update the link references at the bottom.
3. Commit: `chore: release vX.Y.Z`.
4. Tag the commit:
   ```bash
   git tag -a vX.Y.Z -m "sockscope vX.Y.Z"
   git push origin main --follow-tags
   ```
5. Wait for the `release` workflow to complete. Verify the GitHub release page has:
   - Linux amd64 and arm64 archives
   - `checksums.txt`
   - Auto-generated changelog from commit history

## Release note style

Keep release notes short and engineer-facing. Group under `Added`, `Changed`, `Fixed`, `Removed`, `Security`. Link to issues and PRs where relevant.

Example:

```md
## v0.2.0 — 2026-04-20

### Added
- `sockscope inspect --cgroup <path>` for direct cgroup selection.

### Fixed
- IPv6 addresses in `/proc/net/tcp6` now decode correctly on big-endian hosts.
```

## No force-pushing tags

Once a tag is pushed, do not move or delete it. If a release is broken, cut a new patch version.
