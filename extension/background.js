// background.js — MV3 service worker.
//
// Design source: SPEC-preflight-checker_design.md
//   - "方式": extension is a thin UI shell; all PayPal/LLM logic lives in
//     backend/server.py (localhost:8000).
//   - "非機能": "backendへの全fetchはpanel.js/service workerからのみ"
//     (content.js must never fetch backend directly).
//   - API contract: POST /check {capture_id|order_id} -> verdict,
//     POST /track {capture_id, tracking_number, carrier, carrier_name_other?}
//     with header X-Preflight-Token, GET /health -> {ok, llm}.

const BACKEND_BASE = "http://127.0.0.1:8000";

chrome.action.onClicked.addListener((tab) => {
  if (tab && tab.windowId !== undefined) {
    chrome.sidePanel.open({ windowId: tab.windowId });
  }
});

async function getStoredToken() {
  const { preflightToken } = await chrome.storage.local.get("preflightToken");
  return preflightToken || null;
}

async function doCheck(payload) {
  const resp = await fetch(`${BACKEND_BASE}/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok, status: resp.status, data };
}

async function doTrack(payload) {
  const token = await getStoredToken();
  const resp = await fetch(`${BACKEND_BASE}/track`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Preflight-Token": token || "",
    },
    body: JSON.stringify(payload),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok, status: resp.status, data };
}

async function doHealth() {
  try {
    const resp = await fetch(`${BACKEND_BASE}/health`, { method: "GET" });
    const data = await resp.json().catch(() => ({}));
    return { ok: resp.ok, status: resp.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { error: String(err) } };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "check") {
    const { capture_id, order_id } = message;
    doCheck({ capture_id, order_id }).then(sendResponse).catch((err) => {
      sendResponse({ ok: false, status: 0, data: { error: String(err) } });
    });
    return true; // keep the message channel open for the async response
  }

  if (message.type === "track") {
    const { capture_id, tracking_number, carrier, carrier_name_other } = message;
    doTrack({ capture_id, tracking_number, carrier, carrier_name_other })
      .then(sendResponse)
      .catch((err) => {
        sendResponse({ ok: false, status: 0, data: { error: String(err) } });
      });
    return true;
  }

  if (message.type === "health") {
    doHealth().then(sendResponse).catch((err) => {
      sendResponse({ ok: false, status: 0, data: { error: String(err) } });
    });
    return true;
  }

  return false;
});
