# Advanced Usage

## Piping JSON output to jq

```bash
# Extract summary bullets only
kubectl triage pod payment-api -n payments -o json | jq '.summaryBullets[]'

# Check if a NetworkPolicy is missing
kubectl triage pod payment-api -n payments -o json | jq '.network.hasNetworkPolicy'

# Get the triage readout as plain text
kubectl triage pod payment-api -n payments -o json | jq -r '.triageReadout'

# List all recommendations
kubectl triage pod payment-api -n payments -o json | jq '.recommendations[]'

# Show image tags
kubectl triage deployment my-app -n default -o json | jq '.images[] | {container, image, isLatest}'
```

## Using in CI pipelines

kubectl-triage exits with code `2` when risk signals are detected.
Use this to fail a pipeline step or gate a deployment:

```bash
kubectl triage pod $POD_NAME -n $NAMESPACE --quiet
if [ $? -eq 2 ]; then
  echo "Triage flagged risk signals — blocking promotion"
  exit 1
fi
```

## Markdown output for incident docs

Paste a full triage report directly into a GitHub issue, Notion page, or Slack:

```bash
kubectl triage pod crashing-pod -n production -o markdown > triage-report.md
```

## Scripting across multiple pods

```bash
# Triage all pods in a namespace that are not Running
kubectl get pods -n payments --field-selector=status.phase!=Running -o name \
  | sed 's|pod/||' \
  | xargs -I{} kubectl triage pod {} -n payments --quiet
```

## Multiple contexts

```bash
# Triage the same workload in staging vs production
kubectl triage pod payment-api -n payments --context staging
kubectl triage pod payment-api -n payments --context production
```

## Config file

Create `.kubectl-triage.yaml` in your project root or `$HOME`:

```yaml
defaultNamespace: production
outputFormat: table
timeoutSeconds: 15
verbose: false
quiet: false
```

Fields in the config file are used as defaults and can always be overridden by flags.

## Verbose mode

`--verbose` adds two extra sections to the table output:

- **Owner Chain** — shows the full ownership lineage (e.g. `Pod → ReplicaSet → Deployment`)
- **Key Events** — shows all events instead of the top 5

```bash
kubectl triage pod payment-api -n payments --verbose
```

## Quiet mode

`--quiet` suppresses all sections except Summary and Triage Readout.
Useful for dashboards, alerting scripts, or quick checks.

```bash
kubectl triage pod payment-api -n payments --quiet
```
