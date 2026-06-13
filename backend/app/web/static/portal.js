const state = {
  tab: "active",
  lanes: [],
  selectedLaneId: null,
  laneStatuses: {},
  detail: null,
  crm: [],
  carrierRecords: { internal: [], dat: [] },
  carrierSourceTab: "internal",
  detailTab: "overview",
  responseFilter: "all",
  selectedCarrierName: null,
  showCarrierDetails: false,
  pendingLaneId: null,
  datPolling: false,
  outreachPanelOpen: false,
  outreachSources: { internal: true, dat: true, freightx: true },
  outreachNotes: "",
  outreachTestMode: false,
  outreachTestEmails: "",
  outreachPreview: null,
  outreachMetrics: null,
  outreachBatch: null,
  outreachSending: false,
};

let _datPollTimer = null;

function startDatPolling(laneId) {
  stopDatPolling();
  let attempts = 0;
  state.datPolling = true;
  renderDrawer();
  _datPollTimer = setInterval(async () => {
    attempts++;
    try {
      const data = await api(`/portal/lanes/${laneId}/carrier-records`);
      state.carrierRecords = data.sources || { internal: [], dat: [] };
      const internalDone = (state.carrierRecords.internal || []).length > 0;
      const datDone = (state.carrierRecords.dat || []).length > 0;
      if ((internalDone && datDone) || attempts >= 10) {
        stopDatPolling();
      }
      renderDrawer();
    } catch (_) {
      stopDatPolling();
    }
  }, 3000);
}

function stopDatPolling() {
  if (_datPollTimer) {
    clearInterval(_datPollTimer);
    _datPollTimer = null;
  }
  state.datPolling = false;
}

const equipmentLabels = {
  dry_van: "Dry Van",
  reefer: "Reefer",
  flatbed: "Flatbed",
  power_only: "Power Only",
  other: "Other",
};

const els = {
  leftTabs: [...document.querySelectorAll(".left-tab")],
  laneWorkspace: document.getElementById("lane-workspace"),
  crmWorkspace: document.getElementById("crm-workspace"),
  workspaceTitle: document.getElementById("workspace-title"),
  lanesBody: document.getElementById("lanes-body"),
  crmBody: document.getElementById("crm-body"),
  drawer: document.getElementById("drawer"),
  drawerContent: document.getElementById("drawer-content"),
  closeDrawer: document.getElementById("close-drawer"),
  laneDialog: document.getElementById("lane-dialog"),
  openLaneForm: document.getElementById("open-lane-form"),
  cancelLane: document.getElementById("cancel-lane"),
  laneForm: document.getElementById("lane-form"),
  laneFormError: document.getElementById("lane-form-error"),
  datPromptDialog: document.getElementById("dat-prompt-dialog"),
  datStep1: document.getElementById("dat-step-1"),
  datStep2: document.getElementById("dat-step-2"),
  datYesBtn: document.getElementById("dat-yes-btn"),
  datNoBtn: document.getElementById("dat-no-btn"),
  datPasteArea: document.getElementById("dat-paste-area"),
  datSubmitBtn: document.getElementById("dat-submit-btn"),
  datBackBtn: document.getElementById("dat-back-btn"),
  datResultMsg: document.getElementById("dat-result-msg"),
  outreachPreviewDialog: document.getElementById("outreach-preview-dialog"),
  previewSubject: document.getElementById("preview-subject-line"),
  previewBody: document.getElementById("preview-body-box"),
  previewRecipients: document.getElementById("preview-recipient-summary"),
  previewSourceBadges: document.getElementById("preview-source-badges"),
  previewSendBtn: document.getElementById("preview-send-btn"),
  previewEditBtn: document.getElementById("preview-edit-btn"),
  previewCancelBtn: document.getElementById("preview-cancel-btn"),
  previewSendError: document.getElementById("preview-send-error"),
};

function inferStatus(raw, laneId) {
  if (state.laneStatuses[laneId]) return state.laneStatuses[laneId];
  return raw === "closed" || raw === "completed" ? "completed" : "active";
}

function fmtDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function fmtDateTime(value) {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

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

async function loadLanes() {
  const data = await api("/portal/lanes");
  state.lanes = data.lanes || [];
  if (!state.selectedLaneId && state.lanes.length) {
    state.selectedLaneId = state.lanes[0].lane_id;
  }
}

async function loadDetailAndCrm() {
  if (!state.selectedLaneId) return;
  const [detail, crm, carrierData] = await Promise.all([
    api(`/portal/lanes/${state.selectedLaneId}`),
    api(`/portal/lanes/${state.selectedLaneId}/carrier-crm`),
    api(`/portal/lanes/${state.selectedLaneId}/carrier-records`),
  ]);
  state.detail = detail;
  state.crm = crm.carriers || [];
  state.carrierRecords = carrierData.sources || { internal: [], dat: [], freightx: [] };

  // If internal carriers haven't arrived yet, keep polling
  const internalReady = (state.carrierRecords.internal || []).length > 0;
  const datReady = (state.carrierRecords.dat || []).length > 0;
  if (!internalReady || !datReady) {
    if (!_datPollTimer) startDatPolling(state.selectedLaneId);
  }
}

async function loadOutreachMetrics(laneId) {
  try {
    state.outreachMetrics = await api(`/portal/lanes/${laneId}/outreach`);
  } catch (_) {
    state.outreachMetrics = null;
  }
}

function filteredLanes() {
  return state.lanes.filter((lane) => inferStatus(lane.status, lane.lane_id) === state.tab);
}

function renderLanesTable() {
  const rows = filteredLanes();
  if (!rows.length) {
    els.lanesBody.innerHTML = `<tr><td class="empty" colspan="7">No lanes here yet.</td></tr>`;
    return;
  }
  els.lanesBody.innerHTML = rows
    .map((lane) => {
      const status = inferStatus(lane.status, lane.lane_id);
      const cls = state.selectedLaneId === lane.lane_id ? "active-row" : "";
      return `
      <tr class="${cls}" data-lane-id="${lane.lane_id}">
        <td><div class="lane-title">${lane.label}</div></td>
        <td>${equipmentLabels[lane.equipment_type] || lane.equipment_type}</td>
        <td>${fmtDate(lane.pickup_date)}</td>
        <td>${lane.metrics_preview.carriers_contacted}</td>
        <td>${lane.metrics_preview.carriers_responded}</td>
        <td><span class="lane-pill ${status}">${status}</span></td>
        <td><button class="table-action" data-lane-id="${lane.lane_id}">View</button></td>
      </tr>`;
    })
    .join("");

  els.lanesBody.querySelectorAll("tr[data-lane-id]").forEach((row) => {
    row.addEventListener("click", async () => {
      state.selectedLaneId = row.dataset.laneId;
      state.outreachPanelOpen = false;
      await loadDetailAndCrm();
      await loadOutreachMetrics(state.selectedLaneId);
      render();
    });
  });

  els.lanesBody.querySelectorAll(".table-action").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      state.selectedLaneId = btn.dataset.laneId;
      state.outreachPanelOpen = false;
      await loadDetailAndCrm();
      await loadOutreachMetrics(state.selectedLaneId);
      render();
    });
  });
}

function renderCrmTable() {
  if (!state.selectedLaneId || !state.crm.length) {
    els.crmBody.innerHTML = `<tr><td class="empty" colspan="6">Select a lane from Active/Completed to see CRM.</td></tr>`;
    return;
  }
  els.crmBody.innerHTML = state.crm
    .map(
      (c) => `
      <tr>
        <td>${c.carrier_name}</td>
        <td>${c.times_contacted}</td>
        <td>${c.times_responded}</td>
        <td>${c.response_rate.toFixed(1)}%</td>
        <td><span class="chip ${c.preferred_channel}">${c.preferred_channel}</span></td>
        <td>${fmtDateTime(c.last_contacted_at)}</td>
      </tr>`
    )
    .join("");
}

function channelRows(metrics) {
  const rows = [
    { channel: "email", sent: metrics.emails_sent, replies: metrics.email_replies, clicks: metrics.emails_clicked },
    { channel: "sms", sent: metrics.sms_sent, replies: metrics.sms_replies, clicks: null },
    { channel: "whatsapp", sent: metrics.whatsapp_sent, replies: metrics.whatsapp_replies, clicks: null },
  ];
  return rows.map((r) => ({
    ...r,
    rate: r.sent > 0 ? Math.round((r.replies / r.sent) * 100) : 0,
  }));
}

function carrierDetails(carrier) {
  const seed = carrier.carrier_name
    .split("")
    .reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  const local = carrier.carrier_name.toLowerCase().replace(/[^a-z0-9]+/g, ".").replace(/^\.+|\.+$/g, "");
  return {
    mc: `MC-${100000 + (seed % 900000)}`,
    email: `${local || "carrier"}@fleetmail.com`,
    phone: `+1 (5${(seed % 10) + 1}5) ${100 + (seed % 800)}-${1000 + (seed % 8999)}`,
  };
}

