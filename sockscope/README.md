<p align="center">
  <img src="sockscope.png" alt="sockscope" width="280" />
</p>

<h1 align="center">sockscope</h1>

<p align="center">
  A small CLI for looking at what a Linux process is actually talking to.
</p>

<p align="center">
  <a href="https://github.com/topcug/sockscope/actions/workflows/ci.yml"><img src="https://github.com/topcug/sockscope/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/topcug/sockscope/releases/latest"><img src="https://img.shields.io/github/v/release/topcug/sockscope?sort=semver" alt="Release"></a>
  <a href="https://goreportcard.com/report/github.com/topcug/sockscope"><img src="https://goreportcard.com/badge/github.com/topcug/sockscope" alt="Go Report Card"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/topcug/sockscope" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/platform-linux-blue" alt="Linux only">
</p>

---

`sockscope` shows you the sockets a process has open, where its connections are going, and a short list of things you might want to look at next. It's meant for those moments when something is behaving oddly on a box and you want a quick, honest picture of what that process is doing on the network.

<p align="center">
  <img src="docs/demo.gif" alt="sockscope inspect demo" width="720" />
</p>

## Quick look

```bash
# Install (requires Go 1.23+)
go install github.com/topcug/sockscope@latest
export PATH="$HOME/go/bin:$PATH"   # if ~/go/bin isn't already on your PATH

# Find processes with open sockets
sudo ss -tnp | awk 'NR>1 {print $NF}' | grep -oP 'pid=\K[0-9]+' | sort -u

# Then point it at one
sudo sockscope inspect --pid <pid>

# Or look up by name directly
sudo sockscope inspect --name sshd
```

```text
Process
  PID:              1234
  Name:             python
  Command:          python app.py
  PPID:             1200
  UID:              1000
  Container:        payments-api7

Sockets
  TCP   10.42.1.15:48122       -> 34.120.55.2:443         ESTABLISHED
  TCP   127.0.0.1:8080         -> 127.0.0.1:37014         ESTABLISHED
  UNIX  /tmp/agent.sock

Triage notes
  - External connection present: review whether 34.120.55.2:443 is an expected outbound destination
  - IPC via UNIX socket present
```

## Why it exists

When something looks off on a Linux box, you usually end up running `ss`, then `lsof`, then poking around in `/proc`, then checking which container the process belongs to — all to answer the same basic question: what is this thing talking to, and does any of it look wrong?

`sockscope` does that walk for you and prints the result on one screen. It reads `/proc` directly, so there's no shelling out to `ss` or `lsof`, and the output is plain enough to paste into an incident note or a Slack message.

## What it isn't

It's not a packet capture tool, a port scanner, a SIEM, or an eBPF observability platform. It doesn't replace any of those. It just gives you a quick first look at one process and its sockets, and leaves the deeper analysis to whichever tool you'd normally reach for next.

## Install

`sockscope` is Linux-only — it reads everything it needs from `/proc`, so it doesn't run on macOS or Windows.

### With `go install` (recommended for now)

If you have a Go toolchain (1.23 or newer):

```bash
go install github.com/topcug/sockscope@latest
```

One thing to know: `go install` drops the binary in `$(go env GOPATH)/bin`, which is `~/go/bin` on most setups. That directory is **not** on your `PATH` by default on most Linux distributions, so right after installing you'll probably get `sockscope: command not found`. To fix it, add `~/go/bin` to your shell's startup file once:

```bash
# bash
echo 'export PATH="$HOME/go/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# zsh
echo 'export PATH="$HOME/go/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

sockscope --version
# sockscope version v0.2.0
```

After that, `sockscope --version` should work from any directory, and every tool you install with `go install` in the future will too.

#### Running as root

Inspecting processes you don't own requires root. `sudo` typically strips your `PATH`, so the binary won't be found. The cleanest fix is to symlink it into `/usr/local/bin` once:

```bash
sudo ln -sf "$HOME/go/bin/sockscope" /usr/local/bin/sockscope
```

After that, `sudo sockscope inspect --pid <pid>` works normally. Alternatively, pass your current `PATH` inline without the symlink.

You can find something with actual sockets with: `sudo ss -tnp | awk 'NR>1 {print $NF}' | grep -oP 'pid=\K[0-9]+' | sort -u`

```bash
sudo env PATH="$PATH" sockscope inspect --pid <pid>
```

### From source

```bash
git clone https://github.com/topcug/sockscope
cd sockscope
go build -o sockscope .
sudo mv sockscope /usr/local/bin/
sockscope --version
```

### Prebuilt binaries

Prebuilt Linux tarballs (amd64 and arm64) are available on the [releases page](https://github.com/topcug/sockscope/releases). Download, extract, and move the binary to somewhere on your `PATH`:

```bash
curl -LO https://github.com/topcug/sockscope/releases/latest/download/sockscope_linux_amd64.tar.gz
tar -xzf sockscope_linux_amd64.tar.gz
sudo mv sockscope /usr/local/bin/
sockscope --version
```

## Usage

v1 exposes three ways to select a target:

```bash
sockscope inspect --pid 1234
sockscope inspect --name nginx
sockscope inspect --container-id 7bc4d5e9f1a2
```

`--name` matches against `/proc/<pid>/comm` exactly (the kernel truncates comm at 15 characters, so long process names should be matched by PID).

`--container-id` matches any PID whose `/proc/<pid>/cgroup` path contains the given ID, which covers Docker, containerd, CRI-O and most Kubernetes runtimes.

## Output formats

```bash
sockscope inspect --pid 1234                 # table (default)
sockscope inspect --pid 1234 -o json         # for jq and SIEM pipelines
sockscope inspect --pid 1234 -o markdown     # for issues, incident notes, Slack
```

The JSON shape is stable within a major version: `{process, sockets, hints, generated_at}`.

## Triage notes

At the bottom of every report there's a short notes section. It's meant to point out things that are usually worth a second look — an external connection, a listening port, a UNIX socket, a process running as root — without making any claims about whether they're actually a problem.

The language is deliberately soft. You'll see words like "review" and "worth checking" rather than "suspicious" or "malicious", and there are no risk scores. The idea is to give you a nudge toward the next question, not to make the call for you.

Things it will currently flag:

- External outbound connections
- Loopback-only communication
- Listening sockets
- UNIX socket IPC
- Processes running as root
- Interactive shells

## Roadmap

- **v1** — `/proc`-based inspection by PID, name, or container ID, with table, JSON, and Markdown output.
- **v1.1** — Better container awareness, namespace detection, and pod metadata.
- **v2** — An optional `sockscope watch` built on eBPF, so you can follow `connect`, `accept`, `bind`, and `close` events as they happen.

`watch` and `graph` are left out of v1 on purpose. The first release is just about getting a clean one-shot view working well.

## Project

- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Release process](docs/RELEASING.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
