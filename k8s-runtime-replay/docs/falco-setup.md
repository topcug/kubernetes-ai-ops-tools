# Falco setup

Falco is optional — all scenarios run without it. But if you want to see runtime rule hits, this guide gets you there in minutes.

## Install Falco with Helm

```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm repo update

helm install falco falcosecurity/falco \
  --namespace falco \
  --create-namespace \
  --set tty=true
```

Wait for Falco to be ready:

```bash
kubectl rollout status daemonset/falco -n falco --timeout=120s
```

## Verify Falco is running

```bash
kubectl get pods -n falco
```

## View Falco output

Stream live alerts:

```bash
kubectl logs -n falco -l app.kubernetes.io/name=falco -f
```

Or use the Makefile shortcut:

```bash
make logs-falco
```

## Test Falco is detecting

After running any scenario, check for rule hits:

```bash
kubectl logs -n falco -l app.kubernetes.io/name=falco --tail=50 | grep -i "Warning\|Error\|Critical"
```

## Uninstall

```bash
helm uninstall falco -n falco
kubectl delete namespace falco
```

## Notes

- Falco requires access to the kernel — ensure your cluster nodes allow this.
- For kind clusters, Falco works best with the `--set driver.kind=modern_ebpf` option on Linux.
- See [Falco documentation](https://falco.org/docs/) for advanced configuration.