function dummyConversation(carrier) {
  const ch = carrier.preferred_channel;
  return [
    { from: "agent", channel: ch, text: "Hi, we have a lane available. Can you quote this today?" },
    { from: "carrier", channel: ch, text: "Yes, share pickup window and target rate." },
    { from: "agent", channel: ch, text: "Pickup tomorrow morning. Sending details now." },
  ];
}

function showDatStep(step) {
  els.datStep1.classList.toggle("hidden", step !== 1);
  els.datStep2.classList.toggle("hidden", step !== 2);
  els.datResultMsg.classList.add("hidden");
}

async function submitDatImport(laneId, rawText) {
  els.datResultMsg.classList.add("hidden");
  els.datSubmitBtn.disabled = true;
  els.datSubmitBtn.textContent = "Submitting…";
  try {
    await api(`/portal/lanes/${laneId}/dat-imports`, {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText }),
    });
    els.datResultMsg.textContent = "✓ Submitted — parsing in background. The Carriers tab will update automatically.";
    els.datResultMsg.style.background = "#ecfdf5";
    els.datResultMsg.style.color = "#065f46";
    els.datResultMsg.classList.remove("hidden");
    setTimeout(async () => {
      els.datPromptDialog.close();
      els.datPasteArea.value = "";
      els.datSubmitBtn.disabled = false;
      els.datSubmitBtn.textContent = "Parse and Save";
      await loadDetailAndCrm();
      state.detailTab = "carriers";
      state.carrierSourceTab = "dat";
      state.datPolling = true;   // set BEFORE render so spinner shows immediately
      render();
      startDatPolling(laneId);
    }, 1500);
  } catch (err) {
    els.datResultMsg.textContent = err?.payload?.message || err?.message || "Failed to submit DAT text. Please try again.";
    els.datResultMsg.style.background = "#fef2f2";
    els.datResultMsg.style.color = "#991b1b";
    els.datResultMsg.classList.remove("hidden");
    els.datSubmitBtn.disabled = false;
    els.datSubmitBtn.textContent = "Parse and Save";
  }
}

