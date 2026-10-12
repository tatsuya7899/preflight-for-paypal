// check_panel.cjs — real-behavior verification for extension/panel.html + panel.js
// Stubs chrome.* APIs, drives the actual UI, asserts rendered truth.
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");   // devDependency — see package.json

const PANEL = "file://" + path.resolve(__dirname, "../extension/panel.html");
const VERDICT = JSON.parse(fs.readFileSync(path.resolve(__dirname, "verdict_F.json"), "utf8")).verdict;

// verdict with capture_id + meaning in /check response shape (rules.evaluate output)
const CHECK_RESP = VERDICT; // verdict_F.json's "verdict" is already evaluate()-shaped
CHECK_RESP.capture_id = "3J366679AY2283450";
CHECK_RESP.order_id = "3UJ2460633408874H";
// fixture-mode dispute block — mirrors server._dispute_summary output for the
// disputed capture 3J366679AY2283450 (dispute PP-R-XGB-10190971)
CHECK_RESP.dispute = {
  dispute_id: "PP-R-XGB-10190971",
  reason: "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
  status: "UNDER_REVIEW",
  life_cycle_stage: "CHARGEBACK",
  evidence_types: ["PROOF_OF_FULFILLMENT"],
  source: "fixture (captured sandbox dispute)",
};
// variant with no dispute key — verifies the banner hides honestly
const NO_DISPUTE = JSON.parse(JSON.stringify(CHECK_RESP));
delete NO_DISPUTE.dispute;
NO_DISPUTE.capture_id = "NODISPUTE000000000";

// after-track variant: TRACKING_REQUIRED flips to pass.
// NOTE (review 2026-10-12): this is a HAND-BUILT mutation of the real
// evaluate() output — basis string and summary counts are written by hand and
// can drift if rules.py changes. Regenerate verdict_F.json (gen_mock.py) and
// re-check this block on rule changes; the server-side track→re-check loop
// itself is covered by the fixture-mode tests in tests/test_server.py.
const AFTER = JSON.parse(JSON.stringify(CHECK_RESP));
for (const c of AFTER.checks) {
  if (c.condition === "TRACKING_REQUIRED") {
    c.status = "pass";
    c.basis = "tracker 1Z999AA10123456784 (UPS) found for this capture";
  }
}
// Derive summary counts from the mutated checks so a rules.py status rename
// drifts the labels, not the arithmetic.
AFTER.summary = { n_pass: 0, n_fail: 0, n_not_assessable: 0 };
for (const c of AFTER.checks) AFTER.summary[`n_${c.status}`]++;
AFTER.corrections = [];

