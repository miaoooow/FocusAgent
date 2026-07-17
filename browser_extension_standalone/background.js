const STORAGE_KEY = "focusBuddyBrowserState";
const VIOLATION_ALARM = "focus-buddy-violation";
const END_ALARM = "focus-buddy-end";
const CAT_ICON =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" rx="30" fill="#173f32"/><path d="M29 51 35 22l23 18h13l23-18 6 29c9 9 13 21 11 35-4 24-22 35-47 35S21 110 17 86c-2-14 3-27 12-35Z" fill="#d8f28b"/><circle cx="48" cy="68" r="5" fill="#173f32"/><circle cx="80" cy="68" r="5" fill="#173f32"/><path d="M57 81q7 8 14 0" fill="none" stroke="#173f32" stroke-width="5" stroke-linecap="round"/></svg>'
  );

const defaultState = () => ({
  session: null,
  pendingViolation: null,
  totalMinutes: 0,
  coins: 0,
  completedSessions: 0,
});

async function readState() {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  return { ...defaultState(), ...(stored[STORAGE_KEY] || {}) };
}

async function writeState(state) {
  await chrome.storage.local.set({ [STORAGE_KEY]: state });
  return state;
}

function normalizeDomain(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  try {
    const url = raw.includes("://") ? new URL(raw) : new URL(`https://${raw}`);
    return url.hostname.replace(/^www\./, "");
  } catch {
    return raw.replace(/^www\./, "").split("/")[0];
  }
}

function isAllowed(hostname, domains) {
  const host = normalizeDomain(hostname);
  return domains.some((item) => host === item || host.endsWith(`.${item}`));
}

async function clearViolation(state) {
  await chrome.alarms.clear(VIOLATION_ALARM);
  if (state.pendingViolation) {
    state.pendingViolation = null;
    await writeState(state);
  }
}

async function showNotification(title, message) {
  try {
    await chrome.notifications.create({
      type: "basic",
      iconUrl: CAT_ICON,
      title,
      message,
      priority: 1,
    });
  } catch {
    await chrome.action.setBadgeBackgroundColor({ color: "#d65b5b" });
    await chrome.action.setBadgeText({ text: "!" });
  }
}

async function finishSession(state) {
  if (!state.session || state.session.status === "finished") return state;
  const minutes = Math.max(1, Math.round(state.session.durationSeconds / 60));
  const cleanBonus = state.session.driftCount === 0 ? 5 : 0;
  state.totalMinutes += minutes;
  state.coins += Math.max(2, Math.round(minutes / 5) + cleanBonus - state.session.driftCount * 2);
  state.completedSessions += 1;
  state.session = { ...state.session, status: "finished", finishedAt: Date.now() };
  state.pendingViolation = null;
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.clear(END_ALARM);
  await writeState(state);
  await chrome.action.setBadgeBackgroundColor({ color: "#7ca65c" });
  await chrome.action.setBadgeText({ text: "✓" });
  await showNotification("Luna：这轮守住了", "专注完成，猫币已经放进小鱼干罐。");
  return state;
}

async function evaluateActiveTab() {
  const state = await readState();
  const session = state.session;
  if (!session || session.status !== "running") return;
  if (Date.now() >= session.endAt) {
    await finishSession(state);
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab || !tab.url || tab.url.startsWith("chrome-extension://")) {
    await clearViolation(state);
    return;
  }

  let host = "";
  try {
    host = normalizeDomain(new URL(tab.url).hostname);
  } catch {
    await clearViolation(state);
    return;
  }

  if (!host || isAllowed(host, session.allowedDomains)) {
    await clearViolation(state);
    await chrome.action.setBadgeText({ text: "" });
    return;
  }

  if (state.pendingViolation?.host === host && state.pendingViolation?.tabId === tab.id) {
    return;
  }
  state.pendingViolation = { host, tabId: tab.id, startedAt: Date.now() };
  await writeState(state);
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.create(VIOLATION_ALARM, { when: Date.now() + session.graceSeconds * 1000 });
}

