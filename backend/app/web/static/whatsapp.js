/* ── State ──────────────────────────────────────────────────────────── */
const state = {
  conversations: [],
  activeConvId: null,
  messages: [],
  contact: null,
  sessionOpen: true,
  searchTerm: "",
  statusFilter: "open",
  unreadOnly: false,
  sending: false,
  loadingThread: false,
  templates: [],
  // polling — fallback when SSE is unavailable
  convPollTimer: null,
  msgPollTimer: null,
  lastMsgId: null,
  // SSE
  sseConnected: false,
  sseRetryCount: 0,
};

let _evtSource = null;
let _sseRetryTimer = null;
const UI_STATE_KEY = "spotbid.whatsapp.ui-state.v1";

function loadUiState() {
  try {
    const raw = localStorage.getItem(UI_STATE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (typeof saved.searchTerm === "string") state.searchTerm = saved.searchTerm;
    if (typeof saved.statusFilter === "string") state.statusFilter = saved.statusFilter;
    if (typeof saved.unreadOnly === "boolean") state.unreadOnly = saved.unreadOnly;
    if (typeof saved.activeConvId === "string" && saved.activeConvId) state.activeConvId = saved.activeConvId;
  } catch {
    // Ignore broken local storage payloads.
  }
}

function saveUiState() {
  try {
    localStorage.setItem(UI_STATE_KEY, JSON.stringify({
      activeConvId: state.activeConvId,
      searchTerm: state.searchTerm,
      statusFilter: state.statusFilter,
      unreadOnly: state.unreadOnly,
    }));
  } catch {
    // Ignore storage quota / privacy errors.
  }
}

function updateConversationSummary(convId, patch = {}, bubbleTop = true) {
  const conv = state.conversations.find(x => x.id === convId);
  if (!conv) return null;
  Object.assign(conv, patch);
  if (bubbleTop) {
    const idx = state.conversations.indexOf(conv);
    if (idx > 0) {
      state.conversations.splice(idx, 1);
      state.conversations.unshift(conv);
    }
  }
  renderConvList();
  return conv;
}

/* ── API helper ─────────────────────────────────────────────────────── */
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(json?.detail || "Request failed");
    err.status = res.status;
    throw err;
  }
  return json;
}

/* ── SSE client ─────────────────────────────────────────────────────── */
// SSE requires a threaded / async server (gunicorn+gevent, etc.).
// Werkzeug's dev server is single-threaded: the SSE generator holds the
// only thread and blocks every subsequent API call. Disabled for dev;
// call connectSse() manually in production when the server supports it.
function connectSse() {
  if (_evtSource) { _evtSource.close(); _evtSource = null; }
  clearTimeout(_sseRetryTimer);

  _evtSource = new EventSource("/api/whatsapp/stream");

  _evtSource.onopen = () => {
    state.sseConnected = true;
    state.sseRetryCount = 0;
    setConnectionBadge("live");
    stopMsgPoll();
    stopConvPoll();
  };

  _evtSource.onmessage = (e) => {
    try { handleSseEvent(JSON.parse(e.data)); } catch { /* bad JSON */ }
  };

  _evtSource.onerror = () => {
    state.sseConnected = false;
    setConnectionBadge("reconnecting");
    _evtSource.close();
    _evtSource = null;
    // Fall back to polling until SSE reconnects
    startConvPoll();
    if (state.activeConvId) startMsgPoll();
    const delay = Math.min(1000 * Math.pow(1.5, state.sseRetryCount++), 30000);
    _sseRetryTimer = setTimeout(connectSse, delay);
  };
}