let results = [];
const t = (name, ok, extra = "") => { results.push([name, ok, extra]); };

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 400, height: 900 } });

  const calls = [];
  await page.addInitScript(([checkResp, afterResp, noDisputeResp]) => {
    let checkCount = 0;
    window.__calls = [];
    window.chrome = {
      runtime: {
        id: "test-ext",
        lastError: null,
        sendMessage(msg, cb) {
          window.__calls.push(msg);
          setTimeout(() => {
            if (msg.type === "health") cb({ ok: true, status: 200, data: { ok: true, llm: false } });
            else if (msg.type === "check") {
              checkCount++;
              // capture_id payload fails with 404 when the input is actually an
              // order id → exercises the capture→order fallback path
              if (msg.capture_id === "ORDERONLY123456789" && !msg.order_id) {
                cb({ ok: false, status: 404, data: { error: "could not resolve order_id from capture_id" } });
                return;
              }
              if (msg.capture_id === "NODISPUTE000000000") {
                cb({ ok: true, status: 200, data: noDisputeResp });
                return;
              }
              cb({ ok: true, status: 200, data: checkCount <= 1 || msg.order_id === "ORDERONLY123456789" ? checkResp : afterResp });
            }
            else if (msg.type === "track") cb({ ok: true, status: 200, data: { trackers: [{ tracking_number: msg.tracking_number, carrier: msg.carrier }] } });
            else cb({ ok: false, status: 500, data: { error: "unknown" } });
          }, 0);
        },
      },
      tabs: {
        query: () => Promise.resolve([{ id: 7 }]),
        sendMessage(_tabId, msg, cb) {
          if (msg.type === "extract") cb({ confidence: "candidate", candidates: [{ id: "3J366679AY2283450", confidence: "candidate", source: "url_pattern" }] });
          else cb(null);
        },
      },
      storage: { local: { get: () => Promise.resolve({}) } },
    };
  }, [CHECK_RESP, AFTER, NO_DISPUTE]);

  await page.goto(PANEL);
  await page.waitForTimeout(300);

  // 1. health chip shows live + LLM unavailable
  t("data:live chip", await page.locator("#dataState").innerText() === "live");
  t("LLM unavailable", (await page.locator("#llmState").innerText()) === "unavailable");

  // 2. candidate chip rendered from extract
  const chip = page.locator(".cand-chip");
  t("extract candidate chip", (await chip.count()) === 1);
  await chip.first().click();
  t("chip fills input", (await page.locator("#capInput").inputValue()) === "3J366679AY2283450");

  // 3. run Check
  await page.locator("#btnCheck").click();
  await page.waitForTimeout(200);

  // 4. summary counts from verdict
  const chipNums = await page.locator(".chip .n").allInnerTexts();
  t("summary 2/2/3", chipNums.join("/") === "2/2/3", chipNums.join("/"));

  // 5. 7 cards rendered, fail card has rx, pass card has none
  t("7 check cards", (await page.locator(".card").count()) === 7);
  const failCard = page.locator(".card.fail").first();
  t("fail card shows rx", (await failCard.locator(".c-rx").count()) === 1);
  const passCard = page.locator(".card.pass").first();
  t("pass card hides rx", (await passCard.locator(".c-rx").count()) === 0);

  // 6. flags box: ELIGIBLE + declared-data label
  t("flag label", (await page.locator(".flag-label").innerText()) === "DECLARED-DATA SNAPSHOT");
  t("flag ELIGIBLE", await page.locator(".flag-status").innerText() === "ELIGIBLE");

  // 7. semantic: ran=false notice + 1 warning + 3 unassessable
  t("semantic not-run notice", await page.locator("text=Semantic layer not run").isVisible());
  t("1 fraud warning", (await page.locator(".sem-card").nth(1).locator(".sem-item").count()) === 1);
  t("3 unassessable", (await page.locator(".sem-card").nth(2).locator(".sem-item").count()) === 3);

  // 8. slots: PoDA unfillable / TRACKING_INFO+PoF fillable (derived rule)
  const slotOf = (id) => page.locator(id).getAttribute("class");
  t("PoDA slot unfillable", (await slotOf("#slot-PROOF_OF_DELIVERY_ADDRESS")).includes("unfillable"));
  t("TRACKING slot fillable", (await slotOf("#slot-TRACKING_INFORMATION")).includes("fillable"));
  t("PoF slot fillable", (await slotOf("#slot-PROOF_OF_FULFILLMENT")).includes("fillable"));
  // no real-case badge, but the fixture dispute banner IS wired now
  t("no real-case badge", (await page.locator(".badge-case").count()) === 0);
  t("dispute banner visible", await page.locator("#disputeBanner").isVisible());
  t("banner names dispute id", (await page.locator("#bannerMain").innerText()).includes("PP-R-XGB-10190971"));
  // Act-3 correspondence: the slot the dispute record asks for is marked
  t("PoF slot marked requested-in-dispute",
    (await page.locator("#slot-PROOF_OF_FULFILLMENT .req-note").allInnerTexts()).join("").includes("PP-R-XGB-10190971"));
  t("PoDA slot not marked", (await page.locator("#slot-PROOF_OF_DELIVERY_ADDRESS .req-note").count()) === 0);

  // 9. fix section shows register tracking
  t("fix form visible", await page.locator("#fixForm").isVisible());
  t("track btn visible", await page.locator("#btnTrack").isVisible());

  // 10. OTHER carrier reveals name field + validation
  await page.locator("#carrierSel").selectOption("OTHER");
  t("OTHER reveals name input", await page.locator("#carrierOther").isVisible());
  await page.locator("#trackNum").fill("1Z999");
  await page.locator("#btnTrack").click();
  await page.waitForTimeout(100);
  t("OTHER requires name", (await page.locator("#fixNote").innerText()).includes("carrier name"));

  // 11. successful track → auto re-check → before/after updates
  await page.locator("#carrierSel").selectOption("UPS");
  await page.locator("#btnTrack").click();
  await page.waitForTimeout(300);
  const trackCalls = await page.evaluate(() => window.__calls.filter(c => c.type === "track").length);
  const checkCalls = await page.evaluate(() => window.__calls.filter(c => c.type === "check").length);
  t("track called once", trackCalls === 1);
  t("re-check after track", checkCalls === 2);
  // after verdict: TRACKING_REQUIRED now pass → before/after shows the flip
  const baText = (await page.locator("#baBefore").innerText()).split("").filter(c => c !== "​").join("");
  t("before shows old fail", baText.includes("TRACKING_REQUIRED"));
  const summary2 = await page.locator(".chip .n").allInnerTexts();
  t("summary updated 3/1/3", summary2.join("/") === "3/1/3", summary2.join("/"));
  // fix form hidden after corrections empty
  t("fix hidden when no corrections", !(await page.locator("#btnTrack").isVisible()));

  // 11b. fallback: order-id-only input retries with order_id after capture 404
  await page.locator("#capInput").fill("ORDERONLY123456789");
  await page.locator("#btnCheck").click();
  await page.waitForTimeout(200);
  const orderRetry = await page.evaluate(() => window.__calls.filter(c => c.type === "check" && c.order_id === "ORDERONLY123456789").length);
  t("capture 404 → order_id retry", orderRetry === 1, String(orderRetry));
  t("fallback renders verdict", (await page.locator(".card").count()) === 7);

  // 12. horizontal strip nav works
  await page.locator("#stripNext").click();
  await page.waitForTimeout(400);
  const sl = await page.evaluate(() => document.getElementById("strip").scrollLeft);
  t("strip scrolled", sl > 100, String(Math.round(sl)));

  // 12b. verdict without dispute key hides the banner honestly
  await page.locator("#capInput").fill("NODISPUTE000000000");
  await page.locator("#btnCheck").click();
  await page.waitForTimeout(200);
  t("banner hidden without dispute", !(await page.locator("#disputeBanner").isVisible()));
  t("no requested marks without dispute", (await page.locator(".req-note").count()) === 0);

  // 13. error path: check with empty id
  await page.locator("#capInput").fill("");
  await page.locator("#btnCheck").click();
  await page.waitForTimeout(50);
  t("empty id warning", (await page.locator("#loadNote").innerText()).includes("Enter"));

  await browser.close();

  let fails = 0;
  for (const [name, ok, extra] of results) {
    console.log(`${ok ? "✓" : "✗"} ${name}${extra ? "  (" + extra + ")" : ""}`);
    if (!ok) fails++;
  }
  console.log(`FAIL: ${fails}`);
  process.exit(fails ? 1 : 0);
})();
