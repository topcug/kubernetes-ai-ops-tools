.PHONY: help setup-kind setup-falco list-scenarios scenario-run cleanup-run \
	scenario-shell-spawn scenario-sa-token-read scenario-kubectl-exec \
	scenario-curl-egress scenario-secret-enumeration \
	cleanup-shell-spawn cleanup-sa-token-read cleanup-kubectl-exec \
	cleanup-curl-egress cleanup-secret-enumeration \
	cleanup cleanup-all reset \
	logs-falco logs-falco-raw list-rules \
	doctor doctor-falco

SHELL    := /bin/bash
NAMESPACE     ?= k8s-replay
KIND_CLUSTER  ?= k8s-replay
FALCO_NAMESPACE ?= falco
FAST          ?= 0
JSON          ?= 0
DRY_RUN       ?= 0

## ── help ─────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  k8s-runtime-replay"
	@echo "  Safe, repeatable Kubernetes runtime scenarios for detection demos and workshops."
	@echo ""
	@echo "  Setup"
	@echo "    make setup-kind            Create a local kind cluster"
	@echo "    make setup-falco           Install Falco via Helm"
	@echo ""
	@echo "  Health checks"
	@echo "    make doctor                Check cluster, kubectl, namespace, and optional backends"
	@echo "    make doctor-falco          Check Falco pod status and event source"
	@echo ""
	@echo "  Scenarios"
	@echo "    make list-scenarios        Show all available scenarios"
	@echo "    make scenario-<name>       Run a scenario (default: clean state)"
	@echo "    make scenario-<name> FAST=1  Reuse existing pod instead of recreating"
	@echo "    make scenario-<name> JSON=1  Output result as JSON"
	@echo ""
	@echo "    make scenario-shell-spawn"
	@echo "    make scenario-sa-token-read"
	@echo "    make scenario-kubectl-exec"
	@echo "    make scenario-curl-egress"
	@echo "    make scenario-secret-enumeration"
	@echo ""
	@echo "  Cleanup"
	@echo "    make cleanup-<scenario>    Remove a specific scenario's workload"
	@echo "    make cleanup               Remove the k8s-replay namespace"
	@echo "    make cleanup-all           Remove namespace and all scenario resources"
	@echo "    make reset                 Full teardown including kind cluster"
	@echo ""
	@echo "  Utilities"
	@echo "    make logs-falco            Filtered Falco alert view"
	@echo "    make logs-falco-raw        Raw recent Falco output (format debugging)"
	@echo "    make list-rules            Attempt to infer loaded rule names (best-effort)"
	@echo ""
	@echo "  Exit codes"
	@echo "    0   scenario passed, detection verified"
	@echo "    10  scenario passed, detection skipped (no backend)"
	@echo "    11  scenario passed, detection not verified"
	@echo "    20  preflight failed"
	@echo "    21  deploy failed"
	@echo "    22  readiness timeout"
	@echo "    23  trigger failed"
	@echo "    24  behavior not observed"
	@echo ""

## ── setup ────────────────────────────────────────────────────────
setup-kind:
	@command -v kind >/dev/null 2>&1 || { echo "[error] kind not found — see docs/local-cluster.md"; exit 1; }
	@if kind get clusters 2>/dev/null | grep -q "^$(KIND_CLUSTER)$$"; then \
		echo "[ok] kind cluster '$(KIND_CLUSTER)' already exists"; \
	else \
		echo "[info] Creating kind cluster: $(KIND_CLUSTER)"; \
		kind create cluster --name $(KIND_CLUSTER); \
	fi
	@kubectl cluster-info --context kind-$(KIND_CLUSTER)

setup-falco:
	@command -v helm >/dev/null 2>&1 || { echo "[error] helm not found — install from https://helm.sh"; exit 1; }
	@helm repo add falcosecurity https://falcosecurity.github.io/charts 2>/dev/null || true
	@helm repo update
	@helm upgrade --install falco falcosecurity/falco \
		--namespace $(FALCO_NAMESPACE) \
		--create-namespace \
		--set tty=true \
		--set driver.kind=modern_ebpf \
		--set falcosidekick.enabled=false \
		--set auditLog.enabled=false
	@echo "[info] Falco install triggered. Waiting for pod to be ready..."
	@kubectl rollout status daemonset/falco -n $(FALCO_NAMESPACE) --timeout=180s || \
		kubectl get pods -n $(FALCO_NAMESPACE)
	@echo "[ok] Falco ready. Stream logs with: make logs-falco"

