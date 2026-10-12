// Minimal reproduction probe: does a page-side fetch to /track carry the
// X-Preflight-Token header through playwright's route.fetch() shim?
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");
const BASE = "http://127.0.0.1:8765";
const token = fs.readFileSync(process.env.HOME + "/.config/studio/preflight-token", "utf8").trim();

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  await context.route(BASE + "/**", async (route) => {
    const req = route.request();
    console.log("[route]", req.method(), req.url(), "xtoken=" + (req.headers()["x-preflight-token"] || "ABSENT"));
    if (req.method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, POST, OPTIONS",
        "access-control-allow-headers": "content-type, x-preflight-token" } });
    }
    const resp = await route.fetch();
    await route.fulfill({ response: resp, headers: { ...resp.headers(), "access-control-allow-origin": "*" } });
  });
  const page = await context.newPage();
  await page.addInitScript(([base, tok]) => { window.__tok = tok; window.__base = base; }, [BASE, token]);
  await page.goto("data:text/html,<html></html>");
  const r = await page.evaluate(async () => {
    const resp = await fetch(window.__base + "/track", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Preflight-Token": window.__tok },
      body: JSON.stringify({ capture_id: "3J366679AY2283450", tracking_number: "1Z999", carrier: "UPS" }),
    });
    return { status: resp.status, body: await resp.text() };
  });
  console.log("RESULT", r.status, r.body.slice(0, 140));
  await browser.close();
})();