async function confirmViolation() {
  const state = await readState();
  const session = state.session;
  const pending = state.pendingViolation;
  if (!session || session.status !== "running" || !pending) return;

  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  let host = "";
  try {
    host = tab?.url ? normalizeDomain(new URL(tab.url).hostname) : "";
  } catch {
    host = "";
  }
  if (!host || host !== pending.host || isAllowed(host, session.allowedDomains)) {
    await clearViolation(state);
    return;
  }

  session.driftCount += 1;
  state.pendingViolation = null;
  await writeState(state);
  await chrome.action.setBadgeBackgroundColor({ color: "#d65b5b" });
  await chrome.action.setBadgeText({ text: String(Math.min(9, session.driftCount)) });
  const lines = [
    `${host} 今天也没打算替你交作业。`,
    `Luna 看见你绕路了：${host}`,
    `这页很会留人，可你的目标还在等。`,
    `逛得挺丝滑，进度条可没跟上。`,
  ];
  await showNotification("Focus Buddy · 走神提醒", lines[(session.driftCount - 1) % lines.length]);
}

async function startSession(payload) {
  const state = await readState();
  const durationMinutes = Math.max(1, Math.min(240, Number(payload.durationMinutes) || 25));
  const allowedDomains = [...new Set((payload.allowedDomains || []).map(normalizeDomain).filter(Boolean))];
  if (!String(payload.goal || "").trim()) throw new Error("请先写下这一轮的目标");
  if (!allowedDomains.length) throw new Error("至少添加一个允许访问的网站域名");

  const now = Date.now();
  state.session = {
    goal: String(payload.goal).trim().slice(0, 180),
    durationSeconds: durationMinutes * 60,
    startedAt: now,
    endAt: now + durationMinutes * 60 * 1000,
    remainingWhenPaused: null,
    status: "running",
    allowedDomains,
    graceSeconds: 8,
    driftCount: 0,
  };
  state.pendingViolation = null;
  await writeState(state);
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.create(END_ALARM, { when: state.session.endAt });
  await chrome.action.setBadgeText({ text: "" });
  await evaluateActiveTab();
  return state;
}

async function pauseSession() {
  const state = await readState();
  if (state.session?.status === "running") {
    state.session.remainingWhenPaused = Math.max(0, state.session.endAt - Date.now());
    state.session.status = "paused";
    state.pendingViolation = null;
    await chrome.alarms.clear(VIOLATION_ALARM);
    await chrome.alarms.clear(END_ALARM);
    await writeState(state);
  }
  return state;
}

async function resumeSession() {
  const state = await readState();
  if (state.session?.status === "paused") {
    state.session.endAt = Date.now() + Math.max(1000, state.session.remainingWhenPaused || 1000);
    state.session.remainingWhenPaused = null;
    state.session.status = "running";
    await writeState(state);
    await chrome.alarms.create(END_ALARM, { when: state.session.endAt });
    await evaluateActiveTab();
  }
  return state;
}

async function stopSession() {
  const state = await readState();
  state.session = null;
  state.pendingViolation = null;
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.clear(END_ALARM);
  await chrome.action.setBadgeText({ text: "" });
  return writeState(state);
}

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get(STORAGE_KEY);
  if (!current[STORAGE_KEY]) await writeState(defaultState());
});

chrome.tabs.onActivated.addListener(() => evaluateActiveTab());
chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (changeInfo.url || changeInfo.status === "complete") evaluateActiveTab();
});
chrome.windows.onFocusChanged.addListener(() => evaluateActiveTab());
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === VIOLATION_ALARM) await confirmViolation();
  if (alarm.name === END_ALARM) await finishSession(await readState());
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    state: readState,
    start: () => startSession(message.payload || {}),
    pause: pauseSession,
    resume: resumeSession,
    stop: stopSession,
  };
  const action = actions[message.type];
  if (!action) {
    sendResponse({ ok: false, error: "未知操作" });
    return false;
  }
  action()
    .then((state) => sendResponse({ ok: true, state }))
    .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
  return true;
});
