// panel.js — side-panel logic. Talks to backend only via background.js
// messages (check / track / health) and to content.js via tab messages
// (extract). No direct fetch() here — MV3 + design doc non-functional rule.
//
// Data contract: /check response IS the rules.evaluate() verdict:
//   {order_id, capture_id, flags[], summary{}, checks[], meaning{}, corrections[]}
// meaning = {ran, semantic, fraud_warnings[], unassessable_patterns[]}

/* ---------- helpers ---------- */
const $ = (id) => document.getElementById(id);
const hasChrome = typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.id;

function send(message) {
  return new Promise((resolve) => {
    if (!hasChrome) return resolve({ ok: false, status: 0, data: { error: "not in extension context" } });
    try {
      chrome.runtime.sendMessage(message, (resp) => {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, status: 0, data: { error: chrome.runtime.lastError.message } });
        } else {
          resolve(resp || { ok: false, status: 0, data: { error: "empty response" } });
        }
      });
    } catch (err) {
      resolve({ ok: false, status: 0, data: { error: String(err) } });
    }
  });
}

function note(text, color) {
  const el = $("loadNote");
  el.textContent = text;
  el.style.color = color || "var(--text-dim)";
  el.hidden = false;
}
function clearNote() { $("loadNote").hidden = true; }

/* shape dictionary — one shape per dispute evidence_type */
const SHAPES = {
  TRACKING_INFORMATION: "sh-tag",
  PROOF_OF_FULFILLMENT: "sh-envelope",
  PROOF_OF_DELIVERY_ADDRESS: "sh-address",
  SIGNATURE_CONFIRMATION: "sh-signature",
  PROOF_OF_SERVICE_OR_DELIVERY_LOG: "sh-log",
  SHIPMENT_DATE_RECORD: "sh-calendar",
  ITEM_DESCRIPTION_OR_LISTING: "sh-listing",
  CATEGORY_DOCUMENTATION: "sh-folder",
};
function icon(t) { return `<svg><use href="#${SHAPES[t] || "sh-log"}"/></svg>`; }
/* break long identifiers at underscores, not mid-word */
function brk(s) { return String(s).replace(/_/g, "_" + String.fromCharCode(0x200B)); }
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- state ---------- */
let currentVerdict = null;   // verdict being displayed
let previousVerdict = null;  // verdict before the last successful track+re-check

/* ---------- boot ---------- */
async function boot() {
  const health = await send({ type: "health" });
  const ds = $("dataState");
  const llm = $("llmState");
  if (health.ok && health.data && health.data.ok) {
    ds.textContent = health.data.fixture ? "fixture" : "live";
    ds.className = "ok";
    llm.textContent = health.data.llm ? "available" : "unavailable";
    llm.className = health.data.llm ? "ok" : "";
  } else {
    ds.textContent = "offline";
    ds.className = "bad";
    llm.textContent = "—";
    note("Backend is offline at 127.0.0.1:8000 — start it, then load an order.", "var(--amber)");
  }

  // Try to extract an id candidate from the active tab (PayPal console).
  if (!hasChrome || !chrome.tabs) return;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) return;
    chrome.tabs.sendMessage(tab.id, { type: "extract" }, (resp) => {
      if (chrome.runtime.lastError || !resp || !resp.candidates) return; // not a PayPal page / no content script
      renderCandidates(resp.candidates);
    });
  } catch (_) { /* ignore — manual input remains */ }
}

function renderCandidates(cands) {
  const box = $("cands");
  box.innerHTML = "";
  const seen = new Set();
  for (const c of cands) {
    if (!c || !c.id || seen.has(c.id)) continue;
    seen.add(c.id);
    const chip = document.createElement("button");
    chip.className = "cand-chip";
    chip.innerHTML = `${esc(c.id)} <span class="conf">${esc(c.source || "candidate")}</span>`;
    chip.title = `detected via ${c.source || "page scan"} — click to use`;
    chip.addEventListener("click", () => { $("capInput").value = c.id; clearNote(); });
    box.appendChild(chip);
  }
  box.hidden = box.children.length === 0;
}

