# Demo recordings

This page will host asciinema recordings and GIFs for each scenario once they are generated.

## Planned recordings

| Scenario | Status |
|----------|--------|
| `shell-spawn` — end-to-end run with Falco alert | planned (v0.4) |
| `sa-token-read` — token read + detection output | planned (v0.4) |
| `secret-enumeration` — API call + Falco alert | planned (v0.4) |
| `curl-egress` — outbound request + detection | planned (v0.4) |
| `kubectl-exec` — exec event + audit log | planned (v0.4) |

## Recording a scenario yourself

Install [asciinema](https://asciinema.org/):

```bash
pip install asciinema
```

Record a session:

```bash
asciinema rec demo-shell-spawn.cast
make setup-kind
make scenario-shell-spawn
make cleanup-shell-spawn
# Ctrl-D to stop recording
```

Convert to GIF with [agg](https://github.com/asciinema/agg):

```bash
agg demo-shell-spawn.cast demo-shell-spawn.gif
```
