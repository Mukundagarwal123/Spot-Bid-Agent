/* ── Constants ────────────────────────────────────────────────────── */
const LANE_ID    = window.__LANE_ID__;
const STAGES     = ["Build", "Preview", "Send", "Live", "Complete"];
const EQUIP_LABELS = { dry_van: "Dry Van", reefer: "Reefer", flatbed: "Flatbed", power_only: "Power Only", other: "Other" };
const SRC_LABEL    = { internal: "Internal", dat: "DAT", crr_model: "CRR Model", manual: "Manual Emails" };
const SRC_KEYS     = ["internal", "dat", "crr_model", "manual"];
const POLL_MS      = 5000;

/* ── State ────────────────────────────────────────────────────────── */
const state = {
  lane:                null,
  metrics:             null,
  prevMetrics:         null,
  sources:             { internal: true, dat: true, crr_model: true, manual: false },
  notes:               "",
  previewData:         null,
  pollTimer:           null,
  activeTab:           "all",
  sourceFilter:        "all",
  searchTerm:          "",
  allResponses:        [],
  internal_filter_mode: "city_state",  // "city_state" | "state_only"
  source_limits:       {},             // e.g. {"CRR Model": 500}
};

/* ── Utility ──────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res  = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error(json?.detail || "Request failed"); e.payload = json; throw e; }
  return json;
}
const fmtDate = v => v ? new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "TBD";
const fmtTime = v => v ? new Date(v).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "";
const fmtDT   = v => v ? new Date(v).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
const pct     = (n, d) => d ? Math.round(n / d * 100) + "%" : "0%";

/* ── Session storage ──────────────────────────────────────────────── */
function loadSession() {
  try {
    const raw = sessionStorage.getItem(`lane_init_${LANE_ID}`);
    if (!raw) return;
    const d = JSON.parse(raw);
    if (d.sources) Object.assign(state.sources, d.sources);
    if (d.notes)   state.notes = d.notes;
    if (d.manual_emails?.length) {
      state.sources.manual = true;
      d.manual_emails.forEach(e => addManualRow(e));
      document.getElementById("manual-emails-section")?.classList.remove("hidden");
    }
  } catch (_) {}
}

/* ── Stage rail ───────────────────────────────────────────────────── */
function stageIdx(m, lane) {
  if (!m || !m.batch_id) return 0;
  if (m.campaign_ended || lane?.status === "completed") return 4;
  if (m.sent > 0) return 3;
  return 2;
}
function renderStageRail(active) {
  const rail = document.getElementById("stage-rail");
  let html = "";
  STAGES.forEach((label, i) => {
    const cls  = i < active ? "done"   : i === active ? "active" : "pending";
    const icon = i < active ? "✓"      : i === active ? "●"      : String(i + 1);
    html += `<div class="sr-item">
      <div class="sr-dot-wrap">
        <div class="sr-dot ${cls}">${icon}</div>
        <div class="sr-label ${cls}">${label}</div>
      </div>
      ${i < STAGES.length - 1
        ? `<div class="sr-line ${i < active ? "done" : i === active ? "active" : ""}"></div>`
        : ""}
    </div>`;
  });
  rail.innerHTML = html;
}

/* ── Lane header ──────────────────────────────────────────────────── */
function renderHeader(lane) {
  document.title = `${lane.label} — Spot Bid`;
  document.getElementById("nav-label").textContent = lane.label;
  document.getElementById("nav-sub").textContent =
    `${lane.origin_city}, ${lane.origin_state} → ${lane.destination_city}, ${lane.destination_state}`;
  document.getElementById("lane-route").textContent = lane.label;

  const chips = [];
  chips.push(EQUIP_LABELS[lane.equipment_type] || lane.equipment_type);
  if (lane.pickup_date) chips.push(`Pickup ${fmtDate(lane.pickup_date)}`);
  if (lane.origin_zip)  chips.push(`${lane.origin_zip} → ${lane.destination_zip || ""}`);
  document.getElementById("lane-meta").innerHTML = chips.map(c => `<span class="ld-chip">${c}</span>`).join("");

  if (lane.notes) {
    const el = document.getElementById("lane-notes-preview");
    el.textContent = `"${lane.notes}"`;
    el.classList.remove("hidden");
  }

  const statusCls   = { completed: "status-completed", in_progress: "status-in_progress", new: "status-new" };
  const statusLabel = { completed: "Completed", in_progress: "Live", new: "New" };
  document.getElementById("lane-status-wrap").innerHTML =
    `<span class="lane-status-pill ${statusCls[lane.status] || "status-new"}">${statusLabel[lane.status] || lane.status}</span>`;
}

/* ── Nav buttons ──────────────────────────────────────────────────── */
function updateNavBtns(m, lane) {
  const ended    = m?.campaign_ended || lane?.status === "completed";
  const hasBatch = !!(m?.batch_id && m.sent > 0);
  const eligible = m?.follow_up_eligible_count || 0;
  document.getElementById("follow-up-btn").classList.toggle("hidden", ended || !hasBatch || eligible === 0);
  document.getElementById("end-campaign-btn").classList.toggle("hidden", ended || !hasBatch);
  document.getElementById("live-indicator").classList.toggle("hidden", !hasBatch || ended);
}

/* ── Source summary (read-only chips from portal selection) ───────── */
function renderSourceSummary() {
  const LABELS = {
    internal:  "🗄️ Internal",
    dat:       "🚛 DAT",
    crr_model: "✨ CRR Model",
    manual:    "✏️ Manual Emails",
  };
  const chips = Object.entries(state.sources)
    .filter(([, v]) => v)
    .map(([k]) => `<span class="src-summary-chip">${LABELS[k]}</span>`)
    .join("");
  const el = document.getElementById("src-summary");
  if (el) el.innerHTML = chips || `<span class="src-summary-none">No sources selected — go back and add a lane.</span>`;
  // Show/hide internal filter toggle based on whether internal source is selected
  document.getElementById("internal-filter-section")?.classList.toggle("hidden", !state.sources.internal);
}