/* ---------- check flow ---------- */
// Capture ids and order ids are indistinguishable by shape (both ~17 chars),
// so we try capture_id first (extraction candidates are capture ids) and fall
// back to order_id on failure. Sending both fields at once is wrong: the
// backend resolves order_id first, so a capture id sent as order_id 404s.
async function runCheck(idValue) {
  const v = (idValue || "").trim();
  if (!v) { note("Enter a capture id or order id.", "var(--amber)"); return false; }
  $("btnCheck").disabled = true;
  note("Checking…");
  let resp = await send({ type: "check", capture_id: v });
  if (!resp.ok) {
    resp = await send({ type: "check", order_id: v });
  }
  $("btnCheck").disabled = false;
  if (!resp.ok) {
    const msg = (resp.data && resp.data.error) || `backend error (status ${resp.status})`;
    note(`Check failed: ${msg}`, "var(--danger)");
    return false;
  }
  const verdict = resp.data;
  if (!verdict || !verdict.checks) {
    note("Unexpected response shape from backend.", "var(--danger)");
    return false;
  }
  // keep the previous verdict for §06 only when re-checking the SAME order
  previousVerdict = (currentVerdict && currentVerdict.order_id === verdict.order_id) ? currentVerdict : null;
  currentVerdict = verdict;
  clearNote();
  render(verdict, previousVerdict);
  return true;
}

/* ---------- render ---------- */
function render(v, prev) {
  $("metaOrder").textContent = v.order_id ? `${v.order_id.slice(0, 8)}…${v.order_id.slice(-5)}` : "—";
  renderSummary(v.summary);
  renderCards(v.checks);
  renderFlags(v.flags);
  renderSemantic(v.meaning);
  renderSlots(v.checks);
  renderFix(v);
  renderBeforeAfter(v, prev);
}

function renderSummary(s) {
  $("summary").innerHTML =
    `<div class="chip p"><div class="n">${Number(s.n_pass) | 0}</div><div class="l">PASS</div></div>
     <div class="chip f"><div class="n">${Number(s.n_fail) | 0}</div><div class="l">FAIL</div></div>
     <div class="chip n"><div class="n">${Number(s.n_not_assessable) | 0}</div><div class="l">N/A</div></div>`;
}

const pill = (st) =>
  st === "fail" ? '<span class="c-status st-fail">FAIL</span>'
  : st === "pass" ? '<span class="c-status st-pass">PASS</span>'
  : '<span class="c-status st-na">N/A</span>';

function renderCards(checks) {
  $("checksEmpty").hidden = true;
  const strip = $("strip");
  strip.innerHTML = "";
  $("checkCount").textContent = `${checks.length} checks`;
  for (const c of checks) {
    const el = document.createElement("div");
    el.className = "card " + c.status;
    const doNotShip = /do not ship/i.test(c.prescription || "");
    // Prescriptions are corrective (fail-oriented) text: verbatim for fail,
    // contingent for not_assessable, hidden for pass.
    const rx = c.status === "fail"
      ? `<div class="c-rx${doNotShip ? " do-not-ship" : ""}">${esc(c.prescription)}</div>`
      : c.status === "not_assessable"
      ? `<div class="c-rx cond"><span class="lbl">WHEN APPLICABLE</span>${esc(c.prescription)}</div>`
      : "";
    el.innerHTML = `<div class="c-head"><div class="c-name">${brk(esc(c.condition))}</div>${pill(c.status)}</div>
      <div class="c-clause">${esc(c.clause)}</div>
      <div class="c-basis">${esc(c.basis)}</div>
      ${rx}
      <div class="c-legal">declared-data read · not legal advice</div>
      <div class="c-evid">${(c.expected_evidence || []).map((t) => `<a class="evid-mini" href="#slot-${esc(t)}">${icon(t)}<span>${brk(esc(t))}</span></a>`).join("")}</div>`;
    strip.appendChild(el);
  }
  strip.scrollLeft = 0;
  buildStripUi(strip, checks.length);
}

