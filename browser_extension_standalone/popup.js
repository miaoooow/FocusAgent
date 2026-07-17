const $ = (selector) => document.querySelector(selector);
const message = $("#message");

function send(type, payload) {
  return chrome.runtime.sendMessage({ type, payload });
}

function formatTime(milliseconds) {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function render(state) {
  const session = state?.session;
  const active = session && ["running", "paused", "finished"].includes(session.status);
  $("#launcher").hidden = Boolean(active);
  $("#session").hidden = !active;
  $("#coins").textContent = state?.coins || 0;
  $("#total-minutes").textContent = state?.totalMinutes || 0;
  if (!active) {
    $("#status-pill").textContent = "待机";
    return;
  }

  $("#session-goal").textContent = session.goal;
  $("#drifts").textContent = session.driftCount || 0;
  $("#domain-summary").textContent = `允许：${session.allowedDomains.join(" · ")}`;
  const remaining =
    session.status === "paused" ? session.remainingWhenPaused : Math.max(0, session.endAt - Date.now());
  $("#timer").textContent = session.status === "finished" ? "完成" : formatTime(remaining);
  $("#status-pill").textContent =
    session.status === "running" ? "专注中" : session.status === "paused" ? "已暂停" : "已完成";
  $("#pause").textContent = session.status === "paused" ? "继续" : "暂停";
}

async function refresh() {
  const [stateResponse, tabResponse] = await Promise.all([
    send("state"),
    send("activeTab"),
  ]);
  if (stateResponse?.ok) render(stateResponse.state);
  const domain = tabResponse?.state?.domain;
  $("#current-domain").textContent = domain || "浏览器内部页面";
}

async function openFocusPage() {
  const tabResponse = await send("activeTab");
  const domain = tabResponse?.state?.domain || "";
  const page = new URL(chrome.runtime.getURL("focus.html"));
  if (domain) page.searchParams.set("domain", domain);
  await chrome.tabs.create({ url: page.toString() });
  window.close();
}

$("#pause").addEventListener("click", async () => {
  const state = (await send("state")).state;
  const response = await send(state?.session?.status === "paused" ? "resume" : "pause");
  if (response?.ok) render(response.state);
});

$("#stop").addEventListener("click", async () => {
  const response = await send("stop");
  if (response?.ok) render(response.state);
});

$("#open-focus").addEventListener("click", openFocusPage);
$("#open-session").addEventListener("click", openFocusPage);

refresh();
setInterval(refresh, 1000);
