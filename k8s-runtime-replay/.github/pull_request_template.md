## Summary

<!-- What does this PR do? One or two sentences. -->

## Type of change

- [ ] Bug fix
- [ ] New scenario
- [ ] Documentation update
- [ ] CI / tooling change
- [ ] Other

## Checklist

- [ ] Shell scripts pass `shellcheck --severity=warning`
- [ ] New or modified scenarios follow the 7-phase trigger pattern
- [ ] `scenario.yaml` uses semantic detection descriptions (not exact rule names)
- [ ] `README.md` for any new scenario includes all required sections
- [ ] `make list-scenarios` updated if a new scenario was added
- [ ] Scenario runs cleanly on a fresh kind cluster (`make setup-kind`)
- [ ] Cleanup verified: `make cleanup-<scenario>` removes all resources
- [ ] No forbidden vocabulary used (`attack`, `exploit`, `malicious`, `payload`, etc.)

## Testing

<!-- Describe how you tested this change. Include command output if relevant. -->

## Related issues

<!-- Closes #NNN -->
