# curl-egress

## Goal

Make an outbound HTTP request from inside a container to validate detections for unexpected network egress from workloads.

## Safety

Safe. The default target is a public metadata endpoint (`ifconfig.me`). No sensitive data is sent. If a NetworkPolicy denies egress, the request is blocked — this is correct behavior. Runs in an isolated namespace. Designed for test clusters only.

## What gets deployed

A minimal pod (`curl-egress-target`) in the `k8s-replay` namespace running a base image with `curl` available.

## What gets triggered

A `curl` command inside the container makes an outbound HTTP GET request to an external URL.

## Expected runtime evidence

The `curl` call completes with an HTTP response code (2xx–5xx). The network connection is visible in the container's syscall trace.

## Detection semantics

This scenario produces an unexpected outbound network connection from a container. If a runtime detection tool is installed, it should alert on outbound connections from containers. The exact alert name depends on the loaded ruleset and version.

## Known backend-specific variants

Rule names vary by detection tool, ruleset version, and configuration:

- Falco: `Unexpected outbound connection destination`, `Unexpected network outbound activity`
- NetworkPolicy: if egress is denied, the connection is blocked before a runtime alert fires

Use this scenario to validate event visibility first, then map it to your local rule names.

## Deploy and trigger

```bash
make scenario-curl-egress
```

Override the egress target:

```bash
CURL_EGRESS_TARGET=http://example.com make scenario-curl-egress
```

Clean state is enforced by default. To reuse an existing pod:

```bash
make scenario-curl-egress FAST=1
```

JSON output:

```bash
make scenario-curl-egress JSON=1
```

## Cleanup

```bash
make cleanup-curl-egress
```

## Failure modes

| Symptom | Likely cause |
|---------|--------------|
| `behavior: FAIL` | NetworkPolicy is blocking egress — expected in restricted clusters. The scenario still passes at the trigger level. |
| `curl` timeout | Target URL is unreachable from cluster network |
| `detection: NOT VERIFIED` | Ruleset does not include a matching outbound rule, or search pattern does not match Falco output text |
| `detection: SKIP` | Falco is not installed — run `make setup-falco` to install |

For detection issues, run `make logs-falco-raw` to inspect actual Falco output and compare against expected patterns in `scenario.yaml`.
