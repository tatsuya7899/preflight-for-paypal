const path = require("path");
const fs = require("fs");
const { chromium } = require(path.join(
  "/Users/tatsuyasasaki/Developer/tatsuyasasaki-portfolio/node_modules", "playwright"));

const PANEL = "file://" + path.resolve(__dirname, "../extension/panel.html");
const VERDICT = JSON.parse(fs.readFileSync(path.resolve(__dirname, "verdict_F.json"), "utf8")).verdict;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 380, height: 1000 } });
  await page.addInitScript(([checkResp]) => {
    window.chrome = {
      runtime: {
        id: "x", lastError: null,
        sendMessage(msg, cb) {
          setTimeout(() => {
            if (msg.type === "health") cb({ ok: true, status: 200, data: { ok: true, llm: false } });
            else if (msg.type === "check") cb({ ok: true, status: 200, data: checkResp });
            else cb({ ok: false, status: 500, data: {} });
          }, 0);
        },
      },
      tabs: {
        query: () => Promise.resolve([{ id: 1 }]),
        sendMessage: (_id, _m, cb) => cb({ confidence: "candidate", candidates: [{ id: "3J366679AY2283450", confidence: "candidate", source: "url_pattern" }] }),
      },
    };
  }, [VERDICT]);
  await page.goto(PANEL);
  await page.waitForTimeout(300);
  await page.locator(".cand-chip").click();
  await page.locator("#btnCheck").click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: "shots/panel_impl_full.png", fullPage: true });
  await browser.close();
  console.log("saved shots/panel_impl_full.png");
})();
