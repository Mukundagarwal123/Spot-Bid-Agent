/* ── Constants ────────────────────────────────────────────────────── */
const LANE_ID    = window.__LANE_ID__;
const STAGES     = ["Build", "Preview", "Send", "Live", "Complete"];
const EQUIP_LABELS = { dry_van: "Dry Van", reefer: "Reefer", flatbed: "Flatbed", power_only: "Power Only", other: "Other" };
const SRC_LABEL    = { internal: "Internal", dat: "DAT", crr_model: "CRR Model", manual: "Manual Emails" };
const SRC_KEYS     = ["internal", "dat", "crr_model", "manual"];
/* WhatsApp can only be sent to these sources (never CRR Model). */
const WA_ELIGIBLE_SOURCES = ["internal", "dat", "manual"];
const WA_SOURCE_LABEL     = { internal: "Internal", dat: "DAT", manual: "Manual" };
const POLL_MS      = 5000;

/* ── State ────────────────────────────────────────────────────────── */
const state = {
  lane:                null,
  metrics:             null,
  prevMetrics:         null,
  sources:             { internal: true, dat: true, crr_model: false, manual: true },
  channels:            { email: true, whatsapp: true },
  whatsappSources:     ["internal", "dat", "manual"],
  whatsappTemplates:   [],
  notes:               "",
  previewData:         null,
  pollTimer:           null,
  activeTab:           "all",
  sourceFilter:        "all",
  channelFilter:       "all",
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
    if (!raw) return false;
    const d = JSON.parse(raw);
    if (d.sources) Object.assign(state.sources, d.sources);
    if (d.channels) Object.assign(state.channels, d.channels);
    if (d.whatsapp_source_types) state.whatsappSources = d.whatsapp_source_types;
    if (d.notes)   state.notes = d.notes;
    const manualRows = d.manual_recipients || d.manual_emails || [];
    if (manualRows.length) {
      state.sources.manual = true;
      manualRows.forEach(e => addManualRow(e));
      document.getElementById("manual-emails-section")?.classList.remove("hidden");
    }
    return true;
  } catch (_) {
    return false;
  }
}

function applyStoredCampaignConfig(config) {
  if (!config) return;
  if (config.sources) Object.assign(state.sources, config.sources);
  if (config.channels) Object.assign(state.channels, config.channels);
  if (config.whatsapp_source_types) state.whatsappSources = config.whatsapp_source_types;
  if (config.manual_recipients?.length) {
    state.sources.manual = true;
    config.manual_recipients.forEach(entry => addManualRow(entry));
  }
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

  // Read-only reminder of which channels this campaign uses (set in the modal).
  const chEl = document.getElementById("wz-channel-summary");
  if (chEl) {
    const parts = [];
    if (state.channels.email)    parts.push(`<span class="wz-chan-chip email">✉ Email</span>`);
    if (state.channels.whatsapp) parts.push(`<span class="wz-chan-chip whatsapp">◉ WhatsApp</span>`);
    chEl.innerHTML = parts.length
      ? `<span class="wz-chan-lead">Sending via</span>${parts.join("")}`
      : "";
  }
  // Show/hide internal filter toggle based on whether internal source is selected
  document.getElementById("internal-filter-section")?.classList.toggle("hidden", !state.sources.internal);
  document.getElementById("manual-emails-section")?.classList.toggle("hidden", !state.sources.manual);
}