function addManualRow(entry = null) {
  const container = document.getElementById("manual-email-rows");
  const row = document.createElement("div");
  row.className = "manual-row";
  row.innerHTML = `
    <input type="text"  class="manual-carrier-name" placeholder="Carrier Name"  value="${entry?.carrier_name || ""}" />
    <input type="email" class="manual-email-addr"   placeholder="Email address" value="${entry?.email || ""}" />
    <button type="button" class="rm-btn">×</button>`;
  row.querySelector(".rm-btn").addEventListener("click", () => { row.remove(); debouncedPreview(); });
  row.querySelectorAll("input").forEach(i => i.addEventListener("input", debouncedPreview));
  container.appendChild(row);
}

function collectManualRows() {
  return [...document.querySelectorAll(".manual-row")].map(r => ({
    carrier_name: r.querySelector(".manual-carrier-name")?.value?.trim() || "",
    email:        r.querySelector(".manual-email-addr")?.value?.trim()   || "",
  })).filter(e => e.email);
}

/* ── 3-step wizard navigation ─────────────────────────────────────── */
function setWizardStep(n) {
  [1, 2, 3].forEach(i => {
    document.getElementById(`wz-pane-${i}`)?.classList.toggle("hidden", i !== n);
    const el = document.querySelector(`.wz-step[data-step="${i}"]`);
    if (el) {
      el.classList.toggle("active", i === n);
      el.classList.toggle("done",   i < n);
    }
  });
  document.querySelectorAll(".wz-step-line").forEach((el, idx) => {
    el.classList.toggle("done", idx < n - 1);
  });
}

/* ── Client-side email preview ────────────────────────────────────── */
function buildClientPreviewHtml(lane) {
  if (!lane) return "<p style='padding:20px;color:#94a3b8'>Loading…</p>";
  const origin = `${lane.origin_city}, ${lane.origin_state}${lane.origin_zip ? " " + lane.origin_zip : ""}`;
  const dest   = `${lane.destination_city}, ${lane.destination_state}${lane.destination_zip ? " " + lane.destination_zip : ""}`;
  const equip  = EQUIP_LABELS[lane.equipment_type] || lane.equipment_type;
  const pickup = fmtDate(lane.pickup_date);
  const notes  = document.getElementById("launch-notes")?.value?.trim() || "";

  const notesBlock = notes ? `
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#fffbeb;border-left:4px solid #d97706;border-radius:0 10px 10px 0;margin-bottom:22px">
      <tr><td style="padding:14px 20px">
        <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#92400e;font-weight:700;margin-bottom:6px">Special Notes</div>
        <div style="font-size:13px;color:#78350f;line-height:1.55">${notes}</div>
      </td></tr>
    </table>` : "";

  return `<!DOCTYPE html><html><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:16px;background:#f0f4f9;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td align="center">
  <table width="540" cellpadding="0" cellspacing="0" border="0"
         style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.09)">
    <tr><td style="background:#0f2f47;padding:24px 30px">
      <div style="font-size:19px;font-weight:800;color:#fff">T3RA Logistics — Spot Bid Opportunity</div>
      <div style="font-size:12px;color:#abc3d9;margin-top:5px;font-weight:600">${origin} &rarr; ${dest}</div>
      <div style="font-size:10px;color:#7ea8c6;margin-top:5px;font-style:italic">Your Freight. Our Mission. &middot; Veteran-Owned &amp; Operated</div>
    </td></tr>
    <tr><td style="padding:26px 30px">
      <p style="margin:0 0 10px;font-size:15px;font-weight:700;color:#12263a">Hi [Carrier Name],</p>
      <p style="margin:0 0 18px;font-size:13px;color:#344054;line-height:1.65">
        We have an active spot freight opportunity that matches your operating area.
        We're moving quickly to cover this load and would appreciate your best rate.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:#f0f7ff;border-left:4px solid #1d4ed8;border-radius:0 10px 10px 0;margin-bottom:20px">
        <tr><td style="padding:14px 18px">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr><td style="font-size:12px;color:#5e748a;padding:2px 0;width:110px;font-weight:600">Origin</td><td style="font-size:12px;color:#12263a;font-weight:700">${origin}</td></tr>
            <tr><td style="font-size:12px;color:#5e748a;padding:2px 0;font-weight:600">Destination</td><td style="font-size:12px;color:#12263a;font-weight:700">${dest}</td></tr>
            <tr><td style="font-size:12px;color:#5e748a;padding:2px 0;font-weight:600">Equipment</td><td style="font-size:12px;color:#12263a">${equip}</td></tr>
            <tr><td style="font-size:12px;color:#5e748a;padding:2px 0;font-weight:600">Pickup</td><td style="font-size:12px;color:#12263a">${pickup}</td></tr>
          </table>
        </td></tr>
      </table>
      ${notesBlock}
      <p style="margin:0 0 20px;font-size:13px;color:#344054;line-height:1.65">
        Reply with your available capacity and all-in rate and we'll follow up within the hour.
      </p>
      <table cellpadding="0" cellspacing="0" border="0">
        <tr><td style="background:#b91c1c;border-radius:9px">
          <a href="mailto:dispatch@t3ralogistics.com"
             style="display:inline-block;padding:11px 26px;font-size:13px;font-weight:700;color:#fff;text-decoration:none">
            Reply to Bid &rarr;
          </a>
        </td></tr>
      </table>
    </td></tr>
    <tr><td style="background:#f8fbff;padding:12px 30px;border-top:1px solid #e2e8f0">
      <p style="margin:0;font-size:10px;color:#94a3b8">T3RA Logistics &middot; Spot Bid Operations</p>
    </td></tr>
  </table>
</td></tr></table>
</body></html>`;
}