## ── doctor ───────────────────────────────────────────────────────
doctor:
	@echo ""
	@echo "  k8s-runtime-replay — environment check"
	@echo ""
	@command -v kubectl >/dev/null 2>&1 && echo "  [ok] kubectl found" || echo "  [error] kubectl not found"
	@kubectl cluster-info >/dev/null 2>&1 && echo "  [ok] cluster reachable" || echo "  [error] cluster not reachable — check KUBECONFIG"
	@CTX=$$(kubectl config current-context 2>/dev/null || echo "none"); echo "  [info] current context: $$CTX"
	@kubectl get namespace $(NAMESPACE) >/dev/null 2>&1 \
		&& echo "  [ok] namespace $(NAMESPACE) exists" \
		|| echo "  [warn] namespace $(NAMESPACE) not found — will be created on first scenario run"
	@POD=$$(kubectl get pods -n $(FALCO_NAMESPACE) \
		--selector=app.kubernetes.io/name=falco \
		--field-selector=status.phase=Running \
		-o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -n "$$POD" ]; then \
		echo "  [ok] Falco running: $$POD"; \
	else \
		echo "  [warn] Falco not running — detection verification will be skipped"; \
		echo "         run: make setup-falco"; \
	fi
	@echo ""

doctor-falco:
	@echo ""
	@echo "  k8s-runtime-replay — Falco health check"
	@echo ""
	@POD=$$(kubectl get pods -n $(FALCO_NAMESPACE) \
		--selector=app.kubernetes.io/name=falco \
		--field-selector=status.phase=Running \
		-o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -z "$$POD" ]; then \
		echo "  [error] No running Falco pod found in namespace $(FALCO_NAMESPACE)"; \
		echo "          run: make setup-falco"; \
		exit 1; \
	fi; \
	echo "  [ok] Falco pod: $$POD"; \
	echo ""; \
	echo "  Event sources:"; \
	kubectl logs -n $(FALCO_NAMESPACE) "$$POD" --tail=100 2>/dev/null \
		| grep -i "event source\|syscall\|ebpf\|kmod\|modern_ebpf" \
		| sed 's/^/    /' \
		|| echo "    (no event source lines found in recent logs)"; \
	echo ""; \
	echo "  Recent startup lines:"; \
	kubectl logs -n $(FALCO_NAMESPACE) "$$POD" --tail=20 2>/dev/null | sed 's/^/    /'; \
	echo ""

## ── list ─────────────────────────────────────────────────────────
list-scenarios:
	@echo ""
	@echo "  Available scenarios:"
	@echo ""
	@printf "  %-28s %-52s %s\n" "SCENARIO" "GOAL" "VERSION"
	@printf "  %-28s %-52s %s\n" "--------" "----" "-------"
	@for dir in scenarios/*/; do \
		yaml="$$dir/scenario.yaml"; \
		[ -f "$$yaml" ] || continue; \
		id=$$(grep '^id:' "$$yaml" | head -1 | sed 's/id: *//'); \
		goal=$$(grep '^goal:' "$$yaml" | head -1 | sed 's/goal: *//'); \
		ver=$$(grep '^version:' "$$yaml" | head -1 | sed 's/version: *//;s/"//g'); \
		printf "  %-28s %-52s %s\n" "$$id" "$$goal" "$${ver:-—}"; \
	done
	@echo ""

## ── generic scenario run (NAME=<scenario-id>) ────────────────────
scenario-run:
	@[ -n "$(NAME)" ] || { echo "[error] Usage: make scenario-run NAME=<scenario-id>"; exit 1; }
	@[ -d "scenarios/$(NAME)" ] || { echo "[error] Scenario not found: $(NAME)"; echo "Run 'make list-scenarios' to see available scenarios."; exit 1; }
	@FAST=$(FAST) JSON=$(JSON) DRY_RUN=$(DRY_RUN) bash scenarios/$(NAME)/trigger.sh; \
	 code=$$?; [ $$code -le 11 ] && exit 0 || exit $$code

cleanup-run:
	@[ -n "$(NAME)" ] || { echo "[error] Usage: make cleanup-run NAME=<scenario-id>"; exit 1; }
	@[ -f "scenarios/$(NAME)/cleanup.sh" ] || { echo "[error] Scenario not found: $(NAME)"; exit 1; }
	@bash scenarios/$(NAME)/cleanup.sh

## ── scenarios ────────────────────────────────────────────────────
# Exit codes 10 and 11 mean scenario passed — detection skipped or not verified.
# These are not failures. Use || true so make does not treat them as errors.
scenario-shell-spawn:
	@FAST=$(FAST) JSON=$(JSON) DRY_RUN=$(DRY_RUN) bash scenarios/shell-spawn/trigger.sh; \
	 code=$$?; [ $$code -le 11 ] && exit 0 || exit $$code

scenario-sa-token-read:
	@FAST=$(FAST) JSON=$(JSON) DRY_RUN=$(DRY_RUN) bash scenarios/sa-token-read/trigger.sh; \
	 code=$$?; [ $$code -le 11 ] && exit 0 || exit $$code

scenario-kubectl-exec:
	@FAST=$(FAST) JSON=$(JSON) DRY_RUN=$(DRY_RUN) bash scenarios/kubectl-exec/trigger.sh; \
	 code=$$?; [ $$code -le 11 ] && exit 0 || exit $$code

