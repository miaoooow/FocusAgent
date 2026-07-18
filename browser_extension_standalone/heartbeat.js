const HEARTBEAT_INTERVAL_MS = 2000;

function publishDesktopHeartbeat() {
  if (document.visibilityState !== "visible") return;
  try {
    Promise.resolve(
      chrome.runtime.sendMessage({ type: "focus-desktop-heartbeat" })
    ).catch(() => {});
  } catch {
    // The service worker can restart between heartbeats; the next tick retries.
  }
}

publishDesktopHeartbeat();
document.addEventListener("visibilitychange", publishDesktopHeartbeat);
setInterval(publishDesktopHeartbeat, HEARTBEAT_INTERVAL_MS);
