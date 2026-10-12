// record_demo.cjs — records the 3-act demo of extension/panel.html against the
// REAL fixture backend (honest recording: real HTTP to 127.0.0.1, real verdicts).
// Output: demo/demo.webm (playwright recordVideo).
//
// chrome.* is stubbed to route messages straight to the fixture server via
// fetch — same request shapes as background.js — so every pixel on screen is
// produced by the real backend, not canned JSON.
const path = require("path");
const fs = require("fs");
const os = require("os");
const { spawn } = require("child_process");
const { chromium } = require("playwright");   // devDependency — see package.json

const ROOT = path.resolve(__dirname, "..");
const PANEL = "file://" + path.join(ROOT, "extension/panel.html");
const OUT_DIR = path.join(ROOT, "demo");
const TOKEN_PATH = path.join(os.homedir(), ".config/studio/preflight-token");
// 8765, not the default 8000: a `zenn preview` dev server squats on *:8000 on
// this machine and (via IPv6 v4-mapped sockets) steals some 127.0.0.1:8000
// connections, which produced a false-positive /health and a 403 on /track.
const PORT = 8765;
const BASE = `http://127.0.0.1:${PORT}`;

const CAPTURE_ID = "3J366679AY2283450";   // order F — disputed, main demo
const TRACKING = "1Z999AA10123456784";

function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }

// /health must be answered by OUR server, not by any squatter on :8000 — a
// `zenn preview` dev server occupies *:8000 on this machine and its 200 reply
// false-positive'd waitHealth, which made the script read a stale token and
// /track then 403'd mid-recording. Require the app's own marker field.
async function isOurs(resp) {
  if (!resp.ok) return false;
  const j = await resp.json().catch(() => null);
  return !!(j && typeof j === "object" && "fixture" in j);
}

