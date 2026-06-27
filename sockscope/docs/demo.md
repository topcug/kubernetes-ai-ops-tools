# Recording the demo

The README links to `docs/demo.gif`. This file is produced from an [asciinema](https://asciinema.org) recording so the output stays real (real PIDs, real sockets, real triage notes), not a screenshot of fake text.

## Record a cast

Pick a process that has at least one external TCP connection (a browser helper, a language server, or a long-running daemon works well).

```bash
# 1. Install asciinema and agg (the official asciinema -> gif converter)
sudo apt install asciinema
cargo install --git https://github.com/asciinema/agg

# 2. Record
asciinema rec docs/demo.cast \
  --idle-time-limit=1.5 \
  --title "sockscope inspect demo"
```

Inside the recording, run three things in under 30 seconds:

```bash
sockscope inspect --pid <pid>
sockscope inspect --pid <pid> -o json | jq '.hints'
sockscope inspect --pid <pid> -o markdown
```

Exit with `Ctrl-D` to stop the recording.

## Convert to GIF

```bash
agg docs/demo.cast docs/demo.gif \
  --theme monokai \
  --font-size 14 \
  --speed 1.2
```

Commit both `docs/demo.cast` and `docs/demo.gif`. The cast file is small and lets viewers replay the demo at their own speed on asciinema.org.

## Rules

- No fake output. Every demo must be a real run against a real process.
- Keep the cast under 30 seconds. The whole point of sockscope is the one-command first look.
- No secrets in the recording. Scrub remote IPs only if they reveal internal infrastructure.
