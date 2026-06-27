# Scenario authoring guide

This document covers how to add a new scenario to k8s-runtime-replay, the required file structure, naming rules, and the language contract that keeps the repository safe and professional.

## Repository philosophy

The primary success condition of any scenario is reproducing the intended runtime behavior safely and repeatably. Detection backend verification is a second layer — optional and adapter-based.

A scenario is considered passing when the behavior is triggered and confirmed. Detection outcome is reported separately.

## File structure

Every scenario must follow this layout exactly:

```
scenarios/<scenario-id>/
  scenario.yaml      — machine-readable spec (required)
  README.md          — human-readable documentation (required)
  manifests/         — Kubernetes YAML (namespace, workload, RBAC)
  trigger.sh         — execution engine entry point
  cleanup.sh         — removes all scenario resources
```

## scenario.yaml spec

Every scenario must define a `scenario.yaml`. This is the machine-readable contract the tool reads — not the README.

Required fields:

```yaml
id: <scenario-id>
version: "0.1.0"
title: <short human title>
goal: <one sentence describing what this scenario reproduces>
safety: safe
namespace: k8s-replay

deploy:
  manifests:
    - manifests/namespace.yaml   # if scenario creates its own namespace
    - manifests/workload.yaml

workload:
  selector: scenario=<scenario-id>
  pod_name: <pod-name>
  container: target

trigger:
  kind: kubectl-exec             # or: curl, api-call, file-read
  command:
    - /bin/sh
    - -c
    - '<trigger command>'

behavior:
  description: <what observable artifact is produced>
  evidence:
    - exec_succeeded: true

detection:
  semantics:
    - <describe the behavior in plain language — not a rule name>
  falco:
    enabled: true
    search_patterns:
      - <keyword to search in Falco output>
    correlation:
      namespace: k8s-replay
      workload_selector: scenario=<scenario-id>

timeouts:
  ready_seconds: 60
  detect_seconds: 20

cleanup:
  script: cleanup.sh
```

`detection.semantics` must describe the behavior, not a Falco rule name. Rule names go in the README under "Known backend-specific variants".

## README structure

Every scenario README must contain these sections in this order:

```
# <scenario-id>

## Goal
## Safety
## What gets deployed
## What gets triggered
## Expected runtime evidence
## Detection semantics
## Known backend-specific variants
## Deploy and trigger
## Cleanup
## Failure modes
```

Do not use "Expected Falco rule" as a heading. Use "Detection semantics" and "Known backend-specific variants" instead.

## trigger.sh structure

Every trigger script must follow the 7-phase execution engine pattern:

```
Phase 0: init result (RESULT_SCENARIO, RESULT_CONTEXT)
Phase 1: preflight (safety_banner, require_kubectl, check_not_production, check_falco)
Phase 2: deploy
Phase 3: wait ready
Phase 4: trigger — record TRIGGER_TIME=$(date +%s) before the trigger command
Phase 5: behavior verification (verify_exec_succeeded / verify_file_read / verify_network_request / verify_api_call)
Phase 6: detection verification (adapter_verify)
Phase 7: output (print_summary + print_detail, or result_to_json if JSON=1)
```

Source these libraries in this order:

```bash
source "${REPO_ROOT}/lib/common.sh"
source "${REPO_ROOT}/lib/checks.sh"
source "${REPO_ROOT}/lib/result.sh"
source "${REPO_ROOT}/lib/behavior.sh"
source "${REPO_ROOT}/lib/output.sh"
source "${REPO_ROOT}/lib/detection/falco.sh"
```

Clean state is enforced by default. Delete the target pod before deploying unless `FAST=1` is set:

```bash
if [[ "${FAST:-0}" != "1" ]]; then
  kubectl delete pod <pod-name> -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
fi
```

Add a dry-run guard immediately before Phase 2 (deploy). This guard must come after the preflight phase so that safety checks still run:

```bash
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  info "[dry-run] Would deploy: <manifest list>"
  info "[dry-run] Would trigger: <trigger command summary>"
  info "[dry-run] Would verify: <behavior check summary>"
  info "[dry-run] No cluster changes made."
  exit 0
fi
```

## Naming rules

Scenario IDs use lowercase kebab-case: `shell-spawn`, `sa-token-read`, `curl-egress`.

### Required vocabulary

Use these words to describe what a scenario does:

- `simulate`, `replay`, `reproduce`, `trigger`, `validate`, `observe`, `verify`

### Forbidden vocabulary

Never use these words anywhere in scenario files, READMEs, or commit messages:

- `attack`, `exploit`, `weaponize`, `compromise`, `malicious`, `payload`, `hack`

This applies to file names, variable names, comments, and documentation.

## Detection language rules

Never hardcode an exact Falco rule name as an expected value. Rule names vary by ruleset version and configuration.

Instead, separate the semantic expectation from the backend-specific variant:

**Wrong:**
```yaml
expected_signal: Terminal shell in container
```

**Right:**
```yaml
detection:
  semantics:
    - shell execution inside container
  falco:
    search_patterns:
      - shell
      - terminal shell
```

And in the README:

```md
## Detection semantics
This scenario produces a shell execution event inside a container.

## Known backend-specific variants
- Falco: `Terminal shell in container`, `Shell Spawned in a Container`
- Audit-based: `Attach/Exec Pod`
```

## Exit codes

Trigger scripts exit with a structured code. CI and tooling can use these to distinguish scenario success from detection outcome:

| Code | Meaning |
|------|---------|
| 0    | Scenario passed, detection verified |
| 10   | Scenario passed, detection skipped (no backend) |
| 11   | Scenario passed, detection not verified |
| 20   | Preflight failed |
| 21   | Deploy failed |
| 22   | Readiness timeout |
| 23   | Trigger failed |
| 24   | Behavior not observed |

Exit code 11 means the scenario succeeded. Detection not being verified does not mean the scenario failed.

## Adding a new scenario — checklist

- [ ] Create `scenarios/<id>/scenario.yaml` with `id`, `version`, `title`, `goal`, `safety`, `namespace`, `deploy`, `workload`, `trigger`, `behavior`, `detection`, `timeouts`, `cleanup`
- [ ] Create `scenarios/<id>/README.md` with all required sections (Goal, Safety, What gets deployed, What gets triggered, Expected runtime evidence, Detection semantics, Known backend-specific variants, Deploy and trigger, Cleanup, Failure modes)
- [ ] Create `scenarios/<id>/manifests/` with workload YAML
- [ ] Create `scenarios/<id>/trigger.sh` following the 7-phase pattern with `DRY_RUN` guard
- [ ] Create `scenarios/<id>/cleanup.sh`
- [ ] Add `make scenario-<id>` and `make cleanup-<id>` targets to Makefile with `DRY_RUN=$(DRY_RUN)` passed through
- [ ] `make list-scenarios` now reads `scenario.yaml` dynamically — no manual update needed
- [ ] Verify: `bash -n scenarios/<id>/trigger.sh` passes (syntax check)
- [ ] Verify: `make scenario-<id> DRY_RUN=1` exits 0 and prints planned actions
- [ ] Verify: scenario runs cleanly on a fresh kind cluster
- [ ] Verify: `make cleanup-<id>` removes all resources
- [ ] Verify: `make scenario-<id> JSON=1` outputs valid JSON
