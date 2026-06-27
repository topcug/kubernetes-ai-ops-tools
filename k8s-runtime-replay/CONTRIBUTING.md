# Contributing to k8s-runtime-replay

Thank you for your interest in contributing. This document covers how to report issues, propose features, and submit pull requests.

---

## Code of conduct

Be respectful and constructive. This is a professional tool used in security and operations contexts — keep language and framing appropriate for that audience.

---

## Reporting issues

Use the [GitHub issue tracker](../../issues). Before opening a new issue, check whether a similar one already exists.

For bug reports, include:
- What command you ran
- What you expected to happen
- What actually happened (full terminal output)
- Your environment: OS, Kubernetes version, cluster type (kind, minikube, remote), Falco version if relevant

For feature requests, describe the problem you are trying to solve rather than a specific solution.

---

## Proposing a new scenario

A scenario is a good fit if:
- It reproduces a real, observable Kubernetes runtime behavior
- It can run safely on a test cluster without requiring privileged access or destructive actions
- It is scoped to a single, well-defined behavior

To propose a new scenario, open an issue first and describe:
- The behavior you want to reproduce
- The expected detection signal
- Any RBAC, network, or cluster requirements

---

## Development workflow

### Setup

```bash
git clone https://github.com/gulcan-mastery/k8s-runtime-replay
cd k8s-runtime-replay
make setup-kind
```

### Running scenarios locally

```bash
make scenario-shell-spawn
make cleanup-shell-spawn
```

### Linting

All shell scripts must pass `shellcheck`:

```bash
find . -name "*.sh" -not -path "./.git/*" | xargs shellcheck --severity=warning
```

### Adding a scenario

Follow the checklist in [docs/scenario-authoring.md](docs/scenario-authoring.md).

### Submitting a pull request

1. Fork the repository
2. Create a branch: `git checkout -b feat/my-scenario`
3. Make your changes
4. Run shellcheck on any `.sh` files you modified
5. Verify the scenario runs cleanly on a fresh kind cluster
6. Open a pull request against `main`

---

## Language rules

The following words must never appear in scenario files, READMEs, commit messages, or pull request descriptions:

- `attack`, `exploit`, `weaponize`, `compromise`, `malicious`, `payload`, `hack`

Use instead: `simulate`, `replay`, `reproduce`, `trigger`, `validate`, `observe`, `verify`.

---

## Detection language rules

Do not hardcode Falco rule names as expected values. Use semantic descriptions in `scenario.yaml` and list backend-specific variants in the scenario `README.md`. See [docs/scenario-authoring.md](docs/scenario-authoring.md) for the full contract.

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/). Breaking changes to the exit code model, `scenario.yaml` spec, or trigger script interface are considered breaking changes requiring a major version bump.
