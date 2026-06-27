# Contributing to sockscope

Thanks for taking a look. Small fixes, bug reports, and PRs are all welcome.

## Before you start on something big

`sockscope` is trying to stay small, so if you're planning a larger change it's usually a good idea to open an issue first. That way we can talk through whether it fits before you spend time on it.

A few things that probably won't land in v1, just so you know up front:

- Packet capture
- Web UIs or TUIs
- Kubernetes API discovery
- DNS reverse lookup enrichment
- Live socket watching (that's planned for v2, on top of eBPF)

None of these are bad ideas — they're just outside what v1 is trying to do.

## Getting set up

```bash
git clone https://github.com/topcug/sockscope
cd sockscope
go build ./...
go test ./...
```

`sockscope` is Linux-only because everything it reads lives under `/proc`. When you're writing or changing parsers in `internal/proc`, please test them against fixtures in `test/fixtures` rather than whatever happens to be running on your laptop — it makes the tests reproducible for everyone else.

## A few style notes

- Keep the public API small. If something doesn't need to be exported, leave it unexported.
- Comments are more useful when they explain *why* a piece of code exists than when they restate *what* it does.
- Please keep the triage output soft. Use words like "review" or "worth checking" rather than "suspicious" or "malicious", and don't add risk scores.

## Commit messages

A clear one-line summary is enough. Conventional Commits are fine too if that's what you're used to, but they're not required.
