/* ── State ─────────────────────────────────────────────────────────── */
const state = {
  tab: "active",
  lanes: [],
  crm: [],
  pendingLaneId: null,
  // modal source toggles
  modalSources: { internal: true, dat: true, crr_model: true, manual: false },
  // custom email body text (Edit Text tab)
  customEmailText: null,
};

/* ── API helper ────────────────────────────────────────────────────── */
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(json?.detail || "Request failed");
    err.payload = json;
    throw err;
  }
  return json;
}

/* ── Formatters ────────────────────────────────────────────────────── */
const EQUIP_LABELS = {
  dry_van: "Dry Van", reefer: "Reefer", flatbed: "Flatbed",
  power_only: "Power Only", other: "Other",
};
function fmtDate(v) {
  if (!v) return "—";
  return new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
function fmtDateTime(v) {
  if (!v) return "—";
  return new Date(v).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
function inferStatus(lane) {
  const raw = lane.status;
  if (raw === "closed" || raw === "completed") return "completed";
  const hasCampaign = (lane.metrics_preview?.carriers_contacted ?? 0) > 0;
  return hasCampaign ? "active" : "draft";
}

/* ── Lane table ────────────────────────────────────────────────────── */
function renderLanesGrid() {
  const grid = document.getElementById("lanes-grid");

  // Filter: active tab shows draft + active; completed tab shows completed only
  const rows = state.lanes
    .filter(l => {
      const s = inferStatus(l);
      return state.tab === "completed" ? s === "completed" : s !== "completed";
    })
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  if (!rows.length) {
    grid.innerHTML = `<div class="lanes-empty">No ${state.tab === "completed" ? "completed" : "active"} lanes yet. Click <strong>+ Add Lane</strong> to get started.</div>`;
    return;
  }

  const STATUS_LABEL = { draft: "Draft", active: "Active", completed: "Completed" };

  grid.innerHTML = `
    <table class="lanes-table">
      <thead>
        <tr>
          <th>Lane</th>
          <th>Status</th>
          <th>Equipment</th>
          <th>Pickup</th>
          <th>${state.tab === "completed" ? "Completed" : "Sent / Created"}</th>
          <th class="num-col">Reached</th>
          <th class="num-col">Responses</th>
          <th class="num-col">Rate</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(lane => {
          const status    = inferStatus(lane);
          const equip     = EQUIP_LABELS[lane.equipment_type] || lane.equipment_type;
          const contacted = lane.metrics_preview?.carriers_contacted ?? 0;
          const responded = lane.metrics_preview?.carriers_responded ?? 0;
          const rate      = contacted > 0 ? Math.round(responded / contacted * 100) + "%" : "—";
          const dateCol   = contacted > 0 ? fmtDateTime(lane.last_activity_at) : `Created ${fmtDate(lane.created_at)}`;
          return `
            <tr class="lane-row" data-lane-id="${lane.lane_id}" tabindex="0" role="button">
              <td class="lt-route">${lane.label}</td>
              <td><span class="lane-pill ${status}">${STATUS_LABEL[status]}</span></td>
              <td class="lt-equip">${equip}</td>
              <td class="lt-date">${fmtDate(lane.pickup_date)}</td>
              <td class="lt-sent">${dateCol}</td>
              <td class="num-col">${contacted > 0 ? contacted : "—"}</td>
              <td class="num-col">${responded > 0 ? responded : "—"}</td>
              <td class="num-col ${responded > 0 ? "rate-good" : ""}">${rate}</td>
            </tr>`;
        }).join("")}
      </tbody>
    </table>`;

  grid.querySelectorAll(".lane-row").forEach(row => {
    const go = () => window.location.href = `/lanes/${row.dataset.laneId}`;
    row.addEventListener("click", go);
    row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") go(); });
  });
}

/* ── CRM table ─────────────────────────────────────────────────────── */
function renderCrmTable() {
  const tbody = document.getElementById("crm-body");
  if (!state.crm.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:#5e748a">No carrier CRM data yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.crm.map(c => `
    <tr>
      <td>${c.carrier_name}</td>
      <td>${c.times_contacted}</td>
      <td>${c.times_responded}</td>
      <td>${c.response_rate.toFixed(1)}%</td>
      <td><span class="chip ${c.preferred_channel}">${c.preferred_channel}</span></td>
      <td>${fmtDateTime(c.last_contacted_at)}</td>
    </tr>`).join("");
}

/* ── Tab switching ─────────────────────────────────────────────────── */
function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".left-tab").forEach(btn =>
    btn.classList.toggle("active", btn.dataset.tab === tab)
  );
  const laneView = tab !== "crm";
  document.getElementById("lane-workspace").classList.toggle("hidden", !laneView);
  document.getElementById("crm-workspace").classList.toggle("hidden", laneView);
  if (laneView) {
    document.getElementById("workspace-title").textContent =
      tab === "active" ? "Active Lanes" : "Completed Lanes";
    document.getElementById("workspace-sub").textContent =
      tab === "active"
        ? "All open campaigns and drafts — click a row to open."
        : "Lanes where outreach has been wrapped up.";
    renderLanesGrid();
  } else {
    renderCrmTable();
  }
}

/* ── Modal: client-side email preview ──────────────────────────────── */
function buildModalPreviewHtml() {
  const originCity  = document.getElementById("f-origin-city")?.value  || "Origin";
  const originState = document.getElementById("f-origin-state")?.value || "ST";
  const destCity    = document.getElementById("f-dest-city")?.value    || "Destination";
  const destState   = document.getElementById("f-dest-state")?.value   || "ST";
  const originZip   = document.getElementById("f-origin-zip")?.value   || "";
  const destZip     = document.getElementById("f-dest-zip")?.value     || "";
  const equip = EQUIP_LABELS[document.getElementById("f-equip")?.value] || "Dry Van";
  const pickup = fmtDate(document.getElementById("f-pickup")?.value);
  const notes  = document.getElementById("f-notes")?.value?.trim() || "";

  const origin = `${originCity}, ${originState}${originZip ? " " + originZip : ""}`;
  const dest   = `${destCity}, ${destState}${destZip ? " " + destZip : ""}`;

  const customText = state.customEmailText;
  const mainBody = customText != null ? customText.replace(/\n/g, "<br>") :
    `We have an active spot freight opportunity that matches your operating area.
    We're moving quickly to cover this load and would appreciate your best rate.`.replace(/\n/g, "<br>");

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
  <table width="520" cellpadding="0" cellspacing="0" border="0"
         style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.09)">
    <tr><td style="background:#0f2f47;padding:22px 28px">
      <div style="font-size:18px;font-weight:800;color:#fff">T3RA Logistics — Spot Bid Opportunity</div>
      <div style="font-size:12px;color:#abc3d9;margin-top:5px;font-weight:600">${origin} &rarr; ${dest}</div>
      <div style="font-size:10px;color:#7ea8c6;margin-top:6px;font-style:italic">Your Freight. Our Mission. &middot; Veteran-Owned &amp; Operated</div>
    </td></tr>
    <tr><td style="padding:24px 28px">
      <p style="margin:0 0 10px;font-size:15px;font-weight:700;color:#12263a">Hi Sample Carrier,</p>
      <p style="margin:0 0 18px;font-size:13px;color:#344054;line-height:1.65">${mainBody}</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:#f0f7ff;border-left:4px solid #1d4ed8;border-radius:0 10px 10px 0;margin-bottom:20px">
        <tr><td style="padding:14px 18px">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr><td style="font-size:12px;color:#5e748a;padding:2px 0;width:110px;font-weight:600">Origin</td><td style="font-size:12px;color:#12263a;font-weight:700">${origin}</td></tr>
            <tr><td style="font-size:12px;color:#5e748a;padding:2px 0;font-weight:600">Destination</td><td style="font-size:12px;color:#12263a;font-weight:700">${dest}</td></tr>
            <tr><td style="font-size:12px;color:#5e748a;padding:2px 0;font-weight:600">Equipment</td><td style="font-size:12px;color:#12263a">${equip}</td></tr>
            ${pickup ? `<tr><td style="font-size:12px;color:#5e748a;padding:2px 0;font-weight:600">Pickup</td><td style="font-size:12px;color:#12263a">${pickup}</td></tr>` : ""}
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
    <tr><td style="background:#f8fbff;padding:12px 28px;border-top:1px solid #e2e8f0">
      <p style="margin:0;font-size:10px;color:#94a3b8">T3RA Logistics &middot; Spot Bid Operations</p>
    </td></tr>
  </table>
</td></tr></table>
</body></html>`;
}

let _previewTimer = null;
function schedulePreviewUpdate() {
  clearTimeout(_previewTimer);
  _previewTimer = setTimeout(() => {
    const iframe = document.getElementById("lm-preview-iframe");
    if (iframe) iframe.srcdoc = buildModalPreviewHtml();
    // also sync default text to edit pane if not yet customised
    const ta = document.getElementById("lm-email-body-text");
    if (ta && state.customEmailText === null) {
      ta.value = buildDefaultEmailBodyText();
    }
  }, 120);
}

function buildDefaultEmailBodyText() {
  return [
    "Hi [Carrier Name],",
    "",
    "We have an active spot freight opportunity that matches your operating area.",
    "We're moving quickly to cover this load and would appreciate your best rate.",
    "",
    "Reply with your available capacity and all-in rate and we'll follow up within the hour.",
    "",
    "Thank you,",
    "T3RA Logistics — Spot Bid Operations",
  ].join("\n");
}

/* ── Modal source card toggling ────────────────────────────────────── */
function initModalSources() {
  document.querySelectorAll(".src-card").forEach(card => {
    const src = card.dataset.src;
    // set initial visual state
    card.classList.toggle("on", !!state.modalSources[src]);
    card.addEventListener("click", () => {
      state.modalSources[src] = !state.modalSources[src];
      card.classList.toggle("on", state.modalSources[src]);
      if (src === "manual") {
        const section = document.getElementById("manual-emails-section");
        section.classList.toggle("hidden", !state.modalSources.manual);
        if (state.modalSources.manual) {
          const rows = document.getElementById("manual-email-rows");
          if (!rows.querySelector(".manual-email-row")) addManualEmailRow(rows);
        }
      }
    });
  });
}

/* ── Manual email row helpers ──────────────────────────────────────── */
function addManualEmailRow(container) {
  const row = document.createElement("div");
  row.className = "manual-email-row";
  row.innerHTML = `
    <input type="text" class="manual-carrier-name" placeholder="Carrier Name" />
    <input type="email" class="manual-email-addr" placeholder="Email address" />
    <button type="button" class="remove-manual-row">×</button>`;
  row.querySelector(".remove-manual-row").addEventListener("click", () => row.remove());
  container.appendChild(row);
}

function collectManualEmailRows() {
  return [...document.querySelectorAll(".manual-email-row")].map(r => ({
    carrier_name: r.querySelector(".manual-carrier-name")?.value?.trim() || "",
    email:        r.querySelector(".manual-email-addr")?.value?.trim() || "",
  })).filter(e => e.email);
}

/* ── Preview / Edit Text tab switching ─────────────────────────────── */
function initPreviewTabs() {
  document.getElementById("ptab-preview").addEventListener("click", () => {
    document.getElementById("ptab-preview").classList.add("active");
    document.getElementById("ptab-edit").classList.remove("active");
    document.getElementById("lm-preview-pane").classList.remove("hidden");
    document.getElementById("lm-edit-pane").classList.add("hidden");
    schedulePreviewUpdate();
  });
  document.getElementById("ptab-edit").addEventListener("click", () => {
    document.getElementById("ptab-edit").classList.add("active");
    document.getElementById("ptab-preview").classList.remove("active");
    document.getElementById("lm-edit-pane").classList.remove("hidden");
    document.getElementById("lm-preview-pane").classList.add("hidden");
    // populate if empty
    const ta = document.getElementById("lm-email-body-text");
    if (ta && !ta.value) ta.value = buildDefaultEmailBodyText();
  });

  // Sync custom text back to preview
  document.getElementById("lm-email-body-text")?.addEventListener("input", e => {
    state.customEmailText = e.target.value;
    schedulePreviewUpdate();
  });
}

/* ── DAT helpers ───────────────────────────────────────────────────── */
function showDatStep(step) {
  document.getElementById("dat-step-1").classList.toggle("hidden", step !== 1);
  document.getElementById("dat-step-2").classList.toggle("hidden", step !== 2);
  const msg = document.getElementById("dat-result-msg");
  if (msg) msg.classList.add("hidden");
}

async function submitDatImport(laneId, rawText) {
  const submitBtn = document.getElementById("dat-submit-btn");
  const resultMsg = document.getElementById("dat-result-msg");
  resultMsg.classList.add("hidden");
  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting…";
  try {
    await api(`/portal/lanes/${laneId}/dat-imports`, {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText }),
    });
    resultMsg.textContent = "✓ Submitted — redirecting to lane…";
    resultMsg.style.background = "#ecfdf5";
    resultMsg.style.color = "#065f46";
    resultMsg.classList.remove("hidden");
    setTimeout(() => {
      document.getElementById("dat-prompt-dialog").close();
      window.location.href = `/lanes/${laneId}`;
    }, 1200);
  } catch (err) {
    resultMsg.textContent = err?.payload?.message || err?.message || "Failed to submit. Please try again.";
    resultMsg.style.background = "#fef2f2";
    resultMsg.style.color = "#991b1b";
    resultMsg.classList.remove("hidden");
    submitBtn.disabled = false;
    submitBtn.textContent = "Parse and Save";
  }
}

/* ── Create lane ───────────────────────────────────────────────────── */
async function onCreateLane(event) {
  event.preventDefault();
  const errEl = document.getElementById("lane-form-error");
  errEl.classList.add("hidden");

  const fd = new FormData(document.getElementById("lane-form"));
  const manualEmails = collectManualEmailRows();

  const payload = {
    origin_city:        fd.get("origin_city"),
    origin_state:       fd.get("origin_state")?.toUpperCase(),
    origin_zip:         fd.get("origin_zip") || null,
    destination_city:   fd.get("destination_city"),
    destination_state:  fd.get("destination_state")?.toUpperCase(),
    destination_zip:    fd.get("destination_zip") || null,
    equipment_type:     fd.get("equipment_type"),
    pickup_date:        fd.get("pickup_date") || null,
    notes:              fd.get("notes") || null,
    stops: [],
    include_internal:  state.modalSources.internal,
    include_dat:       state.modalSources.dat,
    include_crr_model: state.modalSources.crr_model,
  };

  try {
    const created = await api("/portal/lanes", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    document.getElementById("lane-dialog").close();
    document.getElementById("lane-form").reset();
    document.getElementById("manual-email-rows").innerHTML = "";
    document.getElementById("manual-emails-section").classList.add("hidden");
    state.customEmailText = null;

    state.pendingLaneId = created.lane_id;

    // Store source + manual email selection for detail page pre-fill
    sessionStorage.setItem(`lane_init_${created.lane_id}`, JSON.stringify({
      sources: {
        internal:  state.modalSources.internal,
        dat:       state.modalSources.dat,
        crr_model: state.modalSources.crr_model,
        manual:    state.modalSources.manual,
      },
      notes:         fd.get("notes") || "",
      manual_emails: manualEmails,
    }));

    // Only show DAT import dialog if user actually selected DAT
    if (state.modalSources.dat) {
      showDatStep(1);
      document.getElementById("dat-prompt-dialog").showModal();
    } else {
      window.location.href = `/lanes/${created.lane_id}`;
    }
  } catch (err) {
    const detail = err?.payload?.detail;
    if (Array.isArray(detail) && detail.length) {
      errEl.textContent = detail.map(item => item?.msg || "Invalid value").join(" ");
    } else {
      errEl.textContent = "Failed to create lane. Please check values.";
    }
    errEl.classList.remove("hidden");
  }
}

/* ── Open / close modal ────────────────────────────────────────────── */
function openModal() {
  // Reset sources to defaults
  state.modalSources = { internal: true, dat: true, crr_model: true, manual: false };
  state.customEmailText = null;
  document.querySelectorAll(".src-card").forEach(card => {
    card.classList.toggle("on", !!state.modalSources[card.dataset.src]);
  });
  document.getElementById("manual-emails-section").classList.add("hidden");
  document.getElementById("manual-email-rows").innerHTML = "";
  document.getElementById("lm-email-body-text").value = "";
  document.getElementById("ptab-preview").classList.add("active");
  document.getElementById("ptab-edit").classList.remove("active");
  document.getElementById("lm-preview-pane").classList.remove("hidden");
  document.getElementById("lm-edit-pane").classList.add("hidden");
  document.getElementById("lane-dialog").showModal();
  schedulePreviewUpdate();
}

/* ── Init ──────────────────────────────────────────────────────────── */
async function init() {
  // Tab buttons
  document.querySelectorAll(".left-tab").forEach(btn =>
    btn.addEventListener("click", () => setTab(btn.dataset.tab))
  );

  // Open / close modal
  document.getElementById("open-lane-form").addEventListener("click", openModal);
  document.getElementById("cancel-lane").addEventListener("click", () => document.getElementById("lane-dialog").close());
  document.getElementById("cancel-lane-2")?.addEventListener("click", () => document.getElementById("lane-dialog").close());

  // Form submit
  document.getElementById("lane-form").addEventListener("submit", onCreateLane);

  // Source cards
  initModalSources();

  // Add recipient button
  document.getElementById("add-manual-row-btn")?.addEventListener("click", () => {
    addManualEmailRow(document.getElementById("manual-email-rows"));
  });

  // Preview tabs
  initPreviewTabs();

  // Live preview on form input
  ["f-origin-city", "f-origin-state", "f-origin-zip",
   "f-dest-city", "f-dest-state", "f-dest-zip",
   "f-equip", "f-pickup", "f-notes"].forEach(id => {
    document.getElementById(id)?.addEventListener("input", schedulePreviewUpdate);
  });

  // DAT dialog
  document.getElementById("dat-no-btn").addEventListener("click", () => {
    document.getElementById("dat-prompt-dialog").close();
    window.location.href = `/lanes/${state.pendingLaneId}`;
  });
  document.getElementById("dat-yes-btn").addEventListener("click", () => showDatStep(2));
  document.getElementById("dat-back-btn").addEventListener("click", () => showDatStep(1));
  document.getElementById("dat-submit-btn").addEventListener("click", async () => {
    const raw = document.getElementById("dat-paste-area").value;
    if (!raw.trim()) {
      const msg = document.getElementById("dat-result-msg");
      msg.textContent = "Please paste DAT text before submitting.";
      msg.style.background = "#fef2f2";
      msg.style.color = "#991b1b";
      msg.classList.remove("hidden");
      return;
    }
    await submitDatImport(state.pendingLaneId, raw);
  });

  // Load lanes
  try {
    const data = await api("/portal/lanes");
    state.lanes = data.lanes || [];
  } catch (_) {}

  setTab("active");
}

init();
