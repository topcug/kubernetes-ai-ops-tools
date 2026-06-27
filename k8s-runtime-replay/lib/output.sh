#!/usr/bin/env bash
# lib/output.sh — CLI summary output for k8s-runtime-replay
#
# Reads from RESULT_* globals defined in lib/result.sh.
# Human-readable box and optional JSON output are both derived
# from the same result model.

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
# shellcheck source=result.sh
source "$(dirname "${BASH_SOURCE[0]}")/result.sh"

# ── print_summary ─────────────────────────────────────────────────
# Box layout (all measurements in visible characters):
#   border ║ + 2 spaces + label(18) + 2 spaces + value(16) + border ║
#   total visible width per row = 1 + 2 + 18 + 2 + 16 + 1 = 40
#   top/bottom bar = ╔ + 38×═ + ╗  (40 chars total)
print_summary() {
  local ctx="${RESULT_SCENARIO:-unknown}"
  local scenario="${RESULT_SCENARIO:-unknown}"
  ctx="${RESULT_CONTEXT:-unknown}"

  # Plain row: label + plain value, both left-aligned within fixed columns
  _row() {
    printf "║  %-18s  %-16s║\n" "$1" "${2:0:16}"
  }

  # Colored row: label + ANSI-colored short token
  # pad = 16 - visible length of token (so border stays aligned)
  _crow() {
    local label="$1" color="$2" text="$3"
    local pad=$(( 16 - ${#text} ))
    [[ $pad -lt 0 ]] && pad=0
    printf "║  %-18s  " "$label"
    printf "%b%s%b%*s║\n" "$color" "$text" "$RESET" "$pad" ""
  }

  local _c _t

  echo ""
  echo "╔══════════════════════════════════════╗"
  echo "║  scenario summary                    ║"
  echo "╠══════════════════════════════════════╣"
  _row "scenario"          "$scenario"
  _row "context"           "$ctx"
  _crow "deploy"           "$GREEN"  "PASS"

  _c="$GREEN"; _t="PASS"
  [[ "${RESULT_READY:-pass}" != "pass" ]] && { _c="$RED"; _t="FAIL"; }
  _crow "ready" "$_c" "$_t"

  _c="$GREEN"; _t="PASS"
  [[ "${RESULT_TRIGGER:-pass}" != "pass" ]] && { _c="$RED"; _t="FAIL"; }
  _crow "trigger" "$_c" "$_t"

  _c="$GREEN"; _t="PASS"
  [[ "${RESULT_BEHAVIOR:-pass}" != "pass" ]] && { _c="$RED"; _t="FAIL"; }
  _crow "behavior" "$_c" "$_t"

  _row "detection backend" "${RESULT_DETECTION_BACKEND:-none}"

  case "${RESULT_DETECTION:-pending}" in
    pass) _crow "detection" "$GREEN"  "PASS" ;;
    skip) _crow "detection" "$YELLOW" "SKIP" ;;
    *)    _crow "detection" "$YELLOW" "NOT VERIFIED" ;;
  esac

  case "${RESULT_OVERALL:-pending}" in
    scenario_passed_detection_verified) _crow "overall" "$GREEN"  "SCENARIO PASS" ;;
    *)                                  _crow "overall" "$YELLOW" "SCENARIO PASS" ;;
  esac

  echo "╚══════════════════════════════════════╝"
  echo ""
}

# ── print_detail ──────────────────────────────────────────────────
print_detail() {
  local observed="${1:-}"
  local expected_detection="${2:-}"
  local detection_backend="${RESULT_DETECTION_BACKEND:-none}"

  echo "Observed behavior:"
  echo "  - ${observed}"
  echo ""
  echo "Detection expectation:"
  echo "  - alert for ${expected_detection}"
  echo "  - exact rule name depends on local ruleset"
  echo ""

  if [[ "${RESULT_DETECTION:-pending}" != "pass" ]] && \
     [[ "$detection_backend" != "none" ]] && \
     [[ "$detection_backend" != "NOT INSTALLED" ]]; then
    echo "Falco verification:"
    echo "  - no matching alert found after trigger timestamp"
    echo ""
    warn "Falco is running, but no matching alert was found in the current log window."
    warn "This usually means the loaded ruleset, rule conditions, or log match"
    warn "pattern differ from this scenario's expectation."
    echo ""
    echo "  Likely causes (in order of probability):"
    echo "  - installed ruleset does not include a matching rule"
    echo "  - search pattern does not match current Falco output text"
    echo "  - the scenario behavior does not satisfy the rule conditions"
    echo "  - the log inspection window or filter is too narrow"
    echo "  - Falco is running but not capturing this event source"
    echo ""
    info "Next steps:"
    info "  make logs-falco      — filtered Falco alert view"
    info "  make logs-falco-raw  — raw Falco output (format debugging)"
    info "  make list-rules      — attempt to infer loaded rule names (best-effort)"
  fi
}
