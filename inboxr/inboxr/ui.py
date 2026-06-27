"""Generate a self-contained interactive HTML dashboard from an EvalResult dict."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# HTML template — __DATA_JSON__ is replaced at render time with a single
# JSON blob containing everything the JS needs.
# ---------------------------------------------------------------------------

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Inboxr — Eval Report</title>
<link href="https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600&family=Geist:wght@400;500;600;700&display=swap" rel="stylesheet" />
<style>
  :root {
    --bg:#0a0c0f;--surface:#111318;--surface2:#161b22;--border:#1e2530;--border2:#252d3a;
    --green:#00e5a0;--green-dim:#00e5a015;--red:#ff4d6d;--red-dim:#ff4d6d15;
    --amber:#ffb830;--amber-dim:#ffb83015;--blue:#4da6ff;--blue-dim:#4da6ff12;
    --muted:#4a5568;--text:#c9d1d9;--text-bright:#e6edf3;--text-dim:#8b949e;
    --font-mono:'Geist Mono','Fira Code',monospace;
    --font-display:'Geist',system-ui,sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--text);font-family:var(--font-mono);font-size:13.5px;min-height:100vh;overflow:hidden;}
  .hidden{display:none!important;}

  /* TOPBAR */
  .topbar{display:flex;align-items:center;gap:16px;padding:13px 24px;background:var(--surface);border-bottom:1px solid var(--border);}
  .logo{font-family:var(--font-display);font-weight:700;font-size:17px;color:var(--text-bright);letter-spacing:-0.5px;flex-shrink:0;}
  .logo span{color:var(--green);}
  .meta-chips{display:flex;gap:8px;flex-wrap:wrap;flex:1;}
  .chip{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:5px;font-size:12px;font-weight:600;background:var(--surface2);border:1px solid var(--border2);color:var(--text-dim);white-space:nowrap;}
  .chip .dot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  .chip.live{border-color:var(--green);color:var(--green);background:var(--green-dim);}
  .chip.scenario{color:var(--blue);border-color:var(--blue);background:var(--blue-dim);}
  .chip.agent{color:var(--amber);border-color:var(--amber);background:var(--amber-dim);}

  /* LAYOUT */
  .layout{display:grid;grid-template-columns:380px 1fr;height:calc(100vh - 51px);}

  /* INBOX */
  .panel-inbox{background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;}
  .panel-header{padding:14px 18px 10px;border-bottom:1px solid var(--border);display:flex;align-items:baseline;gap:8px;flex-shrink:0;}
  .panel-title{font-family:var(--font-display);font-weight:600;font-size:13px;color:var(--text-bright);letter-spacing:.4px;text-transform:uppercase;}
  .panel-count{font-size:12px;color:var(--text-dim);}
  .inbox-list{overflow-y:auto;flex:1;}
  .inbox-list::-webkit-scrollbar,.log-body::-webkit-scrollbar,.payload-content::-webkit-scrollbar,.email-viewer::-webkit-scrollbar{width:4px;}
  .inbox-list::-webkit-scrollbar-thumb,.log-body::-webkit-scrollbar-thumb,.payload-content::-webkit-scrollbar-thumb,.email-viewer::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px;}
  .email-row{padding:10px 18px;cursor:pointer;transition:background .1s;border-left:2px solid transparent;animation:fadeIn .3s ease both;user-select:none;}
  @keyframes fadeIn{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:translateX(0)}}
  .email-row:hover{background:var(--surface2);}
  .email-row.accessed{border-left-color:var(--green);}
  .email-row.selected{background:var(--blue-dim)!important;border-left-color:var(--blue);}
  .email-row-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;}
  .email-from{font-size:13px;font-weight:600;color:var(--text-bright);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px;}
  .email-time{font-size:12px;color:var(--text-dim);flex-shrink:0;}
  .email-subject{font-size:12.5px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:4px;}
  .email-labels{display:flex;gap:4px;flex-wrap:wrap;}
  .label{font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;letter-spacing:.3px;}
  .label-IMPORTANT{background:var(--amber-dim);color:var(--amber);border:1px solid var(--amber);}
  .label-STARRED{background:#ffd70015;color:#ffd700;border:1px solid #ffd700;}
  .label-SUSPICIOUS{background:var(--red-dim);color:var(--red);border:1px solid var(--red);}
  .label-AUTOMATED{background:#8b5cf615;color:#8b5cf6;border:1px solid #8b5cf6;}
  .label-default{background:var(--surface2);color:var(--text-dim);border:1px solid var(--border2);}
  .unread-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--blue);margin-right:5px;vertical-align:middle;}

  /* RIGHT */
  .panel-right{display:flex;flex-direction:column;overflow:hidden;background:var(--bg);}
  .tab-bar{display:flex;align-items:stretch;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0;}
  .tab{padding:13px 20px;font-size:12px;font-weight:600;font-family:var(--font-display);color:var(--text-dim);cursor:pointer;border-bottom:2px solid transparent;transition:color .15s,border-color .15s;user-select:none;}
  .tab:hover{color:var(--text);}
  .tab.active{color:var(--text-bright);border-bottom-color:var(--blue);}
  .tab-badge{background:var(--blue-dim);color:var(--blue);border:1px solid var(--blue);border-radius:10px;font-size:10px;padding:0 6px;margin-left:6px;}
  .tab-spacer{flex:1;}
  .view{display:flex;flex-direction:column;flex:1;overflow:hidden;}

  /* LOG */
  .log-cols{display:grid;grid-template-columns:100px 52px 170px 58px 1fr 18px;gap:0 12px;padding:7px 20px;font-size:11px;font-weight:700;color:var(--text-dim);letter-spacing:.7px;text-transform:uppercase;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0;}
  .log-body{overflow-y:auto;flex:1;padding:2px 0;}
  .step-divider{display:flex;align-items:center;justify-content:space-between;padding:5px 20px 4px;font-size:10.5px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);background:#111318ee;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10;cursor:pointer;user-select:none;transition:color .1s,background .1s;}
  .step-divider:hover{background:var(--surface2);color:var(--text-dim);}
  .step-collapse-icon{font-size:10px;transition:transform .2s;}
  .step-divider.collapsed .step-collapse-icon{transform:rotate(-90deg);}
  .log-row{display:grid;grid-template-columns:100px 52px 170px 58px 1fr 18px;gap:0 12px;padding:6px 20px;border-bottom:1px solid #1e253033;align-items:start;cursor:pointer;transition:background .1s;animation:slideIn .2s ease both;}
  .log-row:hover{background:var(--surface2);}
  .log-row.expanded{background:var(--surface2);}
  @keyframes slideIn{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}
  .log-time{color:var(--green);font-size:12px;font-weight:500;}
  .log-level{font-size:11px;color:var(--text-dim);}
  .log-tool{font-size:12.5px;font-weight:600;color:var(--blue);}
  .log-status{font-size:12px;}
  .status-ok{color:var(--green);}
  .status-err{color:var(--red);}
  .log-details{font-size:12px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .expand-icon{font-size:10px;color:var(--muted);transition:transform .2s;padding-top:2px;}
  .log-row.expanded .expand-icon{transform:rotate(90deg);color:var(--blue);}
  .log-payload{display:none;margin:0 20px 8px;border:1px solid var(--border2);border-radius:6px;overflow:hidden;background:var(--bg);}
  .log-payload.open{display:block;}
  .payload-tabs{display:flex;border-bottom:1px solid var(--border2);}
  .payload-tab{padding:6px 14px;font-size:11px;font-weight:600;color:var(--text-dim);cursor:pointer;border-bottom:2px solid transparent;user-select:none;}
  .payload-tab.active{color:var(--blue);border-bottom-color:var(--blue);}
  .payload-content{padding:10px 14px;font-size:11.5px;line-height:1.6;max-height:200px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;}
  .json-key{color:var(--blue);}
  .json-str{color:var(--green);}
  .json-num{color:var(--amber);}
  .json-bool{color:#c084fc;}
  .json-null{color:var(--text-dim);}

  /* EMAIL VIEWER */
  .email-viewer-wrap{flex:1;overflow:hidden;display:flex;flex-direction:column;}
  .email-viewer-empty{flex:1;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:13px;}
  .email-viewer{flex:1;overflow-y:auto;padding:28px 32px;}
  .email-accessed-banner{display:flex;align-items:center;gap:8px;padding:8px 14px;background:var(--green-dim);border:1px solid var(--green);border-radius:6px;margin-bottom:20px;font-size:12px;color:var(--green);}
  .email-meta{margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--border);}
  .email-meta-subject{font-family:var(--font-display);font-size:18px;font-weight:700;color:var(--text-bright);margin-bottom:12px;line-height:1.3;}
  .email-meta-row{display:flex;gap:8px;margin-bottom:5px;font-size:12.5px;}
  .email-meta-label{color:var(--text-dim);flex-shrink:0;width:44px;}
  .email-meta-value{color:var(--text);}
  .email-labels-row{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap;}
  .email-body{font-size:13.5px;line-height:1.8;color:var(--text);white-space:pre-wrap;}

  /* SCORE BAR */
  .score-bar{padding:13px 20px;background:var(--surface);border-top:1px solid var(--border);flex-shrink:0;}
  .score-bar-top{display:flex;align-items:center;gap:18px;flex-wrap:wrap;}
  .score-badge{display:flex;align-items:center;gap:10px;flex-shrink:0;}
  .score-icon{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;}
  .score-icon.pass{background:var(--green-dim);border:1.5px solid var(--green);}
  .score-icon.fail{background:var(--red-dim);border:1.5px solid var(--red);}
  .score-text{font-family:var(--font-display);font-size:19px;font-weight:700;}
  .score-text.pass{color:var(--green);}
  .score-text.fail{color:var(--red);}
  .criteria-list{display:flex;gap:6px;flex-wrap:wrap;flex:1;}
  .criterion{display:inline-flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;padding:4px 9px;border-radius:5px;border:1px solid transparent;transition:background .1s,border-color .1s;user-select:none;position:relative;}
  .criterion:hover{background:var(--surface2);border-color:var(--border2);}
  .criterion.pass{color:var(--text);}
  .criterion.fail{color:var(--text-dim);}
  .criterion .ck{font-size:12px;flex-shrink:0;}
  .criterion.pass .ck{color:var(--green);}
  .criterion.fail .ck{color:var(--red);}
  .criterion-tooltip{display:none;position:absolute;bottom:calc(100% + 8px);left:0;background:var(--surface2);border:1px solid var(--border2);border-radius:6px;padding:8px 12px;font-size:11.5px;color:var(--text-dim);line-height:1.5;width:300px;z-index:50;white-space:normal;box-shadow:0 4px 16px #00000066;}
  .criterion.open .criterion-tooltip{display:block;}
  .final-answer-chip{font-size:12px;color:var(--text-dim);padding:5px 12px;background:var(--surface2);border:1px solid var(--border2);border-radius:5px;flex-shrink:0;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .final-answer-chip strong{color:var(--muted);font-size:10px;letter-spacing:.7px;text-transform:uppercase;display:block;margin-bottom:2px;}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo">inbox<span>r</span></div>
  <div class="meta-chips">
    <div class="chip live"><span class="dot"></span>LIVE</div>
    <div class="chip scenario">SCENARIO &nbsp;__TEMPLATE__</div>
    <div class="chip agent">AGENT &nbsp;__AGENT__</div>
    <div class="chip">STEPS &nbsp;__STEPS__</div>
    <div class="chip">SEED &nbsp;__SEED__</div>
  </div>
</div>

<div class="layout">
  <div class="panel-inbox">
    <div class="panel-header">
      <span class="panel-title">Inbox</span>
      <span class="panel-count" id="inbox-count"></span>
    </div>
    <div class="inbox-list" id="inbox-list"></div>
  </div>

  <div class="panel-right">
    <div class="tab-bar">
      <div class="tab active" id="tab-log" onclick="switchTab('log')">Tool Call Log</div>
      <div class="tab" id="tab-email" onclick="switchTab('email')">
        Email Viewer <span class="tab-badge" id="email-badge">—</span>
      </div>
      <div class="tab-spacer"></div>
      <div class="chip live" style="align-self:center;margin-right:16px"><span class="dot"></span>LIVE</div>
    </div>

    <div class="view" id="view-log">
      <div class="log-cols">
        <span>TIME</span><span>LEVEL</span><span>TOOL</span><span>STATUS</span><span>DETAILS</span><span></span>
      </div>
      <div class="log-body" id="log-body"></div>
    </div>

    <div class="view hidden" id="view-email">
      <div class="email-viewer-wrap">
        <div class="email-viewer-empty" id="email-empty">← select an email from the inbox</div>
        <div class="email-viewer hidden" id="email-content"></div>
      </div>
    </div>

    <div class="score-bar">
      <div class="score-bar-top">
        <div class="score-badge">
          <div class="score-icon __SCORE_CLS__" id="score-icon">__SCORE_ICON__</div>
          <div class="score-text __SCORE_CLS__" id="score-text">Score: __SCORE_DISPLAY__</div>
        </div>
        <div class="criteria-list" id="criteria-list"></div>
        <div class="final-answer-chip">
          <strong>Final Answer</strong>
          <span id="final-answer-text"></span>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
// ── INJECTED DATA ────────────────────────────────────────────────────────────
const DATA = __DATA_JSON__;

// ── HELPERS ──────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function labelHtml(l) {
  const known = ['IMPORTANT','STARRED','SUSPICIOUS','AUTOMATED'];
  const cls = known.includes(l) ? 'label-' + l : 'label-default';
  return `<span class="label ${cls}">${esc(l)}</span>`;
}

function highlight(obj) {
  return JSON.stringify(obj, null, 2)
    .replace(/("(?:[^"\\\\]|\\\\.)*"(?=\\s*:))|("(?:[^"\\\\]|\\\\.)*")|(true|false)|(null)|(-?\\d+(?:\\.\\d+)?)/g,
      (m, key, str, bool, nil, num) => {
        if (key) return `<span class="json-key">${m}</span>`;
        if (str) return `<span class="json-str">${m}</span>`;
        if (bool) return `<span class="json-bool">${m}</span>`;
        if (nil)  return `<span class="json-null">${m}</span>`;
        if (num)  return `<span class="json-num">${m}</span>`;
        return m;
      });
}

// ── INBOX ─────────────────────────────────────────────────────────────────────
document.getElementById('inbox-count').textContent = DATA.emails.length + ' threads';
const inboxEl = document.getElementById('inbox-list');

DATA.emails.forEach((e, i) => {
  const d = document.createElement('div');
  d.className = 'email-row' + (e.accessed ? ' accessed' : '');
  d.id = 'row-' + e.id;
  d.style.animationDelay = (i * 20) + 'ms';
  d.innerHTML = `
    <div class="email-row-top">
      <span class="email-from">${e.unread ? '<span class="unread-dot"></span>' : ''}${esc(e.from)}</span>
      <span class="email-time">${esc(e.time)}</span>
    </div>
    <div class="email-subject">${esc(e.subject)}</div>
    <div class="email-labels">${(e.labels||[]).map(labelHtml).join('')}</div>`;
  d.addEventListener('click', () => openEmail(e, d));
  inboxEl.appendChild(d);
});

// ── LOG ───────────────────────────────────────────────────────────────────────
const logBody = document.getElementById('log-body');
let rowIdx = 0;

DATA.steps.forEach((step, si) => {
  const divider = document.createElement('div');
  divider.className = 'step-divider';
  divider.innerHTML = `<span>${esc(step.label)}</span><span class="step-collapse-icon">▾</span>`;
  divider.addEventListener('click', () => {
    divider.classList.toggle('collapsed');
    const col = divider.classList.contains('collapsed');
    logBody.querySelectorAll('.step-group-' + si).forEach(el => {
      el.style.display = col ? 'none' : '';
    });
  });
  logBody.appendChild(divider);

  step.rows.forEach((row, rj) => {
    const wrap = document.createElement('div');
    wrap.className = 'step-group-' + si;

    const rowEl = document.createElement('div');
    rowEl.className = 'log-row';
    rowEl.style.animationDelay = (rowIdx++ * 35) + 'ms';
    rowEl.innerHTML = `
      <span class="log-time">${esc(row.time)}</span>
      <span class="log-level">${esc(row.level)}</span>
      <span class="log-tool">${esc(row.tool)}</span>
      <span class="log-status status-${row.ok ? 'ok' : 'err'}">${row.ok ? '✓ OK' : '✗ ERR'}</span>
      <span class="log-details">${esc(row.details)}</span>
      <span class="expand-icon">▶</span>`;

    const inId = 'in-' + si + '-' + rj;
    const outId = 'out-' + si + '-' + rj;
    const payload = document.createElement('div');
    payload.className = 'log-payload';
    payload.innerHTML = `
      <div class="payload-tabs">
        <div class="payload-tab active" data-target="${inId}">Input</div>
        <div class="payload-tab" data-target="${outId}">Output</div>
      </div>
      <div class="payload-content" id="${inId}">${highlight(row.input)}</div>
      <div class="payload-content hidden" id="${outId}">${highlight(row.output)}</div>`;

    payload.querySelectorAll('.payload-tab').forEach(tab => {
      tab.addEventListener('click', e => {
        e.stopPropagation();
        payload.querySelectorAll('.payload-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        payload.querySelectorAll('.payload-content').forEach(c => c.classList.add('hidden'));
        document.getElementById(tab.dataset.target).classList.remove('hidden');
      });
    });

    rowEl.addEventListener('click', () => {
      const open = rowEl.classList.toggle('expanded');
      payload.classList.toggle('open', open);
    });

    wrap.appendChild(rowEl);
    wrap.appendChild(payload);
    logBody.appendChild(wrap);
  });
});

setTimeout(() => { logBody.scrollTop = logBody.scrollHeight; }, 600);

// ── CRITERIA ──────────────────────────────────────────────────────────────────
document.getElementById('final-answer-text').textContent = DATA.final_answer || '';
const criteriaEl = document.getElementById('criteria-list');
DATA.criteria.forEach(c => {
  const el = document.createElement('div');
  el.className = 'criterion ' + (c.passed ? 'pass' : 'fail');
  el.innerHTML = `<span class="ck">${c.passed ? '✓' : '✗'}</span>${esc(c.text)}<div class="criterion-tooltip">${esc(c.justification)}</div>`;
  el.addEventListener('click', () => el.classList.toggle('open'));
  criteriaEl.appendChild(el);
});
document.addEventListener('click', e => {
  if (!e.target.closest('.criterion')) {
    document.querySelectorAll('.criterion.open').forEach(el => el.classList.remove('open'));
  }
});

// ── EMAIL VIEWER ──────────────────────────────────────────────────────────────
let activeRow = null;
function openEmail(email, rowEl) {
  if (activeRow) activeRow.classList.remove('selected');
  rowEl.classList.add('selected');
  activeRow = rowEl;
  document.getElementById('email-badge').textContent = email.from.split(' ')[0];
  switchTab('email');
  document.getElementById('email-empty').classList.add('hidden');
  const content = document.getElementById('email-content');
  content.classList.remove('hidden');
  content.innerHTML = `
    ${email.accessed ? '<div class="email-accessed-banner">✓ &nbsp;Agent read this email during eval</div>' : ''}
    <div class="email-meta">
      <div class="email-meta-subject">${esc(email.subject)}</div>
      <div class="email-meta-row"><span class="email-meta-label">From</span><span class="email-meta-value">${esc(email.from)} &lt;${esc(email.addr)}&gt;</span></div>
      <div class="email-meta-row"><span class="email-meta-label">Time</span><span class="email-meta-value">${esc(email.time)}</span></div>
      ${(email.labels||[]).length ? `<div class="email-labels-row">${email.labels.map(labelHtml).join('')}</div>` : ''}
    </div>
    <div class="email-body">${esc(email.body)}</div>`;
}

// ── TABS ──────────────────────────────────────────────────────────────────────
function switchTab(name) {
  ['log','email'].forEach(t => {
    document.getElementById('tab-' + t).classList.toggle('active', t === name);
    document.getElementById('view-' + t).classList.toggle('hidden', t !== name);
  });
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------


def _format_time(ts: str) -> str:
    try:
        return ts[11:16]
    except Exception:
        return ts[:5] if ts else ""


def _tool_detail(tool: str, args: dict[str, Any], result: dict[str, Any]) -> str:
    if "error" in result:
        return result["error"][:80]
    if tool == "read_email":
        return f"Read email ID: {args.get('thread_id', '')}"
    if tool in ("list_emails", "search_emails"):
        count = result.get("count", len(result.get("threads", [])))
        label = args.get("label", "")
        return f"Listed {count} threads" + (f" ({label})" if label else "")
    if tool in ("list_calendar", "find_free_slots"):
        items = result.get("events", result.get("slots", []))
        return f"Retrieved {len(items)} events"
    if tool in ("list_slack_channels", "list_slack_mentions"):
        items = result.get("channels", result.get("mentions", []))
        return f"Retrieved {len(items)} items"
    if tool == "read_slack_channel":
        return f"Read #{args.get('channel', '')}"
    if tool in ("draft_email_reply", "draft_message"):
        to = args.get("to", args.get("thread_id", ""))
        return f"Drafted reply to: {to}"
    if tool == "search_drive":
        return f"Drive search: {result.get('count', '?')} results"
    if tool == "final_answer":
        ans = result.get("final_answer", "")
        return str(ans)[:80] if ans else "Done."
    return (json.dumps(args) or "")[:80]


def _build_data(result: dict[str, Any]) -> dict[str, Any]:
    trajectory = result.get("trajectory", [])
    workspace = result.get("_workspace", {})
    threads = workspace.get("gmail", {}).get("threads", []) if workspace else []

    # emails accessed by agent
    accessed: set[str] = set()
    for step in trajectory:
        for tc in step.get("tool_calls", []):
            tid = (tc.get("arguments") or {}).get("thread_id")
            if tid:
                accessed.add(tid)

    # build email list from workspace threads
    emails = []
    for t in threads[:40]:
        msgs = t.get("messages") or [{}]
        first = msgs[0]
        sender_full = first.get("from", "Unknown")
        sender = (
            sender_full.split("@")[0].replace(".", " ").title()
            if "@" in sender_full
            else sender_full
        )
        body_parts = []
        for m in msgs:
            body_parts.append(m.get("body", ""))
        body = "\n\n---\n\n".join(b for b in body_parts if b)

        emails.append(
            {
                "id": t.get("id", ""),
                "from": sender,
                "addr": sender_full,
                "time": _format_time(first.get("timestamp", "")),
                "subject": t.get("subject", "(no subject)"),
                "labels": t.get("labels", []),
                "unread": bool(t.get("unread")),
                "accessed": t.get("id") in accessed,
                "body": body or "(no content)",
            }
        )

    # build steps from trajectory
    steps = []
    base_ms = 0.0
    for step in trajectory:
        label = f"Step {step.get('step', 0)} — {(step.get('thought') or '')[:70]}"
        rows = []
        tool_calls = step.get("tool_calls") or []
        tool_results = step.get("tool_results") or []

        if not tool_calls and step.get("final_answer"):
            rows.append(
                {
                    "time": f"{base_ms:010.3f}",
                    "level": "INFO",
                    "tool": "final_answer",
                    "ok": True,
                    "details": (step.get("final_answer") or "")[:80],
                    "input": {},
                    "output": {"final_answer": step.get("final_answer")},
                }
            )
            base_ms += 50
        else:
            for i, tc in enumerate(tool_calls):
                tool_name = tc.get("name", "unknown")
                args = tc.get("arguments") or {}
                res = tool_results[i] if i < len(tool_results) else {}
                details = _tool_detail(tool_name, args, res)
                rows.append(
                    {
                        "time": f"{base_ms:010.3f}",
                        "level": "INFO",
                        "tool": tool_name,
                        "ok": "error" not in res,
                        "details": details,
                        "input": args,
                        "output": res,
                    }
                )
                base_ms += round(50 + len(json.dumps(res)) / 200, 3)

        steps.append({"label": label, "rows": rows})

    # criteria
    criteria = []
    for c in result.get("criteria_scores", []):
        criteria.append(
            {
                "text": c.get("criterion", ""),
                "passed": bool(c.get("passed")),
                "justification": c.get("justification", ""),
            }
        )

    score = result.get("score", 0)
    passed = sum(1 for c in criteria if c["passed"])
    total = max(1, len(criteria))

    return {
        "emails": emails,
        "steps": steps,
        "criteria": criteria,
        "final_answer": result.get("final_answer", ""),
        "score": score,
        "score_display": f"{score:.2f} ({passed}/{total})",
        "score_pass": score >= 1.0,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render(result: dict[str, Any]) -> str:
    data = _build_data(result)
    template = result.get("template", "unknown")
    agent = result.get("agent_name", "unknown")
    steps = len(result.get("trajectory", []))
    seed = result.get("seed", "?")
    score_cls = "pass" if data["score_pass"] else "fail"
    score_icon = "✓" if data["score_pass"] else "✗"

    html = _HTML
    html = html.replace("__TEMPLATE__", template)
    html = html.replace("__AGENT__", agent)
    html = html.replace("__STEPS__", str(steps))
    html = html.replace("__SEED__", str(seed))
    html = html.replace("__SCORE_CLS__", score_cls)
    html = html.replace("__SCORE_ICON__", score_icon)
    html = html.replace("__SCORE_DISPLAY__", data["score_display"])
    html = html.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    return html


def write_report(result: dict[str, Any], out_path: str | Path) -> Path:
    p = Path(out_path)
    p.write_text(render(result), encoding="utf-8")
    return p