let stripUiWired = false;
function buildStripUi(strip, count) {
  const dots = $("stripDots");
  dots.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const d = document.createElement("div");
    d.className = "d" + (i === 0 ? " on" : "");
    dots.appendChild(d);
  }
  if (stripUiWired) { syncStripNav(strip); return; }
  stripUiWired = true;
  const prevBtn = $("stripPrev"), nextBtn = $("stripNext");
  strip.addEventListener("scroll", () => {
    const i = Math.round(strip.scrollLeft / 238);
    [...dots.children].forEach((d, j) => d.classList.toggle("on", j === i));
    syncStripNav(strip);
  });
  // wheel → horizontal with edge release
  strip.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    const atStart = strip.scrollLeft <= 1;
    const atEnd = strip.scrollLeft >= strip.scrollWidth - strip.clientWidth - 2;
    if ((e.deltaY < 0 && atStart) || (e.deltaY > 0 && atEnd)) return;
    e.preventDefault();
    strip.scrollLeft += e.deltaY;
  }, { passive: false });
  prevBtn.addEventListener("click", () => strip.scrollBy({ left: -238, behavior: "smooth" }));
  nextBtn.addEventListener("click", () => strip.scrollBy({ left: 238, behavior: "smooth" }));
  let dragX = null, dragL = 0, dragged = false;
  strip.addEventListener("pointerdown", (e) => { dragX = e.clientX; dragL = strip.scrollLeft; dragged = false; });
  strip.addEventListener("pointermove", (e) => { if (dragX === null) return; const dx = e.clientX - dragX; if (Math.abs(dx) > 6) dragged = true; strip.scrollLeft = dragL - dx; });
  strip.addEventListener("pointerup", () => { dragX = null; });
  strip.addEventListener("click", (e) => { if (dragged) { e.preventDefault(); e.stopPropagation(); dragged = false; } }, true);
  syncStripNav(strip);
}
function syncStripNav(strip) {
  $("stripPrev").classList.toggle("off", strip.scrollLeft <= 1);
  $("stripNext").classList.toggle("off", strip.scrollLeft >= strip.scrollWidth - strip.clientWidth - 2);
}

function renderFlags(flags) {
  const box = $("flagBox");
  if (!flags || !flags.length) {
    box.innerHTML = '<div class="sec-empty" style="border:0;padding:0">No seller_protection flag on this order.</div>';
    return;
  }
  const rows = flags.map((f) => {
    const status = f.status || "none";
    const neg = status !== "ELIGIBLE";
    const cats = (f.dispute_categories || []).map((c) => `<span class="flag-cat">${brk(esc(c))}</span>`).join("") || '<span class="flag-cat">none</span>';
    return `<div class="flag-kv"><span class="k">capture_id</span><span class="v">${esc(f.capture_id || "—")}</span></div>
      <div class="flag-kv"><span class="k">seller_protection.status</span><span class="v flag-status${neg ? " neg" : ""}">${esc(status)}</span></div>
      <div class="flag-kv"><span class="k">dispute_categories</span><span class="v">${cats}</span></div>`;
  }).join('<div style="border-top:1px solid var(--line);margin:6px 0"></div>');
  box.innerHTML = `<div class="flag-label">DECLARED-DATA SNAPSHOT</div>${rows}
    <div class="flag-note">"ELIGIBLE" reflects what was declared — may be eligible, not a final decision. showing ${flags.length} capture(s) for this order.</div>`;
}

function renderSemantic(m) {
  const root = $("semRoot");
  let html = "";
  if (m && m.ran === false) {
    html += `<div class="sem-card"><div class="sem-title">Semantic layer not run</div>
      <div class="sdesc" style="font-size:10.5px;color:var(--text-dim);margin-top:4px">No LLM credentials — semantic classification skipped (ran=false). Nothing is inferred or fabricated in its place.</div></div>`;
  } else if (m && m.ran === true && m.semantic) {
    const s = m.semantic;
    html += `<div class="sem-card"><div class="sem-sub">LLM classification</div>`;
    html += `<div class="sem-item"><div class="pbasis">category: ${esc(s.category || "—")} · confidence: ${esc(String(s.confidence ?? "—"))}</div>`;
    if (s.mismatch) {
      html += `<div class="pname" style="margin-top:4px">${brk(esc(s.mismatch))}</div>
        <div class="pbasis">evidence: ${esc(s.evidence_span || "")}</div>`;
    } else {
      html += `<div class="pbasis" style="margin-top:4px">mismatch: none flagged (undisputed mismatches only)</div>`;
    }
    html += `</div></div>`;
  }
  const warns = (m && m.fraud_warnings) || [];
  html += `<div class="sem-card"><div class="sem-sub">fraud warnings — API-visible match</div>`;
  html += warns.length
    ? warns.map((w) => `<div class="sem-item"><div class="pname">${brk(esc(w.name))}</div><div class="pbasis">signal_basis: ${esc(w.signal_basis || "")}</div></div>`).join("")
    : `<div class="sem-empty">no API-visible patterns matched on this capture</div>`;
  html += `</div><div class="sem-card"><div class="sem-sub">unassessable patterns — not evaluable from this API</div>`;
  const unassess = (m && m.unassessable_patterns) || [];
  html += unassess.map((p) => `<div class="sem-item"><div class="pname na">${brk(esc(p.name))}</div><div class="pbasis">reason: ${esc(p.signal_basis || p.reason || "")}</div></div>`).join("");
  html += `<div class="pbasis" style="margin-top:8px;font-size:9.5px;color:var(--text-faint)">table-driven — returned even when the LLM semantic layer has not run</div></div>`;
  root.innerHTML = html;
}