function handleSseEvent(event) {
  if (event.type === "ping" || event.type === "connected") return;

  if (event.type === "new_message") {
    const { convId, message, convUpdate } = event;

    // Update conversation row in the list
    if (!updateConversationSummary(convId, {
      lastMessagePreview: convUpdate.lastMessagePreview,
      lastActivityAt: convUpdate.lastActivityAt,
      unreadCount: convId === state.activeConvId ? 0 : convUpdate.unreadCount,
    })) {
      loadConversations(); // brand-new contact — reload list
    }

    // Append to the open thread if it's the active conversation
    if (convId === state.activeConvId && !state.messages.find(m => m.id === message.id)) {
      state.messages.push(message);
      state.lastMsgId = message.id;
      appendMessageBubble(message, true);
    }
  }

  if (event.type === "status_update") {
    const { messageId, status } = event;
    const msg = state.messages.find(m => m.id === messageId);
    if (msg && msg.status !== status) {
      msg.status = status;
      updateMessageBubble(messageId, status);
    }
  }
}

function setConnectionBadge(badgeState) {
  const badge = document.getElementById("sse-badge");
  if (!badge) return;
  badge.className = `sse-badge ${badgeState}`;
  badge.title = badgeState === "live"
    ? "Live — messages appear automatically"
    : "Reconnecting…";
}

/* ── Avatar helpers ─────────────────────────────────────────────────── */
function avatarClass(phone) {
  let h = 0;
  for (const c of String(phone)) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
  return `av-${h % 8}`;
}
function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
}

/* ── Phone formatter ────────────────────────────────────────────────── */
function formatPhone(phone) {
  if (!phone) return "";
  const digits = String(phone).replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("1"))
    return `+1 (${digits.slice(1,4)}) ${digits.slice(4,7)}-${digits.slice(7)}`;
  if (digits.length === 12 && digits.startsWith("91"))
    return `+91 ${digits.slice(2,7)} ${digits.slice(7)}`;
  return `+${digits}`;
}

/* ── Time formatters ────────────────────────────────────────────────── */
function relTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today - 86400000);
  const dDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  if (dDay.getTime() === today.getTime())
    return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  if (dDay.getTime() === yesterday.getTime()) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function fmtTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today - 86400000);
  const dDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  if (dDay.getTime() === today.getTime()) return "Today";
  if (dDay.getTime() === yesterday.getTime()) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/* ── Tick icon for outbound status ─────────────────────────────────── */
function tickHtml(status) {
  if (status === "pending")   return `<span class="msg-tick sent" title="Sending…">○</span>`;
  if (status === "sent")      return `<span class="msg-tick sent" title="Sent">✓</span>`;
  if (status === "delivered") return `<span class="msg-tick delivered" title="Delivered">✓✓</span>`;
  if (status === "read")      return `<span class="msg-tick read" title="Read">✓✓</span>`;
  if (status === "failed")    return `<span class="msg-tick failed" title="Failed">✗</span>`;
  return "";
}

