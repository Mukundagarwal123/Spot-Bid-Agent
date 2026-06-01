const state = {
  tab: "active",
  lanes: [],
  selectedLaneId: null,
  laneStatuses: {},
  detail: null,
  crm: [],
  detailTab: "overview",
  responseFilter: "all",
  selectedCarrierName: null,
  showCarrierDetails: false,
};

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
  const [detail, crm] = await Promise.all([
    api(`/portal/lanes/${state.selectedLaneId}`),
    api(`/portal/lanes/${state.selectedLaneId}/carrier-crm`),
  ]);
  state.detail = detail;
  state.crm = crm.carriers || [];
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
      await loadDetailAndCrm();
      render();
    });
  });

  els.lanesBody.querySelectorAll(".table-action").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      state.selectedLaneId = btn.dataset.laneId;
      await loadDetailAndCrm();
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

  const content =
    state.detailTab === "overview"
      ? `${overview}${responsesSection}`
      : state.detailTab === "responses"
      ? responsesSection
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
    destination_city: fd.get("destination_city"),
    destination_state: fd.get("destination_state"),
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
    await loadDetailAndCrm();
    els.laneDialog.close();
    els.laneForm.reset();
    render();
  } catch (err) {
    els.laneFormError.textContent = "Failed to create lane. Please check values.";
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
}

async function init() {
  bindEvents();
  await loadLanes();
  if (state.selectedLaneId) {
    await loadDetailAndCrm();
  }
  render();
}

init();