scenario-curl-egress:
	@FAST=$(FAST) JSON=$(JSON) DRY_RUN=$(DRY_RUN) bash scenarios/curl-egress/trigger.sh; \
	 code=$$?; [ $$code -le 11 ] && exit 0 || exit $$code

scenario-secret-enumeration:
	@FAST=$(FAST) JSON=$(JSON) DRY_RUN=$(DRY_RUN) bash scenarios/secret-enumeration/trigger.sh; \
	 code=$$?; [ $$code -le 11 ] && exit 0 || exit $$code

## ── cleanup ──────────────────────────────────────────────────────
cleanup-shell-spawn:
	@bash scenarios/shell-spawn/cleanup.sh

cleanup-sa-token-read:
	@bash scenarios/sa-token-read/cleanup.sh

cleanup-kubectl-exec:
	@bash scenarios/kubectl-exec/cleanup.sh

cleanup-curl-egress:
	@bash scenarios/curl-egress/cleanup.sh

cleanup-secret-enumeration:
	@bash scenarios/secret-enumeration/cleanup.sh

cleanup:
	@echo "[info] Deleting namespace: $(NAMESPACE)"
	@kubectl delete namespace $(NAMESPACE) --ignore-not-found
	@echo "[ok] Namespace $(NAMESPACE) removed."

cleanup-all: cleanup

reset: cleanup
	@if kind get clusters 2>/dev/null | grep -q "^$(KIND_CLUSTER)$$"; then \
		echo "[info] Deleting kind cluster: $(KIND_CLUSTER)"; \
		kind delete cluster --name $(KIND_CLUSTER); \
	else \
		echo "[info] No kind cluster named $(KIND_CLUSTER) found."; \
	fi
	@echo "[ok] Full reset complete."

## ── utilities ────────────────────────────────────────────────────
logs-falco:
	@POD=$$(kubectl get pods -n $(FALCO_NAMESPACE) \
		--selector=app.kubernetes.io/name=falco \
		--field-selector=status.phase=Running \
		-o jsonpath='{.items[0].metadata.name}' 2>/dev/null) && \
	if [ -z "$$POD" ]; then \
		echo "[warn] No running Falco pod found in namespace $(FALCO_NAMESPACE)"; \
	else \
		echo "[info] Searching recent Falco logs for alerts and rule hits..."; \
		RESULT=$$(kubectl logs -n $(FALCO_NAMESPACE) "$$POD" --tail=200 2>/dev/null \
			| grep -i "Warning\|Error\|Critical" || true); \
		if [ -z "$$RESULT" ]; then \
			echo "[warn] No alert entries matched the current filter."; \
			echo "[info] Showing raw tail may help confirm output format: make logs-falco-raw"; \
		else \
			echo "$$RESULT"; \
		fi \
	fi

logs-falco-raw:
	@POD=$$(kubectl get pods -n $(FALCO_NAMESPACE) \
		--selector=app.kubernetes.io/name=falco \
		--field-selector=status.phase=Running \
		-o jsonpath='{.items[0].metadata.name}' 2>/dev/null) && \
	if [ -z "$$POD" ]; then \
		echo "[warn] No running Falco pod found in namespace $(FALCO_NAMESPACE)"; \
	else \
		echo "[info] Raw Falco logs (last 200 lines) from $$POD..."; \
		kubectl logs -n $(FALCO_NAMESPACE) "$$POD" --tail=200 2>/dev/null; \
	fi

list-rules:
	@POD=$$(kubectl get pods -n $(FALCO_NAMESPACE) \
		--selector=app.kubernetes.io/name=falco \
		--field-selector=status.phase=Running \
		-o jsonpath='{.items[0].metadata.name}' 2>/dev/null) && \
	if [ -z "$$POD" ]; then \
		echo "[warn] No running Falco pod found"; \
	else \
		echo "[info] Attempting to infer loaded rule names from Falco startup logs..."; \
		RESULT=$$(kubectl logs -n $(FALCO_NAMESPACE) "$$POD" --tail=1000 2>/dev/null \
			| grep -i "^.*loading rule[^s]" \
			| sed 's/.*[Ll]oading rule[[:space:]]*/  - /' || true); \
		RULEFILES=$$(kubectl logs -n $(FALCO_NAMESPACE) "$$POD" --tail=1000 2>/dev/null \
			| grep -i "Loading rules from:" | sed 's/.*Loading rules from:/  rulefile:/' || true); \
		if [ -n "$$RULEFILES" ]; then \
			echo "$$RULEFILES"; \
		fi; \
		if [ -z "$$RESULT" ]; then \
			echo "[warn] Could not infer individual rule names from startup logs"; \
			echo "[info] This is expected — Falco does not log individual rule names at startup by default"; \
			echo "[info] To see which rules are active, inspect the ruleset file directly:"; \
			echo "[info]   kubectl exec -n $(FALCO_NAMESPACE) $$POD -- grep '^\- rule:' /etc/falco/falco_rules.yaml 2>/dev/null | head -30"; \
		else \
			echo "$$RESULT"; \
		fi \
	fi