function addManualRow(entry = null) {
  const container = document.getElementById("manual-email-rows");
  const row = document.createElement("div");
  row.className = "manual-row";
  row.innerHTML = `
    <input type="text"  class="manual-carrier-name" placeholder="Carrier Name"  value="${entry?.carrier_name || ""}" />
    <input type="email" class="manual-email-addr"   placeholder="Email address" value="${entry?.email || ""}" />
    <input type="tel" class="manual-phone" placeholder="+1 805 555 1212" value="${entry?.phone || ""}" />
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

function collectManualPhones() {
  return [...document.querySelectorAll(".manual-row")].map(r => ({
    carrier_name: r.querySelector(".manual-carrier-name")?.value?.trim() || "",
    phone:        r.querySelector(".manual-phone")?.value?.trim() || "",
  })).filter(entry => entry.phone);
}

function selectedWhatsAppSources() {
  return [...document.querySelectorAll("[data-wa-source]:checked")].map(input => input.dataset.waSource);
}

function campaignPayload() {
  return {
    include_internal:  state.sources.internal,
    include_dat:       state.sources.dat,
    include_crr_model: state.sources.crr_model,
    send_email:        state.channels.email,
    send_whatsapp:     state.channels.whatsapp,
    whatsapp_template_name: document.getElementById("whatsapp-template")?.value || "",
    whatsapp_language: "en_US",
    whatsapp_source_types: selectedWhatsAppSources(),
    test_mode:         false,
    manual_emails:     collectManualRows(),
    manual_phones:     collectManualPhones(),
    notes:             state.notes,
  };
}

/* Render the WhatsApp "send to" checkboxes — only for eligible sources
   (internal / DAT / manual) that the user actually selected. */
function renderWhatsAppSources() {
  const grid = document.getElementById("wa-source-grid");
  if (!grid) return;
  const eligible = WA_ELIGIBLE_SOURCES.filter(k => state.sources[k]);
  if (!eligible.length) {
    grid.innerHTML = `<div class="wa-source-empty">No WhatsApp-eligible sources selected. Pick Internal, DAT, or add manual numbers.</div>`;
    return;
  }
  // Keep only selections that are still eligible + selected.
  state.whatsappSources = eligible.filter(k => state.whatsappSources.includes(k));
  if (!state.whatsappSources.length) state.whatsappSources = [...eligible];
  grid.innerHTML = eligible.map(k => {
    const checked = state.whatsappSources.includes(k) ? "checked" : "";
    return `<label class="wa-source-chip"><input type="checkbox" data-wa-source="${k}" ${checked} /><span>${WA_SOURCE_LABEL[k]}</span></label>`;
  }).join("");
  grid.querySelectorAll("[data-wa-source]").forEach(input =>
    input.addEventListener("change", () => { state.whatsappSources = selectedWhatsAppSources(); })
  );
}

/* Show preview tabs only for the channels that are enabled; when a single
   channel is selected, hide the other tab and default to the active one. */
function updatePreviewChannelTabs() {
  const tabs = document.querySelector(".preview-channel-tabs");
  const emailTab = document.querySelector('.preview-channel-tab[data-preview-channel="email"]');
  const waTab    = document.querySelector('.preview-channel-tab[data-preview-channel="whatsapp"]');
  if (!emailTab || !waTab) return;
  const emailOn = state.channels.email;
  const waOn    = state.channels.whatsapp;
  emailTab.classList.toggle("hidden", !emailOn);
  waTab.classList.toggle("hidden", !waOn);
  // Only one visible tab → collapse the pill styling into a plain label.
  tabs?.classList.toggle("single", (emailOn ? 1 : 0) + (waOn ? 1 : 0) === 1);
  // If the currently-active tab is now hidden, switch to an available one.
  const activeTab = document.querySelector(".preview-channel-tab.active:not(.hidden)");
  if (!activeTab) showPreviewChannel(emailOn ? "email" : "whatsapp");
}

function showPreviewChannel(channel) {
  document.querySelectorAll(".preview-channel-tab").forEach(item =>
    item.classList.toggle("active", item.dataset.previewChannel === channel));
  const showWhatsApp = channel === "whatsapp";
  document.getElementById("email-preview-content")?.classList.toggle("hidden", showWhatsApp);
  document.getElementById("whatsapp-preview-content")?.classList.toggle("hidden", !showWhatsApp);
  // Edit-email only makes sense on the email tab.
  document.getElementById("edit-email-btn")?.classList.toggle("hidden", showWhatsApp);
}

async function initCampaignChannels() {
  // Channels are chosen in the New Campaign modal — the wizard just honours them.
  document.getElementById("whatsapp-section")?.classList.toggle("hidden", !state.channels.whatsapp);
  updatePreviewChannelTabs();
  renderWhatsAppSources();

  const select = document.getElementById("whatsapp-template");
  try {
    const result = await api("/api/whatsapp/templates");
    state.whatsappTemplates = result.templates || [];
    select.innerHTML = state.whatsappTemplates.length
      ? `<option value="" disabled selected>Select an approved template…</option>${state.whatsappTemplates.map(template =>
          `<option value="${template.name}" data-language="${template.language || "en_US"}">${template.label || template.name}</option>`
        ).join("")}`
      : `<option value="" disabled selected>No approved templates configured</option>`;
    const threadSelect = document.getElementById("thread-template-select");
    if (threadSelect) {
      threadSelect.innerHTML = `<option value="">Use free-form reply (24-hour window)</option>${state.whatsappTemplates.map(template =>
        `<option value="${template.name}">${template.label || template.name}</option>`
      ).join("")}`;
    }
  } catch (_) {
    select.innerHTML = `<option value="" disabled selected>Templates unavailable</option>`;
  }

  select.addEventListener("change", () => {
    const selected = state.whatsappTemplates.find(template => template.name === select.value);
    document.getElementById("wa-template-preview-text").textContent =
      selected?.preview || selected?.label || (select.value ? `Template: ${select.value}` : "Choose an approved template to preview the campaign message.");
    // Clear the step-1 template error the moment a valid template is picked.
    if (select.value) document.getElementById("wizard-step1-error")?.classList.add("hidden");
    if (state.previewData) {
      const sendBtn = document.getElementById("launch-campaign-btn");
      const whatsappCount = state.previewData.whatsapp_recipient_count || 0;
      sendBtn.disabled = state.channels.whatsapp && whatsappCount > 0 && !select.value;
      if (!sendBtn.disabled) document.getElementById("wizard-step2-error")?.classList.add("hidden");
    }
  });

  document.querySelectorAll(".preview-channel-tab").forEach(tab => {
    tab.addEventListener("click", () => showPreviewChannel(tab.dataset.previewChannel));
  });
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
  if (!state.channels.email && !state.channels.whatsapp) {
    errEl.textContent = "Select at least one campaign channel.";
    errEl.classList.remove("hidden");
    return;
  }
  // Validate the WhatsApp template here — before advancing — not on the next step.
  if (state.channels.whatsapp) {
    const tpl = document.getElementById("whatsapp-template")?.value;
    if (!tpl) {
      errEl.textContent = "Select an approved WhatsApp template before continuing.";
      errEl.classList.remove("hidden");
      document.getElementById("whatsapp-template")?.focus();
      return;
    }
  }

  state.notes = document.getElementById("launch-notes").value || "";
  state.source_limits = {};  // reset limits on each new fetch
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

        // CRR Model can take much longer than internal/dat.
        // If other faster sources are selected and all settled, don't let CRR block.
        // But if CRR is the ONLY selected source, we must wait for it.
        const hasFasterSources = nonManualSources.some(k => k !== "crr_model");
        const blockingUnresolved = nonManualSources.filter(k => {
          if (k === "dat") return false;                          // dat pending tracked separately
          if (k === "crr_model" && hasFasterSources) return false; // crr doesn't block if faster sources exist
          return !resolved.has(k);
        });
        if (!counts.dat_pending && blockingUnresolved.length === 0) break;
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
      body: JSON.stringify(campaignPayload()),
    });
    state.previewData = preview;

    activeSources.forEach(k => {
      const count = preview.recipient_count_by_source?.[SRC_LABEL[k]] ?? 0;
      if (count > 0) {
        _ftSetState(k, "ready", count, `${count} contact${count !== 1 ? "s" : ""} ready`);
      } else {
        _ftSetState(k, null, 0, "No eligible email or WhatsApp contacts");
      }
    });

    const total   = preview.recipient_count;
    const contacts = preview.unique_contact_count ?? total;
    const emailCount = preview.email_recipient_count ?? total;
    const whatsappCount = preview.whatsapp_recipient_count ?? 0;
    const bounced = preview.bounced_count ?? 0;

    if (total > 0) {
      const bouncedNote = bounced > 0
        ? `<div class="wz-skipped-notice">${bounced} email${bounced !== 1 ? "s" : ""} skipped — previously bounced</div>`
        : "";
      summaryEl.innerHTML = `<div class="wz-total-num">${contacts}</div>
        <div class="wz-total-label">unique contact${contacts !== 1 ? "s" : ""} ready</div>
        <div class="wz-channel-counts">✉ ${emailCount} email &nbsp; · &nbsp; ◉ ${whatsappCount} WhatsApp</div>
        ${bouncedNote}`;
      summaryEl.classList.remove("hidden");
      buildSourceLimitInputs(preview);
      sendBtn.textContent = `Send Campaign — ${emailCount} email · ${whatsappCount} WhatsApp`;
      const templateMissing = state.channels.whatsapp && whatsappCount > 0 && !document.getElementById("whatsapp-template")?.value;
      sendBtn.disabled = templateMissing;
      if (templateMissing) {
        document.getElementById("wizard-step2-error").textContent = "Select an approved WhatsApp template before sending.";
        document.getElementById("wizard-step2-error").classList.remove("hidden");
      }
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
        ...campaignPayload(),
        source_limits: Object.keys(state.source_limits).length ? state.source_limits : null,
      }),
    });

    document.getElementById("wizard-shell").classList.add("hidden");
    document.getElementById("live-dash").classList.remove("hidden");
    logAdd("Campaign launched — email and WhatsApp outreach dispatched", "send");
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
    sendBtn.textContent = "Send Campaign";
  }
}

/* ── Live metrics (bifurcated by channel) ─────────────────────────── */
const CHANNEL_META = {
  email:    { label: "Email",    icon: "✉", openLabel: "Opened", lastLabel: "Bounced", lastKey: "bounced", accent: "email" },
  whatsapp: { label: "WhatsApp", icon: "◉", openLabel: "Read",   lastLabel: "Failed",  lastKey: "failed",  accent: "whatsapp" },
};

/* Which channels to render funnels for: any channel that has actually sent,
   else fall back to the configured selection. */
function activeChannels(m) {
  const list = [];
  if ((m?.channel_metrics?.email?.sent || 0) > 0)    list.push("email");
  if ((m?.channel_metrics?.whatsapp?.sent || 0) > 0) list.push("whatsapp");
  if (list.length) return list;
  if (state.channels.email)    list.push("email");
  if (state.channels.whatsapp) list.push("whatsapp");
  return list.length ? list : ["email"];
}

function _funnelSkeleton(ch) {
  const meta = CHANNEL_META[ch];
  const stages = [
    { key: "sent",      label: "Sent",           cls: "blue"  },
    { key: "delivered", label: "Delivered",      cls: "green" },
    { key: "opened",    label: meta.openLabel,   cls: "amber" },
    { key: "replied",   label: "Replied",        cls: "teal"  },
    { key: meta.lastKey, label: meta.lastLabel,  cls: "red", last: true },
  ];
  const cells = stages.map((s, i) => `
    ${i > 0 ? '<div class="lm-arrow">›</div>' : ""}
    <div class="lm-card" id="mf-${ch}-card-${s.key}">
      <div class="lm-num ${s.cls}" id="mf-${ch}-${s.key}">—</div>
      ${s.last ? "" : `<div class="lm-sub" id="mf-${ch}-sub-${s.key}"></div>`}
      <div class="lm-label">${s.label}</div>
    </div>`).join("");
  return `
    <div class="mf-funnel ${meta.accent}">
      <div class="mf-head">
        <span class="mf-chan-icon">${meta.icon}</span>
        <span class="mf-chan-name">${meta.label}</span>
        <span class="mf-chan-total" id="mf-${ch}-total">0 sent</span>
      </div>
      <div class="live-metrics-row">${cells}</div>
    </div>`;
}

let _funnelsKey = null;
function renderLiveMetrics(m, prev) {
  const channels = activeChannels(m);
  const key = channels.join(",");
  const wrap = document.getElementById("live-metrics");
  if (wrap && _funnelsKey !== key) {
    wrap.innerHTML = channels.map(_funnelSkeleton).join("");
    wrap.classList.toggle("multi", channels.length > 1);
    _funnelsKey = key;
  }

  channels.forEach(ch => {
    const cm   = m.channel_metrics?.[ch] || {};
    const pcm  = prev?.channel_metrics?.[ch] || null;
    const meta = CHANNEL_META[ch];
    const sent = cm.sent || 0;
    const vals = {
      sent, delivered: cm.delivered || 0, opened: cm.opened || 0,
      replied: cm.replied || 0, [meta.lastKey]: cm[meta.lastKey] || 0,
    };
    const subs = {
      delivered: `${pct(vals.delivered, sent)} of sent`,
      opened:    `${pct(vals.opened, sent)} of sent`,
      replied:   `${pct(vals.replied, sent)} of sent`,
    };
    const totalEl = document.getElementById(`mf-${ch}-total`);
    if (totalEl) totalEl.textContent = `${sent} sent`;

    Object.entries(vals).forEach(([k, v]) => {
      const numEl = document.getElementById(`mf-${ch}-${k}`);
      if (numEl) numEl.textContent = v;
      const subEl = document.getElementById(`mf-${ch}-sub-${k}`);
      if (subEl && subs[k] != null) subEl.textContent = subs[k];
      if (pcm && (pcm[k] || 0) !== v) {
        const card = document.getElementById(`mf-${ch}-card-${k}`);
        if (card) { card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash"); }
      }
    });
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
  renderHotLeads(responses);
  applyFilters();
}

/* ── Hot Leads: carriers who replied — the broker's call-now list ──── */
function renderHotLeads(responses) {
  const list    = document.getElementById("hot-leads-list");
  const countEl = document.getElementById("hot-leads-count");
  if (!list) return;
  const leads = (responses || [])
    .filter(r => r.status === "replied")
    .sort((a, b) => (b.last_event_at || "").localeCompare(a.last_event_at || ""));
  if (countEl) countEl.textContent = leads.length;

  if (!leads.length) {
    list.innerHTML = `<div class="hl-empty">Carriers who reply will surface here first — call them before they take another load.</div>`;
    return;
  }

  list.innerHTML = leads.map(r => {
    const channel   = r.channel || "email";
    const src       = (r.source_type || "internal").toLowerCase();
    const safeEmail = (r.email || "").replace(/"/g, "&quot;");
    const safePhone = (r.phone || "").replace(/"/g, "&quot;");
    const safeName  = (r.carrier_name || "").replace(/"/g, "&quot;");
    const contact   = channel === "whatsapp" ? (r.phone || "") : (r.email || "");
    const snippet   = (r.reply_snippet || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<div class="hl-row" data-email="${safeEmail}" data-phone="${safePhone}" data-channel="${channel}" data-carrier="${safeName}">
      <div class="hl-top">
        <span class="hl-name">${r.carrier_name || contact || "—"}</span>
        <span class="channel-badge ${channel}">${channel === "whatsapp" ? "◉" : "✉"}</span>
      </div>
      ${snippet ? `<div class="hl-snippet">"${snippet}"</div>` : `<div class="hl-snippet muted">Replied — open the thread to read.</div>`}
      <div class="hl-meta">
        <span class="source-badge ${src}">${r.source || src}</span>
        <span class="hl-time">${fmtDT(r.last_event_at)}</span>
      </div>
    </div>`;
  }).join("");

  list.querySelectorAll(".hl-row").forEach(row => {
    row.addEventListener("click", () => openCarrierThread({
      email: row.dataset.email,
      phone: row.dataset.phone,
      channel: row.dataset.channel,
      carrierName: row.dataset.carrier,
    }));
  });
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

  if (state.channelFilter !== "all")
    rows = rows.filter(r => (r.channel || "email") === state.channelFilter);

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
    const safePhone = (r.phone || "").replace(/"/g, "&quot;");
    const safeName  = (r.carrier_name || "").replace(/"/g, "&quot;");
    const channel = r.channel || "email";
    return `<tr class="${rowCls}" data-email="${safeEmail}" data-phone="${safePhone}" data-channel="${channel}" data-carrier="${safeName}">
      <td class="rt-carrier">
        ${r.carrier_name || "—"}
        ${r.is_follow_up ? ' <span style="font-size:10px;color:#7c3aed;font-weight:700">(FU)</span>' : ""}
        ${isEngaged ? ' <span style="font-size:10px;color:#059669;font-weight:700">★</span>' : ""}
      </td>
      <td class="rt-email" title="${safeEmail}">${r.email || "—"}</td>
      <td class="rt-phone">${r.phone || "—"}</td>
      <td><span class="channel-badge ${channel}">${channel === "whatsapp" ? "◉ WhatsApp" : "✉ Email"}</span></td>
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
        <th>Channel</th>
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
    tr.addEventListener("click", () => openCarrierThread({
      email: tr.dataset.email,
      phone: tr.dataset.phone,
      channel: tr.dataset.channel,
      carrierName: tr.dataset.carrier,
    }));
  });
}

/* ── Export CSV ───────────────────────────────────────────────────── */
function exportCsv() {
  const rows = state.allResponses;
  if (!rows.length) return;
  const header = ["Carrier", "Email", "Phone", "Channel", "Source", "Stage", "Attempts", "Last Activity", "Reply"].join(",");
  const body = rows.map(r => [
    `"${(r.carrier_name || "").replace(/"/g, '""')}"`,
    `"${(r.email        || "").replace(/"/g, '""')}"`,
    `"${(r.phone        || "").replace(/"/g, '""')}"`,
    r.channel || "email",
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
const threadState = { email: null, phone: null, channel: "email", carrierName: null };