let previewTimer = null;
function debouncedPreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    if (!state.lane) return;
    const iframe = document.getElementById("email-preview-iframe");
    if (iframe) iframe.srcdoc = buildClientPreviewHtml(state.lane);
    const autoSubj = `Spot Bid: ${state.lane.origin_city}, ${state.lane.origin_state} → ${state.lane.destination_city}, ${state.lane.destination_state} | ${EQUIP_LABELS[state.lane.equipment_type] || state.lane.equipment_type}`;
    const sv = document.getElementById("preview-subject-val");
    const editSubjEl = document.getElementById("edit-subject");
    const customSubj = editSubjEl?.value?.trim();
    if (sv) sv.textContent = customSubj || autoSubj;
    if (editSubjEl && !customSubj) editSubjEl.placeholder = autoSubj;
  }, 120);
}

/* ── Edit email panel ─────────────────────────────────────────────── */
function initEditEmailPanel() {
  const btn      = document.getElementById("edit-email-btn");
  const panel    = document.getElementById("email-edit-panel");
  const notesEl  = document.getElementById("launch-notes");
  const inlineEl = document.getElementById("edit-notes-inline");
  const subjEl   = document.getElementById("edit-subject");

  btn?.addEventListener("click", () => {
    const opening = panel.classList.toggle("hidden") === false;
    btn.textContent = opening ? "✕ Close" : "✏️ Edit Email";
    if (opening && notesEl) inlineEl.value = notesEl.value;
  });

  inlineEl?.addEventListener("input", () => {
    if (notesEl) notesEl.value = inlineEl.value;
    state.notes = inlineEl.value;
    debouncedPreview();
  });

  subjEl?.addEventListener("input", debouncedPreview);
}

/* ── Step 2: Fetch timeline ───────────────────────────────────────── */
const SRC_ICONS = { internal: "🗄️", dat: "🚛", crr_model: "✨", manual: "✏️" };

function _ftSetState(k, state_, countVal, statusText) {
  const rowEl    = document.getElementById(`ft-${k}`);
  const countEl  = document.getElementById(`ft-count-${k}`);
  const statusEl = document.getElementById(`ft-status-${k}`);
  if (!rowEl) return;
  rowEl.classList.remove("loading", "found", "ready");
  if (state_) rowEl.classList.add(state_);
  if (statusEl) statusEl.textContent = statusText;
  if (countEl) countEl.outerHTML =
    countVal == null
      ? `<div class="ft-count loading" id="ft-count-${k}"><div class="ft-spinner"></div></div>`
      : `<div class="ft-count ${state_ || ""}" id="ft-count-${k}">${countVal > 0 ? countVal : "—"}</div>`;
}