function renderCarrierSourceTable(records, isLoading) {
  if (!records || !records.length) {
    if (isLoading) {
      return `<div style="padding:1.5rem 0;text-align:center;color:#667085">
        <div style="margin-bottom:.5rem">⏳ Parsing DAT data in background…</div>
        <div style="font-size:.8rem;opacity:.7">This page updates automatically every 3 seconds.</div>
      </div>`;
    }
    return `<div class="empty" style="padding:1.5rem 0;text-align:center;color:#667085">No carrier data for this source.</div>`;
  }
  return `
    <div class="table-wrap">
      <table class="shipment-table" style="font-size:.8rem">
        <thead>
          <tr>
            <th>Carrier Name</th>
            <th>Email</th>
            <th>Phone</th>
            <th>MC#</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          ${records.map((r) => `
            <tr>
              <td>${r.carrier_name}</td>
              <td>${r.email || "-"}</td>
              <td>${r.phone || "-"}</td>
              <td>${r.mc_number || "-"}</td>
              <td style="color:#667085;font-size:.75rem">${r.source_notes || "-"}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

function renderOutreachTab() {
  const m = state.outreachMetrics;
  const hasBatch = m && m.batch_id;

  function metricBox(label, value, rate) {
    return `
      <div style="flex:1;min-width:90px;text-align:center;padding:.75rem;background:#f9fafb;border:1px solid #e4e7ec;border-radius:8px">
        <div style="font-size:1.4rem;font-weight:700;color:#101828">${value}</div>
        ${rate !== undefined ? `<div style="font-size:.7rem;color:#667085">${rate}%</div>` : ""}
        <div style="font-size:.7rem;color:#667085;margin-top:.2rem">${label}</div>
      </div>`;
  }

  const metricsBar = hasBatch ? `
    <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1.25rem">
      ${metricBox("Sent", m.sent, undefined)}
      ${metricBox("Delivered", m.delivered, m.open_rate > 0 ? undefined : undefined)}
      ${metricBox("Opened", m.opened, m.open_rate)}
      ${metricBox("Clicked", m.clicked, m.click_through_rate)}
      ${metricBox("Replied", m.replied, m.reply_rate)}
    </div>` : "";

  const testBadge = hasBatch && m.test_mode
    ? `<span style="background:#fef3c7;color:#92400e;font-size:.7rem;padding:.2rem .5rem;border-radius:4px;font-weight:600">TEST RUN</span>`
    : "";

  const responseRows = (m && m.carrier_responses && m.carrier_responses.length) ? `
    <div style="margin-bottom:1rem">
      <div style="font-size:.8rem;font-weight:600;color:#344054;margin-bottom:.5rem">Carrier Responses</div>
      <div class="table-wrap">
        <table class="shipment-table" style="font-size:.78rem">
          <thead>
            <tr>
              <th>Carrier</th>
              <th>Email</th>
              <th>Source</th>
              <th>Status</th>
              <th>Last Event</th>
              <th>Reply</th>
            </tr>
          </thead>
          <tbody>
            ${m.carrier_responses.map((r) => `
              <tr>
                <td><strong>${r.carrier_name}</strong></td>
                <td style="color:#667085">${r.email}</td>
                <td><span class="chip">${r.source || "-"}</span></td>
                <td><span class="lane-pill active">${r.status}</span></td>
                <td style="color:#667085;font-size:.72rem">${r.last_event_at ? fmtDateTime(r.last_event_at) : "-"}</td>
                <td style="color:#344054;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.reply_snippet || "-"}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>` : "";

  const sourceCheckboxes = ["internal", "dat", "freightx"].map((src) => `
    <label style="display:flex;align-items:center;gap:.4rem;font-size:.85rem;cursor:pointer">
      <input type="checkbox" data-outreach-src="${src}" ${state.outreachSources[src] ? "checked" : ""} />
      ${src.charAt(0).toUpperCase() + src.slice(1)}
    </label>`).join("");

  const testEmailsBlock = state.outreachTestMode ? `
    <label style="display:block;margin-top:.75rem;font-size:.85rem;color:#344054">
      Test Recipients (one per line)
      <textarea id="outreach-test-emails" rows="3"
        style="width:100%;box-sizing:border-box;margin-top:.3rem;resize:vertical;font-size:.8rem;padding:.4rem .6rem;border:1px solid #d0d5dd;border-radius:6px;font-family:monospace"
        placeholder="test1@example.com"
      >${state.outreachTestEmails}</textarea>
    </label>` : "";

  const launchPanel = state.outreachPanelOpen ? `
    <div style="border:1px solid #e4e7ec;border-radius:8px;padding:1rem;margin-top:1rem;background:#fafafa">
      <div style="font-size:.85rem;font-weight:600;color:#344054;margin-bottom:.75rem">Configure Outreach</div>
      <div style="margin-bottom:.75rem">
        <div style="font-size:.8rem;color:#667085;margin-bottom:.4rem">Include Sources</div>
        <div style="display:flex;gap:1rem;flex-wrap:wrap">${sourceCheckboxes}</div>
      </div>
      <label style="display:block;font-size:.85rem;color:#344054;margin-bottom:.5rem">
        Notes (optional)
        <textarea id="outreach-notes" rows="3"
          style="width:100%;box-sizing:border-box;margin-top:.3rem;resize:vertical;font-size:.8rem;padding:.4rem .6rem;border:1px solid #d0d5dd;border-radius:6px"
          placeholder="Add context for carriers…"
        >${state.outreachNotes}</textarea>
      </label>
      <label style="display:flex;align-items:center;gap:.5rem;font-size:.85rem;cursor:pointer;margin-bottom:.25rem">
        <input type="checkbox" id="outreach-test-toggle" ${state.outreachTestMode ? "checked" : ""} />
        Test Mode
      </label>
      ${testEmailsBlock}
      <div class="form-actions" style="margin-top:1rem">
        <button id="outreach-preview-btn" class="btn-primary" ${state.outreachSending ? "disabled" : ""}>
          ${state.outreachSending ? "Sending…" : "Preview Email"}
        </button>
        <button id="outreach-panel-cancel" class="btn-secondary">Cancel</button>
      </div>
    </div>` : "";

  return `
    <section class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem">
        <div style="font-size:.9rem;font-weight:600;color:#101828">
          Email Outreach ${testBadge}
        </div>
        ${hasBatch ? `<button id="launch-outreach-btn" class="btn-secondary" style="font-size:.78rem">New Send</button>` : `<button id="launch-outreach-btn" class="btn-primary" style="font-size:.78rem">Launch Outreach</button>`}
      </div>
      ${metricsBar}
      ${responseRows}
      ${!hasBatch && !state.outreachPanelOpen ? `<div class="empty" style="padding:1.5rem 0;text-align:center;color:#667085">No outreach sent yet for this lane.</div>` : ""}
      ${launchPanel}
    </section>`;
}

function renderDrawer() {
  if (!state.selectedLaneId || state.tab === "crm" || !state.detail) {
    els.drawer.classList.add("hidden");
    return;
  }
  els.drawer.classList.remove("hidden");
  const lane = state.detail.lane;
  const status = inferStatus(lane.status, lane.lane_id);
  const channelData = channelRows(state.detail.metrics);
  const totalSent = channelData.reduce((n, c) => n + c.sent, 0);
  const totalReplies = channelData.reduce((n, c) => n + c.replies, 0);
  const best = [...channelData].sort((a, b) => b.rate - a.rate)[0]?.channel || "-";
  const responded = state.crm.filter(
    (c) => c.times_responded > 0 && (state.responseFilter === "all" || c.preferred_channel === state.responseFilter)
  );
  if (!state.selectedCarrierName && responded.length) {
    state.selectedCarrierName = responded[0].carrier_name;
  }
  const selectedCarrier = responded.find((c) => c.carrier_name === state.selectedCarrierName) || responded[0] || null;
  const details = selectedCarrier ? carrierDetails(selectedCarrier) : null;
  const messages = selectedCarrier ? dummyConversation(selectedCarrier) : [];

  const tabs = [
    ["overview", "Overview"],
    ["responses", "Carrier Responses"],
    ["activity", "Activity Log"],
    ["carriers", "Carriers"],
    ["outreach", "Outreach"],
  ];

  const tabButtons = tabs
    .map(([id, label]) => `<button class="tab-btn ${state.detailTab === id ? "active" : ""}" data-dtab="${id}">${label}</button>`)
    .join("");

  const overview = `
    <section class="card">
      <div class="channel-summary">
        <span>Total Sent: ${totalSent}</span>
        <span>Total Replies: ${totalReplies}</span>
        <span>Best Channel: ${best}</span>
      </div>
      <div class="channel-grid">
        ${channelData
          .map(
            (c) => `
            <div class="channel-item">
              <div class="channel-top">
                <span class="chip ${c.channel}">${c.channel}</span>
                <strong>${c.rate}%</strong>
              </div>
              <div class="channel-metrics">
                <span>Sent ${c.sent}</span>
                <span>Replies ${c.replies}</span>
                <span>${typeof c.clicks === "number" ? `Clicks ${c.clicks}` : ""}</span>
              </div>
              <div class="bar"><div style="width:${c.rate}%"></div></div>
            </div>`
          )
          .join("")}
      </div>
    </section>`;

  const responsesSection = `
  <section class="card">
    <div class="responses-layout">
      <div>
        <div class="response-toolbar">
          <span>Responded Carriers</span>
          <div class="filter-row">
            ${["all", "email", "sms", "whatsapp"]
              .map((f) => `<button class="filter-chip ${state.responseFilter === f ? "active" : ""}" data-filter="${f}">${f}</button>`)
              .join("")}
          </div>
        </div>
        ${responded
          .map(
            (c) => `
            <button class="response-item ${selectedCarrier?.carrier_name === c.carrier_name ? "active" : ""}" data-carrier="${c.carrier_name}">
              <div>
                <div class="name">${c.carrier_name}</div>
                <div class="meta">${c.times_responded} responses | ${c.response_rate.toFixed(1)}%</div>
              </div>
              <span class="chip ${c.preferred_channel}">${c.preferred_channel}</span>
            </button>`
          )
          .join("") || `<div class="empty">No responses for this channel.</div>`}
      </div>
      <div class="conversation-panel">
        <h3>Communication History</h3>
        ${
          selectedCarrier
            ? `<div class="conversation-head">
                <strong>${selectedCarrier.carrier_name}</strong>
                <div class="head-actions">
                  <span>Last contact: ${fmtDateTime(selectedCarrier.last_contacted_at)}</span>
                  <button class="details-toggle" id="toggle-details">${state.showCarrierDetails ? "Hide Details" : "Carrier Details"}</button>
                </div>
              </div>
              ${
                state.showCarrierDetails && details
                  ? `<div class="carrier-details">
                      <div><span>MC Number</span><strong>${details.mc}</strong></div>
                      <div><span>Email</span><strong>${details.email}</strong></div>
                      <div><span>Contact</span><strong>${details.phone}</strong></div>
                    </div>`
                  : ""
              }
              <div class="chat">
                ${messages
                  .map(
                    (m) => `
                    <div class="msg ${m.from}">
                      <div class="msg-top"><span>${m.from === "agent" ? "Agent" : "Carrier"}</span><span>${m.channel}</span></div>
                      <p>${m.text}</p>
                    </div>`
                  )
                  .join("")}
              </div>`
            : `<div class="empty">Select a responding carrier.</div>`
        }
      </div>
    </div>
  </section>`;

  const activity = `
    <section class="card">
      <h3>Detailed Activity Timeline</h3>
      <ul class="timeline">
        ${state.detail.timeline
          .map((e) => `<li><div class="lbl">${e.label}</div><div class="ts">${fmtDateTime(e.timestamp)}</div></li>`)
          .join("")}
      </ul>
    </section>`;

  const internalCount = (state.carrierRecords.internal || []).length;
  const datCount = (state.carrierRecords.dat || []).length;
  const freightxCount = (state.carrierRecords.freightx || []).length;
  const isLoadingInternal = state.datPolling && internalCount === 0;
  const isLoadingDat = state.datPolling && state.carrierSourceTab === "dat" && datCount === 0;
  const internalLabel = isLoadingInternal ? `Internal ⏳` : `Internal (${internalCount})`;
  const datLabel = state.datPolling && datCount === 0 ? `DAT ⏳` : `DAT (${datCount})`;
  const freightxLabel = `FreightX (${freightxCount})`;

  function renderFreightXTable(records) {
    if (!records || !records.length) {
      return `<div class="empty" style="padding:1.5rem 0;text-align:center;color:#667085">No FreightX data for this lane.</div>`;
    }
    return `
      <div class="table-wrap">
        <table class="shipment-table" style="font-size:.8rem">
          <thead>
            <tr>
              <th>Carrier Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>MC#</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            ${records.map((r) => `
              <tr>
                <td>${r.carrier_name || "-"}</td>
                <td>${r.email || "-"}</td>
                <td>${r.phone || "-"}</td>
                <td>${r.mc_number || "-"}</td>
                <td style="color:#667085;font-size:.75rem">${r.source_notes || "-"}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  const activeCarrierTable = state.carrierSourceTab === "freightx"
    ? renderFreightXTable(state.carrierRecords.freightx || [])
    : renderCarrierSourceTable(state.carrierRecords[state.carrierSourceTab] || [], isLoadingDat);

  const carriersSection = `
    <section class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
        <div class="tabs">
          ${[["internal", internalLabel], ["dat", datLabel], ["freightx", freightxLabel]]
            .map(([src, label]) => `<button class="tab-btn ${state.carrierSourceTab === src ? "active" : ""}" data-csrc="${src}">${label}</button>`)
            .join("")}
        </div>
        <button id="refresh-carriers-btn" style="font-size:.75rem;padding:.25rem .6rem;border:1px solid #d0d5dd;border-radius:6px;background:#fff;cursor:pointer;color:#344054">↻ Refresh</button>
      </div>
      ${activeCarrierTable}
    </section>`;

  const outreachSection = renderOutreachTab();

  const content =
    state.detailTab === "overview"
      ? `${overview}${responsesSection}`
      : state.detailTab === "responses"
      ? responsesSection
      : state.detailTab === "carriers"
      ? carriersSection
      : state.detailTab === "outreach"
      ? outreachSection
      : activity;

  els.drawerContent.innerHTML = `
    <div class="drawer-top">
      <div>
        <h2 class="drawer-title">${lane.label}</h2>
        <p class="drawer-sub">${lane.equipment_type.replace("_", " ")}${lane.pickup_date ? ` | Pickup ${lane.pickup_date}` : ""}</p>
      </div>
      <div>
        <span class="lane-pill ${status}">${status}</span>
      </div>
    </div>
    <div class="tabs">${tabButtons}</div>
    ${content}
  `;

  els.drawerContent.querySelectorAll("[data-dtab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.detailTab = btn.dataset.dtab;
      renderDrawer();
    });
  });
  els.drawerContent.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.responseFilter = btn.dataset.filter;
      state.selectedCarrierName = null;
      renderDrawer();
    });
  });
  els.drawerContent.querySelectorAll("[data-carrier]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedCarrierName = btn.dataset.carrier;
      renderDrawer();
    });
  });
  const detailsBtn = document.getElementById("toggle-details");
  if (detailsBtn) {
    detailsBtn.addEventListener("click", () => {
      state.showCarrierDetails = !state.showCarrierDetails;
      renderDrawer();
    });
  }
  els.drawerContent.querySelectorAll("[data-csrc]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.carrierSourceTab = btn.dataset.csrc;
      renderDrawer();
    });
  });
  const refreshBtn = document.getElementById("refresh-carriers-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      refreshBtn.textContent = "↻ Refreshing…";
      refreshBtn.disabled = true;
      try {
        const data = await api(`/portal/lanes/${state.selectedLaneId}/carrier-records`);
        state.carrierRecords = data.sources || { internal: [], dat: [], freightx: [] };
        if ((state.carrierRecords.dat || []).length > 0) stopDatPolling();
      } finally {
        renderDrawer();
      }
    });
  }

  bindOutreachEvents();
}