/* ---------- §04 evidence slots ----------
   Slot state is DERIVED in the panel from the check row's backend-declared
   unfixable_for_order flag (fallback: "do not ship" prescription match for
   older verdict shapes):
   - fail-referenced type where every failing check is unfixable_for_order
     → unfillable (no way to produce it for this order)
   - any other fail-referenced type → fillable (some path still produces it)
   - pass-referenced types render as compact chips only */
function deriveSlotState(refsForType) {
  const fails = refsForType.filter((r) => r.status === "fail");
  if (!fails.length) return "fillable";
  const allUnfixable = fails.every((r) =>
    r.unfixable_for_order === true || /do not ship|excluded from seller protection/i.test(r.prescription || ""));
  return allUnfixable ? "unfillable" : "fillable";
}
const SLOT_DESC = {
  fillable: "Not present in this order's API data yet — it can still be produced.",
  unfillable: "Cannot be produced for this order — every check requiring it prescribes not shipping.",
};
function renderSlots(checks) {
  const root = $("slotRoot");
  root.innerHTML = "";
  const refs = {};
  for (const c of checks) for (const t of c.expected_evidence || []) {
    (refs[t] = refs[t] || []).push({
      condition: c.condition, status: c.status,
      prescription: c.prescription, unfixable_for_order: c.unfixable_for_order,
    });
  }
  const types = Object.keys(refs);
  const bigTypes = types.filter((t) => refs[t].some((r) => r.status === "fail"));
  const smallTypes = types.filter((t) => !bigTypes.includes(t));
  if (!bigTypes.length && !smallTypes.length) {
    root.innerHTML = '<div class="sec-empty">No evidence types referenced by this order.</div>';
    return;
  }
  for (const t of bigTypes) {
    const st = deriveSlotState(refs[t]);
    const el = document.createElement("div");
    el.className = "slot " + st;
    el.id = "slot-" + t;
    const refTxt = refs[t].map((r) => `${brk(esc(r.condition))} (${esc(r.status)})`).join(" · ");
    el.innerHTML = `<div class="pouch">${icon(t)}</div>
      <div class="body"><div class="shead"><div class="sname">${brk(esc(t))}</div><span class="sstate ss-${st}">${st.toUpperCase()}</span></div>
        <div class="sdesc">${SLOT_DESC[st]}</div>
        <div class="srefs">referenced by: ${refTxt}</div></div>`;
    root.appendChild(el);
  }
  if (smallTypes.length) {
    const wrap = document.createElement("div");
    wrap.innerHTML = `<div class="srefs" style="margin:10px 0 4px">also referenced by this order's checks:</div>`;
    const list = document.createElement("div");
    list.className = "ref-list";
    for (const t of smallTypes) {
      const chip = document.createElement("span");
      chip.className = "ref-chip";
      chip.id = "slot-" + t;   // anchor target for card evid-mini links
      // smallTypes have no fail refs by definition; show "n/a" only when
      // every referencing check is not_assessable, otherwise "pass"
      const st = refs[t].every((r) => r.status === "not_assessable") ? "not_assessable" : "pass";
      chip.title = refs[t].map((r) => `${r.condition} (${r.status})`).join(" · ");
      chip.innerHTML = `${icon(t)}<span>${brk(esc(t))}</span><span class="rc-st">${st === "not_assessable" ? "n/a" : esc(st)}</span>`;
      list.appendChild(chip);
    }
    wrap.appendChild(list);
    root.appendChild(wrap);
  }
}