async function onCheckCarriers() {
  const errEl = document.getElementById("wizard-step1-error");
  errEl.classList.add("hidden");

  state.notes = document.getElementById("launch-notes").value || "";
  state.source_limits = {};  // reset limits on each new fetch
  const manualEmails = collectManualRows();

  // Read internal filter mode from radio buttons
  state.internal_filter_mode =
    document.querySelector('input[name="internal_filter"]:checked')?.value || "city_state";

  setWizardStep(2);

  const activeSources = SRC_KEYS.filter(k => state.sources[k]);
  const timeline = document.getElementById("fetch-timeline");
  timeline.innerHTML = activeSources.map(k => `
    <div class="ft-row loading" id="ft-${k}">
      <div class="ft-icon-wrap">${SRC_ICONS[k] || "📦"}</div>
      <div class="ft-info">
        <div class="ft-name">${SRC_LABEL[k]}</div>
        <div class="ft-status" id="ft-status-${k}">Scanning database…</div>
      </div>
      <div class="ft-count loading" id="ft-count-${k}">
        <div class="ft-spinner"></div>
      </div>
    </div>`).join("");

  const summaryEl  = document.getElementById("wz-total-summary");
  const sendBtn    = document.getElementById("launch-campaign-btn");
  const dlBtn       = document.getElementById("download-outreach-btn");
  summaryEl.classList.add("hidden");
  sendBtn.classList.add("hidden");
  sendBtn.disabled = true;
  if (dlBtn) dlBtn.classList.add("hidden");
  document.getElementById("source-limits-section")?.classList.add("hidden");
  document.getElementById("wizard-step2-error").classList.add("hidden");

  // ── State-only internal rerun (if user selected broader filter) ────
  if (state.sources.internal && state.internal_filter_mode === "state_only") {
    _ftSetState("internal", "loading", null, "Re-fetching with state filter…");
    try {
      await api(`/portal/lanes/${LANE_ID}/carriers/internal-rerun`, {
        method: "POST",
        body: JSON.stringify({ filter_mode: "state_only" }),
      });
    } catch (_) { /* non-fatal — counts poll will show whatever is in DB */ }
  }

  // ── Phase 1: poll DB counts until background tasks finish ──────────
  const nonManualSources = activeSources.filter(k => k !== "manual");
  if (nonManualSources.length > 0) {
    const POLL_INTERVAL_MS = 2000;
    const MAX_WAIT_MS      = 150000; // 2.5 min — DAT LLM can take 60-90 s
    const deadline         = Date.now() + MAX_WAIT_MS;
    const resolved         = new Set();

    // Show "processing" immediately for DAT if it was submitted
    if (activeSources.includes("dat")) {
      _ftSetState("dat", "loading", 0, "Processing paste… (~60 s)");
    }

    // Poll until all sources resolve or deadline, keeping DAT alive while pending
    while (Date.now() < deadline) {
      try {
        const counts = await api(`/portal/lanes/${LANE_ID}/carriers/counts`);

        if (counts.dat_pending) {
          _ftSetState("dat", "loading", 0, "Processing paste… (~60 s)");
        }

        nonManualSources.forEach(k => {
          if (resolved.has(k)) return;
          const n = counts[k] ?? 0;
          if (n > 0) {
            _ftSetState(k, "found", n, `${n.toLocaleString()} carriers found — resolving emails…`);
            resolved.add(k);
          }
        });

        // Done when all sources resolved and no DAT still pending
        if (resolved.size === nonManualSources.length && !counts.dat_pending) break;

        // If nothing is pending (no dat_pending, all non-dat resolved) give up early
        const nonDatPending = nonManualSources.filter(k => k !== "dat" && !resolved.has(k));
        if (!counts.dat_pending && nonDatPending.length === 0) break;
      } catch (_) { /* keep polling */ }

      await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
    }

    // Any source still unresolved: mark as no data
    nonManualSources.forEach(k => {
      if (!resolved.has(k)) _ftSetState(k, null, 0, "No data found for this lane");
    });
  }

  // ── Phase 2: full outreach preview (builds outreach set + email filter) ─
  try {
    const preview = await api(`/portal/lanes/${LANE_ID}/outreach/preview`, {
      method: "POST",
      body: JSON.stringify({
        include_internal:  state.sources.internal,
        include_dat:       state.sources.dat,
        include_crr_model: state.sources.crr_model,
        test_mode:         false,
        manual_emails:     manualEmails,
        notes:             state.notes,
      }),
    });
    state.previewData = preview;

    activeSources.forEach(k => {
      const count = preview.recipient_count_by_source?.[SRC_LABEL[k]] ?? 0;
      if (count > 0) {
        _ftSetState(k, "ready", count, `${count} email${count !== 1 ? "s" : ""} ready`);
      } else {
        _ftSetState(k, null, 0, "No emails for this lane");
      }
    });

    const total   = preview.recipient_count;
    const bounced = preview.bounced_count ?? 0;

    if (total > 0) {
      const bouncedNote = bounced > 0
        ? `<div class="wz-skipped-notice">${bounced} email${bounced !== 1 ? "s" : ""} skipped — previously bounced</div>`
        : "";
      summaryEl.innerHTML = `<div class="wz-total-num">${total}</div>
        <div class="wz-total-label">email${total !== 1 ? "s" : ""} ready to send</div>
        ${bouncedNote}`;
      summaryEl.classList.remove("hidden");
      buildSourceLimitInputs(preview);
      sendBtn.textContent = `🚀 Send Campaign — ${total} email${total !== 1 ? "s" : ""}`;
      sendBtn.disabled = false;
      sendBtn.classList.remove("hidden");
      if (dlBtn) dlBtn.classList.remove("hidden");
    } else {
      const errEl2 = document.getElementById("wizard-step2-error");
      errEl2.textContent = "No valid recipients found for selected sources.";
      errEl2.classList.remove("hidden");
    }

    const iframe = document.getElementById("email-preview-iframe");
    if (iframe) iframe.srcdoc = preview.html_body || buildClientPreviewHtml(state.lane);
    const sv = document.getElementById("preview-subject-val");
    if (sv) sv.textContent = preview.subject;

  } catch (err) {
    setWizardStep(1);
    errEl.textContent = err?.payload?.detail || err?.message || "Failed to load carrier data. Please try again.";
    errEl.classList.remove("hidden");
  }
}


/* ── Step 3: Send ─────────────────────────────────────────────────── */
async function onLaunchCampaign() {
  const errEl  = document.getElementById("wizard-step2-error");
  const sendBtn = document.getElementById("launch-campaign-btn");
  errEl.classList.add("hidden");
  setWizardStep(3);

  try {
    await api(`/portal/lanes/${LANE_ID}/outreach/send`, {
      method: "POST",
      body: JSON.stringify({
        include_internal:  state.sources.internal,
        include_dat:       state.sources.dat,
        include_crr_model: state.sources.crr_model,
        test_mode:         false,
        manual_emails:     collectManualRows(),
        notes:             state.notes,
        source_limits:     Object.keys(state.source_limits).length ? state.source_limits : null,
      }),
    });

    document.getElementById("wizard-shell").classList.add("hidden");
    document.getElementById("live-dash").classList.remove("hidden");
    logAdd("Campaign launched — emails dispatched", "send");
    renderStageRail(3);
    document.getElementById("live-indicator").classList.remove("hidden");
    document.getElementById("log-live-indicator").innerHTML =
      `<span class="live-dot" style="background:#34d399"></span> Live`;

    const m = await api(`/portal/lanes/${LANE_ID}/outreach`).catch(() => null);
    if (m) {
      state.metrics = m;
      renderLiveMetrics(m, null);
      renderRecipientTable(m.carrier_responses || []);
      renderSourceConv(m.source_metrics || {});
      updateNavBtns(m, state.lane);
      renderStageRail(stageIdx(m, state.lane));
    }
    startPolling();

  } catch (err) {
    setWizardStep(2);
    errEl.textContent = err?.payload?.detail || err?.message || "Failed to send. Please try again.";
    errEl.classList.remove("hidden");
    sendBtn.disabled = false;
    sendBtn.textContent = `🚀 Send Campaign — ${state.previewData?.recipient_count ?? ""} emails`;
  }
}

