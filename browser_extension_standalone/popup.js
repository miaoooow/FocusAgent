const $ = (selector) => document.querySelector(selector);
const goalInput = $("#goal");
const durationInput = $("#duration");
const domainsInput = $("#domains");
const message = $("#message");

const domainHints = [
  { keys: ["代码", "编程", "python", "开发"], domains: ["github.com", "stackoverflow.com", "docs.python.org"] },
  { keys: ["文档", "报告", "论文"], domains: ["docs.google.com", "office.com", "cnki.net"] },
  { keys: ["课程", "作业", "学习"], domains: ["bilibili.com", "coursera.org", "icourse163.org"] },
  { keys: ["设计", "原型"], domains: ["figma.com", "canva.com"] },
];

function send(type, payload) {
  return chrome.runtime.sendMessage({ type, payload });
}

function parseDomains() {
  return domainsInput.value
    .split(/[\n,，\s]+/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function addDomain(domain) {
  const current = parseDomains();
  if (!current.includes(domain)) current.push(domain);
  domainsInput.value = current.join("\n");
}

function renderSuggestions() {
  const goal = goalInput.value.toLowerCase();
  const matches = domainHints
    .filter((item) => item.keys.some((key) => goal.includes(key)))
    .flatMap((item) => item.domains);
  const unique = [...new Set(matches)].slice(0, 6);
  $("#suggestions").innerHTML = "";
  unique.forEach((domain) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `＋ ${domain}`;
    button.addEventListener("click", () => addDomain(domain));
    $("#suggestions").append(button);
  });
}

function formatTime(milliseconds) {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function render(state) {
  const session = state?.session;
  const active = session && ["running", "paused", "finished"].includes(session.status);
  $("#planner").hidden = Boolean(active);
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
  const response = await send("state");
  if (response?.ok) render(response.state);
}

goalInput.addEventListener("input", () => {
  const match = goalInput.value.match(/(\d{1,3})\s*分钟/);
  if (match) durationInput.value = Math.min(240, Math.max(1, Number(match[1])));
  renderSuggestions();
});

$("#start").addEventListener("click", async () => {
  message.textContent = "";
  const response = await send("start", {
    goal: goalInput.value,
    durationMinutes: Number(durationInput.value),
    allowedDomains: parseDomains(),
  });
  if (!response?.ok) {
    message.textContent = response?.error || "暂时无法开始";
    return;
  }
  render(response.state);
});

$("#pause").addEventListener("click", async () => {
  const state = (await send("state")).state;
  const response = await send(state?.session?.status === "paused" ? "resume" : "pause");
  if (response?.ok) render(response.state);
});

$("#stop").addEventListener("click", async () => {
  const response = await send("stop");
  if (response?.ok) render(response.state);
});

refresh();
setInterval(refresh, 1000);