function render() {
  els.leftTabs.forEach((btn) =>
    btn.classList.toggle("active", btn.dataset.tab === state.tab)
  );
  const laneView = state.tab !== "crm";
  els.laneWorkspace.classList.toggle("hidden", !laneView);
  els.crmWorkspace.classList.toggle("hidden", laneView);
  if (laneView) {
    els.workspaceTitle.textContent =
      state.tab === "active" ? "Active Lanes" : "Completed Lanes";
    renderLanesTable();
  } else {
    renderCrmTable();
  }
  renderDrawer();
}

async function onTabChange(tab) {
  state.tab = tab;
  render();
  if (tab === "crm" && state.selectedLaneId) {
    await loadDetailAndCrm();
    render();
  }
}

async function onCreateLane(event) {
  event.preventDefault();
  els.laneFormError.classList.add("hidden");
  const fd = new FormData(els.laneForm);
  const payload = {
    origin_city: fd.get("origin_city"),
    origin_state: fd.get("origin_state"),
    origin_zip: fd.get("origin_zip"),
    destination_city: fd.get("destination_city"),
    destination_state: fd.get("destination_state"),
    destination_zip: fd.get("destination_zip"),
    equipment_type: fd.get("equipment_type"),
    pickup_date: fd.get("pickup_date") || null,
    stops: [],
  };
  try {
    const created = await api("/portal/lanes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await loadLanes();
    state.selectedLaneId = created.lane_id;
    state.tab = "active";
    els.laneDialog.close();
    els.laneForm.reset();
    state.pendingLaneId = created.lane_id;
    showDatStep(1);
    els.datPromptDialog.showModal();
  } catch (err) {
    const detail = err?.payload?.detail;
    if (Array.isArray(detail) && detail.length) {
      els.laneFormError.textContent = detail
        .map((item) => item?.msg || "Invalid value")
        .join(" ");
    } else {
      els.laneFormError.textContent = "Failed to create lane. Please check values.";
    }
    els.laneFormError.classList.remove("hidden");
  }
}

function bindEvents() {
  els.leftTabs.forEach((btn) =>
    btn.addEventListener("click", () => onTabChange(btn.dataset.tab))
  );
  els.closeDrawer.addEventListener("click", () => {
    state.selectedLaneId = null;
    state.detail = null;
    state.crm = [];
    render();
  });
  els.openLaneForm.addEventListener("click", () => els.laneDialog.showModal());
  els.cancelLane.addEventListener("click", () => els.laneDialog.close());
  els.laneForm.addEventListener("submit", onCreateLane);

  els.datNoBtn.addEventListener("click", async () => {
    els.datPromptDialog.close();
    await loadDetailAndCrm();
    render();
  });
  els.datYesBtn.addEventListener("click", () => showDatStep(2));
  els.datBackBtn.addEventListener("click", () => showDatStep(1));
  els.datSubmitBtn.addEventListener("click", async () => {
    const raw = els.datPasteArea.value;
    if (!raw.trim()) {
      els.datResultMsg.textContent = "Please paste DAT text before submitting.";
      els.datResultMsg.style.background = "#fef2f2";
      els.datResultMsg.style.color = "#991b1b";
      els.datResultMsg.classList.remove("hidden");
      return;
    }
    await submitDatImport(state.pendingLaneId, raw);
  });

  // Preview dialog buttons
  els.previewCancelBtn.addEventListener("click", () => {
    els.outreachPreviewDialog.close();
  });

  els.previewEditBtn.addEventListener("click", () => {
    els.outreachPreviewDialog.close();
    // Return focus to notes in the outreach panel
    setTimeout(() => {
      const notesTA = document.getElementById("outreach-notes");
      if (notesTA) notesTA.focus();
    }, 50);
  });

  els.previewSendBtn.addEventListener("click", async () => {
    if (!state.outreachPreview || state.outreachSending) return;
    state.outreachSending = true;
    els.previewSendBtn.disabled = true;
    els.previewSendBtn.textContent = "Sending…";
    els.previewSendError.classList.add("hidden");

    try {
      const result = await api(`/portal/lanes/${state.selectedLaneId}/outreach/send`, {
        method: "POST",
        body: JSON.stringify(state.outreachPreview._payload),
      });
      state.outreachBatch = result;
      state.outreachPanelOpen = false;
      els.outreachPreviewDialog.close();
      state.detailTab = "outreach";
      await loadOutreachMetrics(state.selectedLaneId);
      renderDrawer();
      // Poll for fast webhook events (up to 5 times, every 10s)
      let polls = 0;
      const pollTimer = setInterval(async () => {
        polls++;
        await loadOutreachMetrics(state.selectedLaneId);
        renderDrawer();
        if (polls >= 5 || (state.outreachMetrics && state.outreachMetrics.delivered > 0)) {
          clearInterval(pollTimer);
        }
      }, 10000);
    } catch (err) {
      els.previewSendError.textContent = err?.payload?.detail || err?.message || "Send failed. Please try again.";
      els.previewSendError.classList.remove("hidden");
    } finally {
      state.outreachSending = false;
      els.previewSendBtn.disabled = false;
      els.previewSendBtn.textContent = "Confirm and Send";
    }
  });
}

function bindOutreachEvents() {
  // Launch / New Send button
  const launchBtn = document.getElementById("launch-outreach-btn");
  if (launchBtn) {
    launchBtn.addEventListener("click", () => {
      state.outreachPanelOpen = true;
      renderDrawer();
    });
  }

  // Cancel outreach panel
  const panelCancel = document.getElementById("outreach-panel-cancel");
  if (panelCancel) {
    panelCancel.addEventListener("click", () => {
      state.outreachPanelOpen = false;
      renderDrawer();
    });
  }

  // Source checkboxes
  document.querySelectorAll("[data-outreach-src]").forEach((cb) => {
    cb.addEventListener("change", () => {
      state.outreachSources[cb.dataset.outreachSrc] = cb.checked;
    });
  });

  // Notes textarea (live sync)
  const notesTA = document.getElementById("outreach-notes");
  if (notesTA) {
    notesTA.addEventListener("input", () => { state.outreachNotes = notesTA.value; });
  }

  // Test mode toggle
  const testToggle = document.getElementById("outreach-test-toggle");
  if (testToggle) {
    testToggle.addEventListener("change", () => {
      state.outreachTestMode = testToggle.checked;
      renderDrawer();
    });
  }

  // Test emails textarea (live sync)
  const testEmailsTA = document.getElementById("outreach-test-emails");
  if (testEmailsTA) {
    testEmailsTA.addEventListener("input", () => { state.outreachTestEmails = testEmailsTA.value; });
  }

  // Preview button
  const previewBtn = document.getElementById("outreach-preview-btn");
  if (previewBtn) {
    previewBtn.addEventListener("click", async () => {
      const notes = document.getElementById("outreach-notes")?.value ?? state.outreachNotes;
      const testEmails = document.getElementById("outreach-test-emails")?.value ?? state.outreachTestEmails;
      state.outreachNotes = notes;
      state.outreachTestEmails = testEmails;

      const manualEmails = testEmails
        .split("\n")
        .map((e) => e.trim())
        .filter(Boolean);

      const payload = {
        include_internal: state.outreachSources.internal,
        include_dat: state.outreachSources.dat,
        include_freightx: state.outreachSources.freightx,
        test_mode: state.outreachTestMode,
        manual_emails: manualEmails,
        notes: notes,
      };

      previewBtn.disabled = true;
      previewBtn.textContent = "Loading preview…";
      try {
        const preview = await api(`/portal/lanes/${state.selectedLaneId}/outreach/preview`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.outreachPreview = { ...preview, _payload: payload };
        openPreviewModal(preview);
      } catch (err) {
        alert(err?.payload?.detail || err?.message || "Failed to load preview.");
      } finally {
        previewBtn.disabled = false;
        previewBtn.textContent = "Preview Email";
      }
    });
  }
}

function openPreviewModal(preview) {
  els.previewSubject.textContent = preview.subject;
  els.previewBody.textContent = preview.body;

  const recipientLabel = preview.test_mode
    ? `${preview.recipient_count} test recipient${preview.recipient_count !== 1 ? "s" : ""}`
    : `${preview.recipient_count} carrier${preview.recipient_count !== 1 ? "s" : ""}`;
  els.previewRecipients.textContent = `Recipients: ${recipientLabel}`;

  els.previewSourceBadges.innerHTML = preview.test_mode
    ? `<span style="background:#fef3c7;color:#92400e;font-size:.75rem;padding:.2rem .6rem;border-radius:4px;font-weight:600">TEST RUN</span>`
    : (preview.sources_included || []).map((s) =>
        `<span class="chip">${s}</span>`
      ).join("");

  els.previewSendError.classList.add("hidden");
  els.previewSendError.textContent = "";
  els.outreachPreviewDialog.showModal();
}

async function init() {
  bindEvents();
  await loadLanes();
  if (state.selectedLaneId) {
    await loadDetailAndCrm();
    await loadOutreachMetrics(state.selectedLaneId);
  }
  render();
}

init();