/* ── Live metrics ─────────────────────────────────────────────────── */
function renderLiveMetrics(m, prev) {
  const fields = [
    ["lm-num-sent",      m.sent,      null,              null],
    ["lm-num-delivered", m.delivered, "lm-sub-delivered", `${pct(m.delivered, m.sent)} of sent`],
    ["lm-num-opened",    m.opened,    "lm-sub-opened",    `${pct(m.opened, m.sent)} of sent`],
    ["lm-num-replied",   m.replied,   "lm-sub-replied",   `${pct(m.replied, m.sent)} of sent`],
    ["lm-num-bounced",   m.bounced ?? 0, null,            null],
  ];
  const cards    = ["lm-sent", "lm-delivered", "lm-opened", "lm-replied", "lm-bounced"];
  const prevVals = prev ? [prev.sent, prev.delivered, prev.opened, prev.replied, prev.bounced ?? 0] : null;

  fields.forEach(([id, val, subId, subText], i) => {
    const numEl = document.getElementById(id);
    if (numEl) numEl.textContent = val ?? "—";
    if (subId) {
      const el = document.getElementById(subId);
      if (el) el.textContent = subText;
    }
    if (prevVals && prevVals[i] !== val) {
      const card = document.getElementById(cards[i]);
      if (card) { card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash"); }
    }
  });
}

/* ── Activity log ─────────────────────────────────────────────────── */
function logAdd(text, type = "system", time = null) {
  const container = document.getElementById("activity-log");
  const empty = container.querySelector(".log-empty");
  if (empty) empty.remove();
  const div = document.createElement("div");
  div.className = "log-entry";
  div.innerHTML = `
    <div class="log-dot ${type}"></div>
    <div class="log-text">${text}</div>
    <div class="log-ts">${fmtTime(time || new Date().toISOString())}</div>`;
  container.insertBefore(div, container.firstChild);
}

function syncLog(m, prev) {
  if (!prev) return;
  if (m.replied   > prev.replied)   logAdd(`${m.replied   - prev.replied} carrier(s) replied`,   "reply");
  if (m.opened    > prev.opened)    logAdd(`${m.opened    - prev.opened} email(s) opened`,        "open");
  if (m.delivered > prev.delivered) logAdd(`${m.delivered - prev.delivered} email(s) delivered`, "send");
}

/* ── Recipient table ──────────────────────────────────────────────── */
const STAGE_ICONS = { replied: "💬", opened: "👁", clicked: "🔗", delivered: "✉", sent: "→", bounced: "✕", failed: "✕" };

function renderRecipientTable(responses) {
  state.allResponses = responses;
  applyFilters();
}

function applyFilters() {
  let rows = state.allResponses;

  if (state.activeTab !== "all")
    rows = rows.filter(r => r.status === state.activeTab);

  if (state.sourceFilter !== "all") {
    const sf = state.sourceFilter.toLowerCase();
    rows = rows.filter(r => {
      const src = (r.source_type || r.source || "").toLowerCase();
      return src.includes(sf) || src === sf;
    });
  }

  if (state.searchTerm) {
    const q = state.searchTerm.toLowerCase();
    rows = rows.filter(r =>
      (r.carrier_name || "").toLowerCase().includes(q) ||
      (r.email        || "").toLowerCase().includes(q) ||
      (r.phone        || "").toLowerCase().includes(q)
    );
  }

  const engaged = state.allResponses.filter(r => ["opened", "replied", "clicked"].includes(r.status)).length;
  document.getElementById("response-count").textContent = `${engaged} engaged`;

  const wrap = document.getElementById("recipient-table-wrap");
  if (!rows.length) {
    wrap.innerHTML = `<div class="empty-table">No ${state.activeTab !== "all" ? state.activeTab + " " : ""}recipients match your filters.</div>`;
    return;
  }

  const tbody = rows.map(r => {
    const src = (r.source_type || "internal").toLowerCase();
    const isEngaged = ["opened", "replied"].includes(r.status);
    const rowCls = ["clickable-row", r.status === "replied" ? "row-replied" : r.status === "opened" ? "row-opened" : ""].join(" ").trim();
    const safeEmail = (r.email || "").replace(/"/g, "&quot;");
    const safeName  = (r.carrier_name || "").replace(/"/g, "&quot;");
    return `<tr class="${rowCls}" data-email="${safeEmail}" data-carrier="${safeName}">
      <td class="rt-carrier">
        ${r.carrier_name || "—"}
        ${r.is_follow_up ? ' <span style="font-size:10px;color:#7c3aed;font-weight:700">(FU)</span>' : ""}
        ${isEngaged ? ' <span style="font-size:10px;color:#059669;font-weight:700">★</span>' : ""}
      </td>
      <td class="rt-email" title="${safeEmail}">${r.email || "—"}</td>
      <td class="rt-phone">${r.phone || "—"}</td>
      <td><span class="source-badge ${src}">${r.source || src}</span></td>
      <td><span class="stage-badge ${r.status}">${STAGE_ICONS[r.status] || ""} ${r.status}</span></td>
      <td class="rt-count">${r.attempt_number || 1}</td>
      <td style="font-size:11px;color:var(--muted)">${fmtDT(r.last_event_at)}</td>
      <td class="rt-reply" title="${(r.reply_snippet || "").replace(/"/g, "&quot;")}">${r.reply_snippet || "—"}</td>
    </tr>`;
  }).join("");

  wrap.innerHTML = `
    <table class="rtable">
      <thead><tr>
        <th>Carrier</th>
        <th>Email</th>
        <th>Phone</th>
        <th>Source</th>
        <th>Stage</th>
        <th style="text-align:center">Attempts</th>
        <th>Last Activity</th>
        <th>Reply</th>
      </tr></thead>
      <tbody>${tbody}</tbody>
    </table>
    <div class="rt-footer">${rows.length} recipient${rows.length !== 1 ? "s" : ""} shown</div>`;

  wrap.querySelectorAll(".clickable-row").forEach(tr => {
    tr.addEventListener("click", () => openCarrierThread(tr.dataset.email, tr.dataset.carrier));
  });
}

/* ── Export CSV ───────────────────────────────────────────────────── */
function exportCsv() {
  const rows = state.allResponses;
  if (!rows.length) return;
  const header = ["Carrier", "Email", "Phone", "Source", "Stage", "Attempts", "Last Activity", "Reply"].join(",");
  const body = rows.map(r => [
    `"${(r.carrier_name || "").replace(/"/g, '""')}"`,
    `"${(r.email        || "").replace(/"/g, '""')}"`,
    `"${(r.phone        || "").replace(/"/g, '""')}"`,
    `"${(r.source       || "").replace(/"/g, '""')}"`,
    r.status || "",
    r.attempt_number || 1,
    r.last_event_at ? new Date(r.last_event_at).toISOString() : "",
    `"${(r.reply_snippet || "").replace(/"/g, '""')}"`,
  ].join(",")).join("\n");

  const blob = new Blob([header + "\n" + body], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `campaign_${LANE_ID}_recipients.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ── Source conversion bars ───────────────────────────────────────── */
function renderSourceConv(sourceMetrics) {
  const grid = document.getElementById("source-conv-grid");
  const hasData = Object.values(sourceMetrics).some(v => v.total > 0);
  if (!hasData) {
    grid.innerHTML = `<div class="sconv-empty">Source data appears once emails are delivered.</div>`;
    return;
  }
  const rows = SRC_KEYS.map(key => {
    const label = SRC_LABEL[key];
    const d = sourceMetrics[label];
    if (!d || d.total === 0) return "";
    const replyPct = d.total ? Math.round(d.replied / d.total * 100) : 0;
    return `<div class="sconv-row">
      <div class="sconv-header">
        <span class="sconv-name"><span class="sconv-dot ${key}"></span>${label}</span>
        <span class="sconv-stats">${d.replied}/${d.total} replied · ${replyPct}%</span>
      </div>
      <div class="sconv-bar"><div class="sconv-fill ${key}" style="width:${replyPct}%"></div></div>
    </div>`;
  }).join("");
  grid.innerHTML = rows || `<div class="sconv-empty">No source data yet.</div>`;
}

/* ── Polling ──────────────────────────────────────────────────────── */
function startPolling() {
  if (state.pollTimer) return;
  state.pollTimer = setInterval(async () => {
    const m = await api(`/portal/lanes/${LANE_ID}/outreach`).catch(() => null);
    if (!m) return;
    const prev = state.metrics;
    state.metrics = m;
    renderLiveMetrics(m, prev);
    syncLog(m, prev);
    renderRecipientTable(m.carrier_responses || []);
    renderSourceConv(m.source_metrics || {});
    renderStageRail(stageIdx(m, state.lane));
    updateNavBtns(m, state.lane);
    if (m.campaign_ended) stopPolling();
  }, POLL_MS);
}
function stopPolling() {
  clearInterval(state.pollTimer); state.pollTimer = null;
  document.getElementById("log-live-indicator").innerHTML = "";
  document.getElementById("live-indicator").classList.add("hidden");
}

/* ── Follow-up ────────────────────────────────────────────────────── */
function openFollowUp() {
  const eligible = state.metrics?.follow_up_eligible_count || 0;
  document.getElementById("followup-eligible-msg").textContent =
    `${eligible} carrier${eligible !== 1 ? "s" : ""} haven't replied yet and will receive a follow-up email.`;
  document.getElementById("followup-subject").value = "";
  document.getElementById("followup-notes").value   = "";
  document.getElementById("followup-error").classList.add("hidden");
  document.getElementById("followup-dialog").showModal();
}
async function onFollowUpSend() {
  const btn   = document.getElementById("followup-send-btn");
  const errEl = document.getElementById("followup-error");
  errEl.classList.add("hidden");
  btn.disabled = true; btn.textContent = "Sending…";
  try {
    await api(`/portal/lanes/${LANE_ID}/outreach/follow-up`, {
      method: "POST",
      body: JSON.stringify({
        notes:            document.getElementById("followup-notes").value || "",
        subject_override: document.getElementById("followup-subject").value || "",
      }),
    });
    document.getElementById("followup-dialog").close();
    logAdd("Follow-up emails sent", "send");
    const m = await api(`/portal/lanes/${LANE_ID}/outreach`).catch(() => null);
    if (m) {
      state.metrics = m;
      renderLiveMetrics(m, null);
      renderRecipientTable(m.carrier_responses || []);
      updateNavBtns(m, state.lane);
    }
  } catch (err) {
    errEl.textContent = err?.payload?.detail || err?.message || "Failed to send follow-up.";
    errEl.classList.remove("hidden");
  } finally { btn.disabled = false; btn.textContent = "Send Follow-Up"; }
}

/* ── End campaign ─────────────────────────────────────────────────── */
async function onEndCampaign() {
  if (!confirm("Mark this lane as Covered / Completed? This will freeze metrics.")) return;
  try {
    await api(`/portal/lanes/${LANE_ID}/outreach/end`, { method: "POST", body: JSON.stringify({ reason: "covered" }) });
    stopPolling();
    logAdd("Campaign ended — lane marked as covered", "system");
    renderStageRail(4);
    document.getElementById("follow-up-btn").classList.add("hidden");
    document.getElementById("end-campaign-btn").classList.add("hidden");
    document.getElementById("lane-status-wrap").innerHTML =
      `<span class="lane-status-pill status-completed">Completed</span>`;
  } catch (err) { alert(err?.payload?.detail || "Failed to end campaign."); }
}

/* ── Carrier thread panel ─────────────────────────────────────────── */
const threadState = { email: null, carrierName: null };

function openCarrierThread(email, carrierName) {
  if (!email) return;
  threadState.email       = email;
  threadState.carrierName = carrierName || email;

  document.getElementById("thread-carrier-name").textContent = carrierName || email;
  document.getElementById("thread-carrier-email").textContent = email;
  document.getElementById("thread-messages").innerHTML =
    `<div class="thread-loading"><div class="thread-spinner"></div><span>Loading conversation…</span></div>`;
  document.getElementById("thread-reply-subject").value = "";
  document.getElementById("thread-reply-body").value    = "";
  document.getElementById("thread-reply-error").classList.add("hidden");

  document.getElementById("thread-overlay").classList.remove("hidden");
  document.getElementById("thread-panel").classList.remove("hidden");

  fetchCarrierThread(email);
}

function closeCarrierThread() {
  document.getElementById("thread-overlay").classList.add("hidden");
  document.getElementById("thread-panel").classList.add("hidden");
  threadState.email = null;
}

async function fetchCarrierThread(email) {
  try {
    const thread = await api(
      `/portal/lanes/${LANE_ID}/outreach/thread?email=${encodeURIComponent(email)}`
    );
    renderThreadMessages(thread);

    // Pre-fill reply subject from latest outbound message
    const lastOut = [...(thread.messages || [])].reverse().find(m => m.direction === "outbound");
    if (lastOut?.subject) {
      const subj = document.getElementById("thread-reply-subject");
      if (!subj.value) subj.value = `Re: ${lastOut.subject}`;
    }
  } catch (err) {
    document.getElementById("thread-messages").innerHTML =
      `<div class="thread-empty">Could not load conversation: ${err.message || "unknown error"}</div>`;
  }
}

function renderThreadMessages(thread) {
  const container = document.getElementById("thread-messages");
  if (!thread.messages || !thread.messages.length) {
    container.innerHTML = `<div class="thread-empty">No messages in this conversation yet.</div>`;
    return;
  }

  container.innerHTML = thread.messages.map(msg => {
    const isOut  = msg.direction === "outbound";
    const time   = fmtDT(msg.timestamp);
    const whoTxt = isOut ? "You" : (msg.from_name || thread.email);
    const bodyHtml = (msg.body || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");

    const statusBadge = isOut && msg.status
      ? `<span class="thread-msg-status ${msg.status}">${msg.status}</span>` : "";
    const subjectBadge = msg.subject
      ? `<span class="thread-msg-subject">${msg.subject.replace(/</g, "&lt;")}</span>` : "";
    const attemptLbl = isOut && msg.attempt_number
      ? `<div class="thread-msg-attempt">Attempt ${msg.attempt_number}</div>` : "";

    return `<div class="thread-msg ${isOut ? "outbound" : "inbound"}">
      <div class="thread-msg-meta">
        <span class="thread-msg-who">${whoTxt}</span>
        <span class="thread-msg-time">${time}</span>
        ${subjectBadge}
        ${statusBadge}
      </div>
      <div class="thread-msg-bubble">${bodyHtml || "<em style='opacity:.5'>No content</em>"}</div>
      ${attemptLbl}
    </div>`;
  }).join("");

  container.scrollTop = container.scrollHeight;
}

async function onSendCarrierReply() {
  const btn     = document.getElementById("thread-send-btn");
  const errEl   = document.getElementById("thread-reply-error");
  const subject = document.getElementById("thread-reply-subject").value.trim();
  const body    = document.getElementById("thread-reply-body").value.trim();

  errEl.classList.add("hidden");

  if (!subject || !body) {
    errEl.textContent = "Subject and body are required.";
    errEl.classList.remove("hidden");
    return;
  }

  btn.disabled = true; btn.textContent = "Sending…";
  try {
    await api(`/portal/lanes/${LANE_ID}/outreach/carrier-reply`, {
      method: "POST",
      body: JSON.stringify({
        email:        threadState.email,
        carrier_name: threadState.carrierName,
        subject,
        body,
      }),
    });

    document.getElementById("thread-reply-body").value    = "";
    document.getElementById("thread-reply-subject").value = "";
    logAdd(`Reply sent to ${threadState.carrierName || threadState.email}`, "send");

    // Refresh the thread so the sent reply appears
    await fetchCarrierThread(threadState.email);
  } catch (err) {
    errEl.textContent = err?.payload?.detail || err?.message || "Failed to send reply.";
    errEl.classList.remove("hidden");
  } finally {
    btn.disabled = false; btn.textContent = "Send Reply ↗";
  }
}

/* ── Per-source send limits ───────────────────────────────────────── */
function buildSourceLimitInputs(preview) {
  const section   = document.getElementById("source-limits-section");
  const inputsDiv = document.getElementById("source-limit-inputs");
  const bySource  = preview.recipient_count_by_source || {};
  const sources   = Object.entries(bySource).filter(([, c]) => c > 0);
  if (!sources.length) { section?.classList.add("hidden"); return; }

  // Default limits = max from each source
  sources.forEach(([label, count]) => {
    if (!(label in state.source_limits)) state.source_limits[label] = count;
  });

  inputsDiv.innerHTML = sources.map(([label, count]) => {
    const id = `limit-${label.replace(/\s+/g, "-")}`;
    const cur = state.source_limits[label] ?? count;
    return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
      <label for="${id}" style="font-size:12px;color:#475569;width:90px;flex-shrink:0">${label}</label>
      <input type="number" id="${id}" class="src-limit-input"
             data-source="${label}" data-max="${count}"
             value="${cur}" min="1" max="${count}"
             style="width:75px;padding:4px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;text-align:right" />
      <span style="font-size:11px;color:#94a3b8">/ ${count.toLocaleString()}</span>
    </div>`;
  }).join("");

  section?.classList.remove("hidden");
  inputsDiv.querySelectorAll(".src-limit-input").forEach(inp =>
    inp.addEventListener("input", _onLimitChange)
  );
  _updateLimitsTotal();
}

function _onLimitChange(e) {
  const label = e.target.dataset.source;
  const max   = parseInt(e.target.dataset.max, 10);
  let   val   = parseInt(e.target.value, 10);
  if (isNaN(val) || val < 1) val = 1;
  if (val > max) { val = max; e.target.value = val; }
  state.source_limits[label] = val;
  _updateLimitsTotal();
  const total = Object.values(state.source_limits).reduce((s, v) => s + v, 0);
  const sendBtn = document.getElementById("launch-campaign-btn");
  if (sendBtn && !sendBtn.classList.contains("hidden"))
    sendBtn.textContent = `🚀 Send Campaign — ${total.toLocaleString()} email${total !== 1 ? "s" : ""}`;
}

function _updateLimitsTotal() {
  const total = Object.values(state.source_limits).reduce((s, v) => s + v, 0);
  const el = document.getElementById("limits-total-count");
  if (el) el.textContent = total.toLocaleString();
}

/* ── Download outreach JSON ───────────────────────────────────────── */
async function downloadOutreachJson() {
  const btn = document.getElementById("download-outreach-btn");
  if (btn) { btn.disabled = true; btn.textContent = "⏳"; }
  try {
    const params = new URLSearchParams({
      include_internal:  state.sources.internal  ? "true" : "false",
      include_dat:       state.sources.dat        ? "true" : "false",
      include_crr_model: state.sources.crr_model  ? "true" : "false",
    });
    if (Object.keys(state.source_limits).length)
      params.set("source_limits", JSON.stringify(state.source_limits));

    const data = await api(`/portal/lanes/${LANE_ID}/outreach/export?${params}`);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `outreach_${LANE_ID}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Download failed: " + (err?.payload?.detail || err?.message || "unknown error"));
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "⬇ JSON"; }
  }
}


/* ── Init ─────────────────────────────────────────────────────────── */
async function init() {
  loadSession();

  const [laneData, metricsData] = await Promise.all([
    api(`/portal/lanes/${LANE_ID}`).catch(() => null),
    api(`/portal/lanes/${LANE_ID}/outreach`).catch(() => null),
  ]);

  if (!laneData) { document.getElementById("nav-label").textContent = "Lane not found"; return; }

  state.lane    = laneData.lane;
  state.metrics = metricsData;

  renderHeader(state.lane);

  const hasSentBatch = metricsData?.batch_id && (metricsData.sent > 0 || metricsData.batch_status === "sending");

  if (hasSentBatch) {
    // ── Live dashboard ────────────────────────────────────────────
    document.getElementById("live-dash").classList.remove("hidden");
    renderStageRail(stageIdx(metricsData, state.lane));
    renderLiveMetrics(metricsData, null);
    renderRecipientTable(metricsData.carrier_responses || []);
    renderSourceConv(metricsData.source_metrics || {});
    updateNavBtns(metricsData, state.lane);

    if (metricsData.sent_at)   logAdd(`Campaign sent — ${metricsData.sent} emails dispatched`, "send", metricsData.sent_at);
    if (metricsData.opened > 0) logAdd(`${metricsData.opened} opened`,  "open");
    if (metricsData.replied > 0) logAdd(`${metricsData.replied} replied`, "reply");

    if (!metricsData.campaign_ended) {
      document.getElementById("live-indicator").classList.remove("hidden");
      document.getElementById("log-live-indicator").innerHTML =
        `<span class="live-dot" style="background:#34d399"></span> Live`;
      startPolling();
    }

  } else {
    // ── Launch wizard ─────────────────────────────────────────────
    document.getElementById("wizard-shell").classList.remove("hidden");
    renderStageRail(0);

    const notesEl = document.getElementById("launch-notes");
    if (notesEl) notesEl.value = state.notes || state.lane.notes || "";
    renderSourceSummary();

    document.getElementById("add-manual-row-btn").addEventListener("click", () => addManualRow());
    document.getElementById("launch-notes").addEventListener("input", debouncedPreview);

    initEditEmailPanel();

    // Step 1 → 2
    document.getElementById("check-carriers-btn").addEventListener("click", onCheckCarriers);
    // Step 2 back
    document.getElementById("back-to-config-btn").addEventListener("click", () => setWizardStep(1));
    // Step 2 → 3 (send directly)
    document.getElementById("launch-campaign-btn").addEventListener("click", onLaunchCampaign);
    // Download outreach JSON
    document.getElementById("download-outreach-btn")?.addEventListener("click", downloadOutreachJson);

    // Start on the configure step so the user sees sources + internal filter
    debouncedPreview();
    setWizardStep(1);
  }

  // Recipient tab bar
  document.getElementById("rtab-bar")?.addEventListener("click", e => {
    const btn = e.target.closest(".rtab");
    if (!btn) return;
    document.querySelectorAll(".rtab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    state.activeTab = btn.dataset.tab;
    applyFilters();
  });

  // Source filter
  document.getElementById("source-filter")?.addEventListener("change", e => {
    state.sourceFilter = e.target.value;
    applyFilters();
  });

  // Search
  document.getElementById("carrier-search")?.addEventListener("input", e => {
    state.searchTerm = e.target.value;
    applyFilters();
  });

  // Export
  document.getElementById("export-btn")?.addEventListener("click", exportCsv);

  // Nav buttons
  document.getElementById("follow-up-btn").addEventListener("click", openFollowUp);
  document.getElementById("end-campaign-btn").addEventListener("click", onEndCampaign);

  // Thread slide-over
  document.getElementById("thread-close-btn").addEventListener("click", closeCarrierThread);
  document.getElementById("thread-overlay").addEventListener("click", closeCarrierThread);
  document.getElementById("thread-send-btn").addEventListener("click", onSendCarrierReply);

  // Follow-up dialog
  document.getElementById("followup-send-btn").addEventListener("click", onFollowUpSend);
  document.getElementById("followup-cancel-btn")?.addEventListener("click", () => document.getElementById("followup-dialog").close());
  document.getElementById("followup-close-btn")?.addEventListener("click", () => document.getElementById("followup-dialog").close());
}

init();