async function waitHealth(tries = 60) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(`${BASE}/health`);
      const ours = await isOurs(r);
      if (i < 8 || ours) console.log(`health[${i}] status=${r.status} ours=${ours}`);
      if (ours) return true;
    } catch (e) {
      if (i < 8) console.log(`health[${i}] err=${e.message}`);
    }
    await wait(250);
  }
  return false;
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  // 1. boot the real fixture server on a dedicated port.
  //    Guard: abort if a stale preflight server already answers /health there
  //    (it would hold a different token and 403 /track mid-recording).
  //    NOTE: on this machine a `zenn preview` squats on *:8000 — that is why
  //    PORT is 8765, not the app default.
  if (await fetch(`${BASE}/health`).then(isOurs).catch(() => false)) {
    throw new Error(
      `port ${PORT} already serves a preflight server — kill it and re-run`);
  }

  const srv = spawn("python3", ["-m", "backend.server", "--fixture"], {
    cwd: ROOT, stdio: ["ignore", "ignore", "pipe"],
    env: { ...process.env, PREFLIGHT_PORT: String(PORT) },
  });
  srv.stderr.on("data", (d) => process.stderr.write("[srv] " + d));
  try {
    if (!(await waitHealth())) {
      console.log(`srv exitCode=${srv.exitCode} killed=${srv.killed} pid=${srv.pid}`);
      throw new Error("fixture server did not come up");
    }
    const token = fs.readFileSync(TOKEN_PATH, "utf8").trim();

    // Auth pre-flight: prove the spawned server accepts this token BEFORE
    // recording, so a broken video is never produced silently. Probing with a
    // bogus capture_id keeps the fixture tracker store clean (auth is checked
    // first; 404 means the token passed, 403 means it did not).
    const probe = await fetch(`${BASE}/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Preflight-Token": token },
      body: JSON.stringify({ capture_id: "AUTHPROBE000000000", tracking_number: "1Z999AA10123456784", carrier: "UPS" }),
    });
    if (probe.status !== 404) {
      throw new Error(`auth probe failed: expected 404 got HTTP ${probe.status} ${await probe.text()}`);
    }
    console.log("auth probe ok");

    // 2. browser context with video recording
    const browser = await chromium.launch();
    const context = await browser.newContext({
      viewport: { width: 420, height: 860 },
      recordVideo: { dir: OUT_DIR, size: { width: 420, height: 860 } },
    });
    const page = await context.newPage();
    page.on("console", (m) => { if (m.type() === "error") console.log("[page]", m.text()); });

    // 2b. file:// pages are subject to CORS on localhost fetches — the real
    // extension is not (host_permissions). Intercept at the route layer and
    // satisfy preflight/headers so the REAL backend logic still serves every
    // byte; only the transport shim is synthetic.
    await context.route(`${BASE}/**`, async (route) => {
      if (route.request().method() === "OPTIONS") {
        return route.fulfill({
          status: 204,
          headers: {
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET, POST, OPTIONS",
            "access-control-allow-headers": "content-type, x-preflight-token",
          },
        });
      }
      const resp = await route.fetch();
      await route.fulfill({
        response: resp,
        headers: { ...resp.headers(), "access-control-allow-origin": "*" },
      });
    });

    // 3. chrome.* stub → real fixture backend via fetch (background.js shapes)
    await page.addInitScript(([base, token]) => {
      async function api(path, body) {
        const r = await fetch(base + path, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Preflight-Token": token },
          body: JSON.stringify(body),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) console.error(`[api] ${path} -> HTTP ${r.status}: ${JSON.stringify(data).slice(0, 160)}`);
        return { ok: r.ok, status: r.status, data };
      }
      window.chrome = {
        runtime: {
          id: "demo-ext", lastError: null,
          sendMessage(msg, cb) {
            setTimeout(async () => {
              if (msg.type === "health") {
                try {
                  const r = await fetch(base + "/health");
                  cb({ ok: r.ok, status: r.status, data: await r.json() });
                } catch (e) { cb({ ok: false, status: 0, data: { error: String(e) } }); }
              } else if (msg.type === "check") {
                cb(await api("/check", { capture_id: msg.capture_id, order_id: msg.order_id }));
              } else if (msg.type === "track") {
                cb(await api("/track", {
                  capture_id: msg.capture_id, tracking_number: msg.tracking_number,
                  carrier: msg.carrier, carrier_name_other: msg.carrier_name_other,
                }));
              } else cb({ ok: false, status: 500, data: { error: "unknown" } });
            }, 0);
          },
        },
        tabs: { query: () => Promise.resolve([{ id: 1 }]), sendMessage: (_id, _m, cb) => cb(null) },
        storage: { local: { get: () => Promise.resolve({}) } },
      };
    }, [BASE, token]);

    // Absolute-timeline helper — the narration track (demo/subtitles_en.srt)
    // runs 0:00–2:00, so screen action must hold each beat for its whole
    // subtitle window rather than racing through it.
    const t0 = Date.now();
    const until = async (sec) => {
      const d = t0 + sec * 1000 - Date.now();
      if (d > 0) await wait(d);
    };

    /* ---------- Act 1 — diagnosis (0:00–0:40) ---------- */
    await page.goto(PANEL);
    await until(4);                                         // health chips settle ("fixture")
    await page.locator("#capInput").fill(CAPTURE_ID);
    await until(8);
    await page.locator("#btnCheck").click();
    await until(12);                                        // verdict renders
    // 0:12–0:26 — slow pass over the diagnostic cards / flags
    for (let y = 0; y <= 1400; y += 200) {
      await page.evaluate((v) => window.scrollTo(0, v), y);
      await wait(1700);
    }
    // 0:26–0:40 — dwell on the evidence slots
    await page.evaluate(() => document.getElementById("slot-TRACKING_INFORMATION").scrollIntoView({ block: "center" }));
    await until(40);

    /* ---------- Act 2 — corrective loop (0:40–1:10) ---------- */
    await page.evaluate(() => document.getElementById("fixTitle").scrollIntoView({ block: "center" }));
    await until(44);
    await page.locator("#carrierSel").selectOption("UPS");
    await until(48);
    await page.locator("#trackNum").fill(TRACKING);
    await until(52);
    await page.locator("#btnTrack").click();
    await until(56);                                        // register + auto re-check
    // 0:56–1:10 — BEFORE/AFTER flip reads (TRACKING_REQUIRED fail → pass)
    await page.evaluate(() => document.getElementById("baBefore").scrollIntoView({ block: "center" }));
    await until(70);

    /* ---------- Act 3 — dispute correspondence (1:10–1:50) ---------- */
    await page.evaluate(() => document.getElementById("disputeBanner").scrollIntoView({ block: "center" }));
    await until(82);                                        // 1:10–1:22 banner reads
    await page.evaluate(() => document.getElementById("slot-PROOF_OF_FULFILLMENT").scrollIntoView({ block: "center" }));
    await until(98);                                        // 1:22–1:38 marker reads
    await until(110);                                       // hold through 1:50
    // closing (1:50–2:00) — back to top summary
    await page.evaluate(() => window.scrollTo(0, 0));
    await until(120);

    // Content assertions — a video whose pixels show an error state must fail
    // loudly here instead of shipping silently.
    const shot = await page.evaluate(() => {
      // panel.js brk() inserts ZWSP for line-breaking — strip before matching.
      const txt = (id) =>
        ((document.getElementById(id) || {}).textContent || "").replace(/\u200b/g, "");
      const banner = document.getElementById("disputeBanner");
      return {
        disputeVisible: !!(banner && !banner.hidden && banner.textContent.includes("PP-R-XGB-10190971")),
        requestedBadge: txt("slot-PROOF_OF_FULFILLMENT").includes("in dispute"),
        baBefore: txt("baBefore"),
        baAfter: txt("baAfter"),
        fixNote: txt("fixNote"),
      };
    });
    const problems = [];
    if (!shot.disputeVisible) problems.push("dispute banner missing/hidden");
    if (!shot.requestedBadge) problems.push("requested-in-dispute marker missing");
    if (!/TRACKING_REQUIRED/.test(shot.baBefore) || !/fail/.test(shot.baBefore))
      problems.push(`BEFORE row wrong: ${shot.baBefore.slice(0, 80)}`);
    if (!/TRACKING_REQUIRED/.test(shot.baAfter) || !/pass/.test(shot.baAfter))
      problems.push(`AFTER row wrong: ${shot.baAfter.slice(0, 80)}`);
    if (shot.fixNote !== "registered — re-check complete")
      problems.push(`fixNote: ${shot.fixNote}`);
    if (problems.length) throw new Error("recording assertions failed: " + problems.join("; "));
    console.log("content assertions ok");

    await context.close();                                  // finalize video
    await browser.close();
    const vids = fs.readdirSync(OUT_DIR)
      .filter((f) => f.endsWith(".webm") && f !== "demo.webm")
      .map((f) => ({ f, t: fs.statSync(path.join(OUT_DIR, f)).mtimeMs }))
      .sort((a, b) => b.t - a.t);
    if (!vids.length) throw new Error("no video produced");
    fs.renameSync(path.join(OUT_DIR, vids[0].f), path.join(OUT_DIR, "demo.webm"));
    console.log("recorded: demo/demo.webm");
  } finally {
    srv.kill();
  }
  process.exit(0);
})();