/* ── Conversation list ──────────────────────────────────────────────── */
function renderConvList() {
  const list = document.getElementById("conv-list");
  const empty = document.getElementById("conv-list-empty");
  const badge = document.getElementById("unread-total-badge");

  if (!list) return;

  const totalUnread = state.conversations.reduce((s, c) => s + (c.unreadCount || 0), 0);
  if (badge) {
    if (totalUnread > 0) {
      badge.textContent = totalUnread;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }

  const term = state.searchTerm.toLowerCase();
  const filtered = state.conversations.filter(c => {
    if (state.unreadOnly && !c.unreadCount) return false;
    if (state.statusFilter !== "all" && c.status !== state.statusFilter) return false;
    if (term && !c.contactName?.toLowerCase().includes(term)
             && !c.phone?.toLowerCase().includes(term)
             && !c.lastMessagePreview?.toLowerCase().includes(term)) return false;
    return true;
  });

  if (!filtered.length) {
    list.innerHTML = "";
    if (empty) {
      empty.classList.remove("hidden");
    } else {
      list.innerHTML = `<div class="conv-list-empty" id="conv-list-empty">No conversations yet.</div>`;
    }
    return;
  }
  if (empty) empty.classList.add("hidden");

  list.innerHTML = filtered.map(c => {
    const cls = avatarClass(c.phone);
    const ini = initials(c.contactName);
    const unreadBadge = c.unreadCount > 0
      ? `<span class="conv-unread-dot">${c.unreadCount}</span>` : "";
    const active = c.id === state.activeConvId ? "active" : "";
    const unread = c.unreadCount > 0 ? "unread" : "";
    return `
      <div class="conv-row ${active} ${unread}" data-id="${c.id}">
        <div class="conv-avatar ${cls}">${ini}${unreadBadge}</div>
        <div class="conv-body">
          <div class="conv-name-row">
            <span class="conv-name">${esc(c.contactName || c.phone)}</span>
            <span class="conv-ts">${relTime(c.lastActivityAt)}</span>
          </div>
          <div class="conv-phone">${esc(formatPhone(c.phone))}</div>
          <div class="conv-preview">${esc(c.lastMessagePreview || "")}</div>
        </div>
      </div>`;
  }).join("");

  list.querySelectorAll(".conv-row").forEach(row => {
    row.addEventListener("click", () => selectConversation(row.dataset.id));
  });
}

/* ── Thread view (full render, used only on initial conversation load) */
function renderThread() {
  const msgs = state.messages;
  const container = document.getElementById("thread-messages");

  if (!msgs.length) {
    container.innerHTML = `<div class="thread-empty-msgs">No messages yet.</div>`;
    return;
  }

  let html = "";
  let lastDate = null;
  let lastDir = null;

  msgs.forEach((m) => {
    const iso = m.direction === "inbound" ? m.receivedAt : m.sentAt;
    const dateLabel = fmtDate(iso);

    if (dateLabel !== lastDate) {
      html += `<div class="date-sep"><div class="date-sep-label">${dateLabel}</div></div>`;
      lastDate = dateLabel;
      lastDir = null;
    }

    const dir = m.direction;
    const showSender = dir === "inbound" && dir !== lastDir;
    lastDir = dir;

    const templateBadge = m.isTemplate ? `<span class="msg-template-badge">template</span>` : "";
    const metaTime = `<span class="msg-time">${fmtTime(iso)}</span>`;
    const tick = dir === "outbound" ? tickHtml(m.status) : "";
    const retryBtn = m.status === "failed"
      ? `<button class="msg-retry-btn" data-id="${m.id}">Retry</button>` : "";

    html += `
      <div class="msg-bubble-wrap ${dir} ${m.status}" data-msg-id="${m.id}">
        ${showSender ? `<div class="msg-sender-name">${esc(state.contact?.displayName || state.contact?.phone || "")}</div>` : ""}
        <div class="msg-bubble">${esc(m.body)}</div>
        <div class="msg-meta">${metaTime}${tick}${templateBadge}${retryBtn}</div>
      </div>`;
  });

  const wasAtBottom = isAtBottom(container);
  container.innerHTML = html;
  if (wasAtBottom || state.loadingThread) scrollToBottom(container);

  if (msgs.length) state.lastMsgId = msgs[msgs.length - 1].id;
}

/* ── Incremental message append — no full re-render ─────────────────── */
function appendMessageBubble(msg, animate = false) {
  const container = document.getElementById("thread-messages");
  if (!container) return;

  // Remove "No messages yet." placeholder if present
  const placeholder = container.querySelector(".thread-empty-msgs");
  if (placeholder) placeholder.remove();

  const atBottom = isAtBottom(container);
  const iso = msg.direction === "inbound" ? msg.receivedAt : msg.sentAt;
  const dateLabel = fmtDate(iso);

  // Check whether a date separator is needed
  const msgs = state.messages;
  const msgIdx = msgs.findIndex(m => m.id === msg.id);
  let needSep = true;
  if (msgIdx > 0) {
    const prev = msgs[msgIdx - 1];
    const prevIso = prev.direction === "inbound" ? prev.receivedAt : prev.sentAt;
    if (fmtDate(prevIso) === dateLabel) needSep = false;
  }

  const frag = document.createDocumentFragment();

  if (needSep) {
    const sep = document.createElement("div");
    sep.className = "date-sep";
    sep.innerHTML = `<div class="date-sep-label">${dateLabel}</div>`;
    frag.appendChild(sep);
  }

  const dir = msg.direction;
  const templateBadge = msg.isTemplate ? `<span class="msg-template-badge">template</span>` : "";
  const metaTime = `<span class="msg-time">${fmtTime(iso)}</span>`;
  const tick = dir === "outbound" ? tickHtml(msg.status) : "";
  const retryBtn = msg.status === "failed"
    ? `<button class="msg-retry-btn" data-id="${msg.id}">Retry</button>` : "";

  const wrap = document.createElement("div");
  wrap.className = `msg-bubble-wrap ${dir} ${msg.status}${animate ? " msg-new" : ""}`;
  wrap.dataset.msgId = msg.id;
  wrap.innerHTML = `
    <div class="msg-bubble">${esc(msg.body)}</div>
    <div class="msg-meta">${metaTime}${tick}${templateBadge}${retryBtn}</div>`;
  frag.appendChild(wrap);

  container.appendChild(frag);

  if (atBottom || dir === "inbound") scrollToBottom(container);
}

/* ── In-place status tick update ────────────────────────────────────── */
function updateMessageBubble(msgId, newStatus) {
  const wrap = document.querySelector(`[data-msg-id="${msgId}"]`);
  if (!wrap) return;

  wrap.classList.remove("pending", "sent", "delivered", "read", "failed");
  if (newStatus) wrap.classList.add(newStatus);

  const metaEl = wrap.querySelector(".msg-meta");
  if (!metaEl) return;

  const msg = state.messages.find(m => m.id === msgId);
  if (!msg) return;

  const iso = msg.direction === "inbound" ? msg.receivedAt : msg.sentAt;
  const templateBadge = msg.isTemplate ? `<span class="msg-template-badge">template</span>` : "";
  const retryBtn = newStatus === "failed"
    ? `<button class="msg-retry-btn" data-id="${msg.id}">Retry</button>` : "";

  metaEl.innerHTML = `<span class="msg-time">${fmtTime(iso)}</span>${tickHtml(newStatus)}${templateBadge}${retryBtn}`;
}

function isAtBottom(el) {
  return el.scrollHeight - el.scrollTop - el.clientHeight < 60;
}
function scrollToBottom(el) {
  el.scrollTop = el.scrollHeight;
}

/* ── Contact panel ──────────────────────────────────────────────────── */
function renderContactPanel() {
  const contact = state.contact;
  const emptyEl = document.getElementById("contact-panel-empty");
  const detailEl = document.getElementById("contact-detail");

  if (!contact) {
    emptyEl.classList.remove("hidden");
    detailEl.classList.add("hidden");
    return;
  }
  emptyEl.classList.add("hidden");
  detailEl.classList.remove("hidden");

  const cls = avatarClass(contact.phone);
  const ini = initials(contact.displayName || contact.phone);

  const avatarEl = document.getElementById("contact-avatar-lg");
  avatarEl.className = `contact-avatar-lg ${cls}`;
  avatarEl.textContent = ini;

  const nameEl = document.getElementById("contact-name-edit");
  nameEl.textContent = contact.displayName || contact.phone;

  document.getElementById("contact-phone-display").textContent = formatPhone(contact.phone);

  const sessionRow = document.getElementById("contact-session-row");
  if (state.sessionOpen) {
    sessionRow.className = "contact-session-row open";
    sessionRow.textContent = "✓ Session open";
  } else {
    sessionRow.className = "contact-session-row expired";
    sessionRow.textContent = "⚠ Session expired";
  }

  const labels = JSON.parse(contact.labelsJson || "[]");
  const labelsEl = document.getElementById("contact-labels");
  labelsEl.innerHTML = labels.length
    ? labels.map(l => `<span class="contact-label-chip">${esc(l)}</span>`).join("")
    : `<span style="font-size:.72rem;color:#94a3b8">No labels</span>`;
}

/* ── Thread header ──────────────────────────────────────────────────── */
function renderThreadHeader() {
  if (!state.contact) return;
  const contact = state.contact;
  const cls = avatarClass(contact.phone);
  const ini = initials(contact.displayName || contact.phone);

  const avatarEl = document.getElementById("thread-avatar");
  avatarEl.className = `thread-avatar ${cls}`;
  avatarEl.textContent = ini;
  document.getElementById("thread-contact-name").textContent = contact.displayName || contact.phone;
  document.getElementById("thread-contact-phone").textContent = formatPhone(contact.phone);

  const badge = document.getElementById("thread-session-badge");
  if (state.sessionOpen) {
    badge.className = "thread-session-badge open";
    badge.textContent = "Session open";
  } else {
    badge.className = "thread-session-badge expired";
    badge.textContent = "Session expired";
  }
}

/* ── Composer state ─────────────────────────────────────────────────── */
function updateComposer() {
  const sessionWarn = document.getElementById("session-warning");
  const composerRow = document.getElementById("composer-row");
  const templateRow = document.getElementById("template-row");
  const input = document.getElementById("composer-input");
  const sendBtn = document.getElementById("composer-send");

  if (!state.sessionOpen) {
    sessionWarn.classList.remove("hidden");
    composerRow.classList.add("hidden");
    templateRow.classList.remove("hidden");
  } else {
    sessionWarn.classList.add("hidden");
    composerRow.classList.remove("hidden");
    templateRow.classList.add("hidden");
  }

  input.disabled = state.sending;
  sendBtn.disabled = state.sending;
}

/* ── Select a conversation ──────────────────────────────────────────── */
async function selectConversation(convId) {
  if (convId === state.activeConvId && state.messages.length > 0) return;

  state.activeConvId = convId;
  saveUiState();
  state.messages = [];
  state.lastMsgId = null;
  state.loadingThread = true;
  stopMsgPoll();

  // ── Instant header render from already-fetched conv list data ────────
  // No API call needed — the conv list already contains embedded contact.
  const convCached = state.conversations.find(c => c.id === convId);
  if (convCached) {
    // Build contact from embedded field (added to _conv_to_dict)
    state.contact = convCached.contact || {
      id: convCached.contactId,
      phone: convCached.phone,
      displayName: convCached.contactName,
      waId: convCached.waId,
      labelsJson: "[]",
    };
    state.sessionOpen = convCached.sessionOpen ?? true;
    // Immediately clear unread in local state so the badge disappears
    if (convCached.unreadCount > 0) { convCached.unreadCount = 0; }
  }

  document.getElementById("thread-empty").classList.add("hidden");
  document.getElementById("thread-inner").classList.remove("hidden");
  document.getElementById("thread-messages").innerHTML = `
    <div class="thread-loading">
      <div class="loading-dots"><span></span><span></span><span></span></div>
    </div>`;

  // Render header + composer right now — user sees who they're talking to instantly
  renderConvList();
  renderThreadHeader();
  renderContactPanel();
  updateComposer();

  let loadOk = false;
  try {
    // One request: fetch the thread and mark it read server-side.
    const msgData = await api(`/api/whatsapp/conversations/${convId}/messages?mark_read=true`);
    state.messages = msgData.messages;

    if (state.activeConvId === convId && msgData.conversation) {
      const conv = msgData.conversation;
      state.contact = conv.contact || state.contact;
      state.sessionOpen = conv.sessionOpen;
      updateConversationSummary(convId, {
        unreadCount: conv.unreadCount ?? 0,
        lastMessagePreview: conv.lastMessagePreview ?? state.conversations.find(c => c.id === convId)?.lastMessagePreview,
        lastActivityAt: conv.lastActivityAt ?? state.conversations.find(c => c.id === convId)?.lastActivityAt,
        sessionOpen: conv.sessionOpen,
      }, false);
      renderThreadHeader();
      renderContactPanel();
      updateComposer();
    }

    loadOk = true;
  } catch (e) {
    console.error("selectConversation error", e);
    const container = document.getElementById("thread-messages");
    if (container) container.innerHTML = `
      <div style="background:#fee2e2;color:#991b1b;padding:12px;border-radius:8px;font-size:.8rem;margin:12px">
        <strong>Load error:</strong> ${esc(e?.message || String(e))}
      </div>`;
  } finally {
    state.loadingThread = false;
    if (loadOk) renderThread();
    startMsgPoll();
  }
}

/* ── Send reply ─────────────────────────────────────────────────────── */
async function sendReply() {
  const input = document.getElementById("composer-input");
  const body = input.value.trim();
  if (!body || state.sending || !state.activeConvId) return;

  state.sending = true;
  updateComposer();

  const optimisticId = `opt-${Date.now()}`;
  const optimistic = {
    id: optimisticId,
    direction: "outbound",
    body,
    status: "pending",
    sentAt: new Date().toISOString(),
    receivedAt: null, deliveredAt: null, readAt: null,
    isTemplate: false, templateName: null,
  };
  state.messages.push(optimistic);
  appendMessageBubble(optimistic, true);
  input.value = "";
  input.style.height = "auto";

  try {
    const msg = await api(`/api/whatsapp/conversations/${state.activeConvId}/messages`, {
      method: "POST",
      body: JSON.stringify({ body }),
    });

    // Replace optimistic entry in state
    const idx = state.messages.findIndex(m => m.id === optimisticId);
    if (idx !== -1) state.messages[idx] = msg;
    state.lastMsgId = msg.id;

    // Swap the DOM bubble in-place with real data
    const el = document.querySelector(`[data-msg-id="${optimisticId}"]`);
    if (el) {
      el.dataset.msgId = msg.id;
      el.classList.remove("pending");
      el.classList.add(msg.status || "sent");
      const metaEl = el.querySelector(".msg-meta");
      if (metaEl) metaEl.innerHTML = `<span class="msg-time">${fmtTime(msg.sentAt)}</span>${tickHtml(msg.status || "sent")}`;
    }

    if (state.activeConvId) {
      updateConversationSummary(state.activeConvId, {
        lastMessagePreview: body.slice(0, 80),
        lastActivityAt: msg.sentAt,
        unreadCount: 0,
      });
    }
  } catch (e) {
    const idx = state.messages.findIndex(m => m.id === optimisticId);
    if (idx !== -1) state.messages[idx].status = "failed";
    updateMessageBubble(optimisticId, "failed");
    console.error("sendReply error", e);
  } finally {
    state.sending = false;
    updateComposer();
  }
}

/* ── Send template ──────────────────────────────────────────────────── */
async function sendTemplate() {
  const sel = document.getElementById("template-select");
  const templateName = sel.value;
  if (!templateName || state.sending || !state.activeConvId) return;

  state.sending = true;
  updateComposer();

  try {
    const msg = await api(`/api/whatsapp/conversations/${state.activeConvId}/messages`, {
      method: "POST",
      body: JSON.stringify({ template_name: templateName }),
    });
    state.messages.push(msg);
    state.lastMsgId = msg.id;
    sel.value = "";
    state.sessionOpen = true;
    updateComposer();
    appendMessageBubble(msg, true);
    if (state.activeConvId) {
      updateConversationSummary(state.activeConvId, {
        lastMessagePreview: msg.body.slice(0, 80),
        lastActivityAt: msg.sentAt,
        unreadCount: 0,
        sessionOpen: true,
      });
    }
  } catch (e) {
    alert("Template send failed: " + e.message);
  } finally {
    state.sending = false;
    updateComposer();
  }
}

/* ── Load conversations ─────────────────────────────────────────────── */
async function loadConversations() {
  const params = new URLSearchParams({
    status: state.statusFilter,
    search: state.searchTerm,
    page: 1,
  });
  if (state.unreadOnly) params.set("unread", "true");

  try {
    const data = await api(`/api/whatsapp/conversations?${params}`);
    state.conversations = data.conversations.map(c =>
      c.id === state.activeConvId ? { ...c, unreadCount: 0 } : c
    );
    renderConvList();
  } catch (e) {
    console.error("loadConversations error", e);
  }
}

/* ── Fallback polling (when SSE is down) ────────────────────────────── */
async function pollMessages() {
  if (!state.activeConvId || state.loadingThread) return;
  const params = state.lastMsgId ? `?after=${state.lastMsgId}` : "";
  try {
    const data = await api(`/api/whatsapp/conversations/${state.activeConvId}/messages${params}`);
    const newMsgs = data.messages;
    if (!newMsgs.length) return;

    const existingIds = new Set(state.messages.map(m => m.id));
    newMsgs.forEach(m => {
      if (existingIds.has(m.id)) {
        const idx = state.messages.findIndex(x => x.id === m.id);
        if (idx !== -1 && state.messages[idx].status !== m.status) {
          state.messages[idx] = m;
          updateMessageBubble(m.id, m.status);
        }
      } else {
        state.messages.push(m);
        state.lastMsgId = m.id;
        appendMessageBubble(m, true);
        updateConversationSummary(state.activeConvId, {
          lastMessagePreview: m.body.slice(0, 120),
          lastActivityAt: m.sentAt || m.receivedAt || m.createdAt,
          unreadCount: 0,
        });
      }
    });
  } catch { /* silent — poll will retry */ }
}

/* ── Polling timers ─────────────────────────────────────────────────── */
function startConvPoll() {
  stopConvPoll();
  state.convPollTimer = setInterval(() => {
    if (document.visibilityState === "visible") loadConversations();
  }, 5000); // 5 s — fast enough to catch new conversations
}
function stopConvPoll() {
  if (state.convPollTimer) { clearInterval(state.convPollTimer); state.convPollTimer = null; }
}
function startMsgPoll() {
  stopMsgPoll();
  state.msgPollTimer = setInterval(() => {
    if (document.visibilityState === "visible") pollMessages();
  }, 2000); // 2 s — feels near-real-time
}
function stopMsgPoll() {
  if (state.msgPollTimer) { clearInterval(state.msgPollTimer); state.msgPollTimer = null; }
}

function refreshVisibleInbox() {
  if (document.visibilityState === "visible") {
    loadConversations();
    if (state.activeConvId && !state.loadingThread) pollMessages();
  }
}

document.addEventListener("visibilitychange", refreshVisibleInbox);
window.addEventListener("focus", refreshVisibleInbox);

/* ── New conversation dialog ────────────────────────────────────────── */
function openNewConvDialog() {
  populateTemplateSels();
  const dlg = document.getElementById("new-conv-dialog");
  document.getElementById("new-conv-phone").value = "";
  document.getElementById("new-conv-body").value = "";
  document.getElementById("new-conv-error").classList.add("hidden");
  dlg.showModal();
}

async function submitNewConv() {
  const phone = document.getElementById("new-conv-phone").value.trim();
  const body = document.getElementById("new-conv-body").value.trim();
  const templateName = document.getElementById("new-conv-template-select").value;
  const errEl = document.getElementById("new-conv-error");
  errEl.classList.add("hidden");

  if (!phone) { showDialogError(errEl, "Phone number is required."); return; }
  const digitsOnly = phone.replace(/[\s\-().]/g, "");
  if (digitsOnly.length < 11) {
    showDialogError(errEl, "Include the country code — e.g. +1 805 733 2428 for a US number.");
    return;
  }
  if (!body && !templateName) { showDialogError(errEl, "Enter a message or choose a template."); return; }

  const sendBtn = document.getElementById("new-conv-send");
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending…";

  try {
    const payload = { phone };
    if (templateName) payload.template_name = templateName;
    else payload.body = body;

    const result = await api("/api/whatsapp/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    document.getElementById("new-conv-dialog").close();

    const conv = result.conversation;
    if (!state.conversations.find(c => c.id === conv.id)) state.conversations.unshift(conv);
    renderConvList();
    selectConversation(conv.id);
  } catch (e) {
    showDialogError(errEl, e.message || "Send failed.");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send";
  }
}

function showDialogError(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

/* ── Populate template selects ──────────────────────────────────────── */
async function loadTemplates() {
  try {
    const data = await api("/api/whatsapp/templates");
    state.templates = data.templates;
    populateTemplateSels();
  } catch { /* non-fatal */ }
}
function populateTemplateSels() {
  const sels = [
    document.getElementById("template-select"),
    document.getElementById("new-conv-template-select"),
  ];
  sels.forEach(sel => {
    if (!sel) return;
    const val = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    state.templates.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.name;
      opt.textContent = t.label || t.name;
      sel.appendChild(opt);
    });
    sel.value = val;
  });
  const hint = document.getElementById("no-templates-hint");
  if (hint) hint.classList.toggle("hidden", state.templates.length > 0);
}

/* ── Escape HTML ────────────────────────────────────────────────────── */
function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ── Auto-grow textarea ─────────────────────────────────────────────── */
function autoGrow(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

/* ── Wire events ────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  loadUiState();

  const searchInput = document.getElementById("conv-search");
  const unreadToggle = document.getElementById("unread-only-toggle");
  if (searchInput) searchInput.value = state.searchTerm;
  if (unreadToggle) unreadToggle.checked = state.unreadOnly;
  document.querySelectorAll(".cf-pill").forEach(p => {
    p.classList.toggle("active", p.dataset.status === state.statusFilter);
  });

  let searchTimer = null;
  searchInput.addEventListener("input", e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.searchTerm = e.target.value.trim();
      saveUiState();
      renderConvList();
    }, 250);
  });

  document.getElementById("conv-filters").addEventListener("click", e => {
    const pill = e.target.closest(".cf-pill");
    if (!pill) return;
    document.querySelectorAll(".cf-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    state.statusFilter = pill.dataset.status;
    saveUiState();
    loadConversations();
  });

  unreadToggle.addEventListener("change", e => {
    state.unreadOnly = e.target.checked;
    saveUiState();
    renderConvList();
  });

  const input = document.getElementById("composer-input");
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendReply(); }
  });
  input.addEventListener("input", () => autoGrow(input));
  document.getElementById("composer-send").addEventListener("click", sendReply);
  document.getElementById("template-send").addEventListener("click", sendTemplate);

  document.getElementById("btn-new-conv").addEventListener("click", openNewConvDialog);
  document.getElementById("new-conv-close").addEventListener("click", () =>
    document.getElementById("new-conv-dialog").close());
  document.getElementById("new-conv-cancel").addEventListener("click", () =>
    document.getElementById("new-conv-dialog").close());
  document.getElementById("new-conv-send").addEventListener("click", submitNewConv);

  document.getElementById("copy-phone-btn").addEventListener("click", () => {
    const phone = state.contact?.phone;
    if (phone) navigator.clipboard.writeText(phone).catch(() => {});
  });

  const nameEl = document.getElementById("contact-name-edit");
  nameEl.addEventListener("blur", async () => {
    const newName = nameEl.textContent.trim();
    if (!state.contact || newName === state.contact.displayName) return;
    try {
      await api(`/api/whatsapp/contacts/${state.contact.id}`, {
        method: "PATCH",
        body: JSON.stringify({ display_name: newName }),
      });
      state.contact.displayName = newName;
      const c = state.conversations.find(x => x.id === state.activeConvId);
      if (c) c.contactName = newName;
      renderConvList();
      renderThreadHeader();
    } catch {
      nameEl.textContent = state.contact.displayName || state.contact.phone;
    }
  });
  nameEl.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); nameEl.blur(); }
  });

  // Retry failed message via event delegation
  document.getElementById("thread-messages").addEventListener("click", e => {
    const retryBtn = e.target.closest(".msg-retry-btn");
    if (!retryBtn) return;
    const msgId = retryBtn.dataset.id;
    const msg = state.messages.find(m => m.id === msgId);
    if (!msg) return;
    const input = document.getElementById("composer-input");
    input.value = msg.body;
    autoGrow(input);
    state.messages = state.messages.filter(m => m.id !== msgId);
    renderThread();
    input.focus();
  });

  // Boot — polling-based; SSE is available on threaded servers via connectSse()
  (async () => {
    await Promise.all([loadTemplates(), loadConversations()]);
    if (state.activeConvId) {
      const restoreId = state.activeConvId;
      await selectConversation(restoreId);
    }
    startConvPoll();
  })().catch(err => console.error("bootstrap whatsapp inbox failed", err));
});