/* ---------- §05 fix ---------- */
function renderFix(v) {
  const corr = (v.corrections || []).find((c) => c.action === "REGISTER_TRACKING");
  const form = $("fixForm"), btn = $("btnTrack"), cav = $("fixCaveat");
  if (!corr) {
    $("fixTitle").textContent = "No fixes available";
    $("fixDesc").textContent = "This order has no in-panel corrective action. Checks marked N/A or DO NOT SHIP are not fixable here.";
    form.hidden = true; btn.hidden = true; cav.hidden = true;
    return;
  }
  $("fixTitle").textContent = corr.label || "Register tracking";
  $("fixDesc").textContent = "Fills the TRACKING_INFORMATION slot above. May update the TRACKING_REQUIRED check once PayPal confirms.";
  cav.textContent = "Registering tracking updates this order's declared data — it does not guarantee any dispute outcome.";
  cav.hidden = false;
  form.hidden = false; btn.hidden = false;
}

function renderBeforeAfter(v, prev) {
  if (!prev) {
    $("baBefore").innerHTML = '<div class="ba-note" style="margin:0">re-check after a fix to compare</div>';
    $("baAfter").innerHTML = '<div class="ba-note" style="margin:0">—</div>';
    return;
  }
  const prevStatus = {};
  for (const c of prev.checks) prevStatus[c.condition] = c.status;
  const changed = v.checks.filter((c) => prevStatus[c.condition] !== c.status);
  const baRow = (c, st) => `<div class="ba-row"><span class="ba-dot ${st}"></span><span class="ba-name">${brk(esc(c.condition))} — ${st}</span></div>`;
  $("baBefore").innerHTML = changed.length
    ? changed.map((c) => baRow(c, prevStatus[c.condition])).join("")
    : '<div class="ba-note" style="margin:0">no status changes</div>';
  $("baAfter").innerHTML = changed.length
    ? changed.map((c) => baRow(c, c.status)).join("")
    : '<div class="ba-note" style="margin:0">no status changes</div>';
}

/* ---------- §05 track flow ---------- */
async function runTrack() {
  const carrier = $("carrierSel").value;
  const tracking = $("trackNum").value.trim();
  const other = carrier === "OTHER" ? $("carrierOther").value.trim() : null;
  const fn = $("fixNote");
  if (!tracking) { fn.textContent = "tracking number is required"; fn.style.color = "var(--amber)"; return; }
  if (carrier === "OTHER" && !other) { fn.textContent = "carrier name is required when carrier = OTHER"; fn.style.color = "var(--amber)"; return; }
  if (!currentVerdict || !currentVerdict.capture_id) { fn.textContent = "load an order first"; fn.style.color = "var(--amber)"; return; }
  $("btnTrack").disabled = true;
  fn.textContent = "registering…"; fn.style.color = "var(--text-dim)";
  const resp = await send({
    type: "track",
    capture_id: currentVerdict.capture_id,
    tracking_number: tracking,
    carrier,
    carrier_name_other: other,
  });
  $("btnTrack").disabled = false;
  if (!resp.ok) {
    const msg = (resp.data && resp.data.error) || `backend error (status ${resp.status})`;
    fn.textContent = `registration failed: ${msg}`;
    fn.style.color = "var(--danger)";
    return;
  }
  fn.textContent = "registered · re-checking…";
  fn.style.color = "var(--green)";
  const ok = await runCheck(currentVerdict.capture_id);
  if (ok) {
    fn.textContent = "registered — re-check complete";
    fn.style.color = "var(--green)";
  } else {
    fn.textContent = "registered, but the re-check failed (see note above)";
    fn.style.color = "var(--amber)";
  }
}

/* ---------- wiring ---------- */
$("btnCheck").addEventListener("click", () => runCheck($("capInput").value));
$("capInput").addEventListener("keydown", (e) => { if (e.key === "Enter") runCheck($("capInput").value); });
$("carrierSel").addEventListener("change", (e) => { $("carrierOther").hidden = e.target.value !== "OTHER"; });
$("btnTrack").addEventListener("click", runTrack);

boot();