function openCarrierThread({ email = "", phone = "", channel = "email", carrierName = "" }) {
  const address = channel === "whatsapp" ? phone : email;
  if (!address) return;
  threadState.email = email;
  threadState.phone = phone;
  threadState.channel = channel;
  threadState.carrierName = carrierName || address;

  document.getElementById("thread-carrier-name").textContent = carrierName || address;
  document.getElementById("thread-carrier-email").textContent =
    channel === "whatsapp" ? `WhatsApp · ${phone}` : email;
  document.getElementById("thread-messages").innerHTML =
    `<div class="thread-loading"><div class="thread-spinner"></div><span>Loading conversation…</span></div>`;
  document.getElementById("thread-reply-subject").value = "";
  document.getElementById("thread-reply-body").value    = "";
  document.getElementById("thread-reply-error").classList.add("hidden");

  document.getElementById("thread-overlay").classList.remove("hidden");
  document.getElementById("thread-panel").classList.remove("hidden");

  const isWhatsApp = channel === "whatsapp";
  document.getElementById("thread-reply-subject").classList.toggle("hidden", isWhatsApp);
  document.getElementById("thread-template-select").classList.toggle("hidden", !isWhatsApp);
  document.getElementById("thread-reply-body").placeholder = isWhatsApp
    ? "Type a reply, or choose a template if the 24-hour window has closed…"
    : "Type your reply…";
  fetchCarrierThread();
}

function closeCarrierThread() {
  document.getElementById("thread-overlay").classList.add("hidden");
  document.getElementById("thread-panel").classList.add("hidden");
  threadState.email = null;
  threadState.phone = null;
}

async function fetchCarrierThread() {
  try {
    const query = threadState.channel === "whatsapp"
      ? `channel=whatsapp&phone=${encodeURIComponent(threadState.phone)}`
      : `channel=email&email=${encodeURIComponent(threadState.email)}`;
    const thread = await api(`/portal/lanes/${LANE_ID}/outreach/thread?${query}`);
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
    const whoTxt = isOut ? "You" : (msg.from_name || thread.email || thread.phone);
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
  const templateName = document.getElementById("thread-template-select").value;

  errEl.classList.add("hidden");

  if (threadState.channel === "email" && (!subject || !body)) {
    errEl.textContent = "Subject and body are required.";
    errEl.classList.remove("hidden");
    return;
  }
  if (threadState.channel === "whatsapp" && !body && !templateName) {
    errEl.textContent = "Enter a reply or choose an approved template.";
    errEl.classList.remove("hidden");
    return;
  }

  btn.disabled = true; btn.textContent = "Sending…";
  try {
    if (threadState.channel === "whatsapp") {
      await api(`/portal/lanes/${LANE_ID}/outreach/whatsapp-reply`, {
        method: "POST",
        body: JSON.stringify({ phone: threadState.phone, body, template_name: templateName }),
      });
    } else {
      await api(`/portal/lanes/${LANE_ID}/outreach/carrier-reply`, {
        method: "POST",
        body: JSON.stringify({
          email: threadState.email,
          carrier_name: threadState.carrierName,
          subject,
          body,
        }),
      });
    }

    document.getElementById("thread-reply-body").value    = "";
    document.getElementById("thread-reply-subject").value = "";
    document.getElementById("thread-template-select").value = "";
    logAdd(`Reply sent to ${threadState.carrierName || threadState.email || threadState.phone}`, "send");

    // Refresh the thread so the sent reply appears
    await fetchCarrierThread();
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
    sendBtn.textContent = `Send Campaign — up to ${total.toLocaleString()} contacts per channel`;
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
  const sessionLoaded = loadSession();

  const [laneData, metricsData] = await Promise.all([
    api(`/portal/lanes/${LANE_ID}`).catch(() => null),
    api(`/portal/lanes/${LANE_ID}/outreach`).catch(() => null),
  ]);

  if (!laneData) { document.getElementById("nav-label").textContent = "Lane not found"; return; }

  state.lane    = laneData.lane;
  state.metrics = metricsData;
  if (!sessionLoaded) applyStoredCampaignConfig(state.lane.campaign_config);
  await initCampaignChannels();

  renderHeader(state.lane);

  const hasSentBatch = metricsData?.batch_id && (metricsData.sent > 0 || metricsData.batch_status === "sent" || metricsData.batch_status === "sending");

  if (hasSentBatch) {
    // ── Live dashboard ────────────────────────────────────────────
    document.getElementById("live-dash").classList.remove("hidden");
    renderStageRail(stageIdx(metricsData, state.lane));
    renderLiveMetrics(metricsData, null);
    renderRecipientTable(metricsData.carrier_responses || []);
    renderSourceConv(metricsData.source_metrics || {});
    updateNavBtns(metricsData, state.lane);

    if (metricsData.sent_at)   logAdd(`Campaign sent — ${metricsData.sent} messages dispatched`, "send", metricsData.sent_at);
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
    if (state.sources.manual && !document.querySelector(".manual-row")) addManualRow();

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

  document.getElementById("channel-filter")?.addEventListener("change", e => {
    state.channelFilter = e.target.value;
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
