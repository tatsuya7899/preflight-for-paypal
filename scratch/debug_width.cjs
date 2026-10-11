// debug_width.cjs — find elements extending past the 360px viewport
const { chromium } = require('/Users/tatsuyasasaki/Developer/tatsuyasasaki-portfolio/node_modules/playwright');
const URL = 'file:///Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/scratch/panel_v5.html';
(async () => {
  const b = await chromium.launch();
  const page = await (await b.newContext({ viewport: { width: 360, height: 700 } })).newPage();
  await page.goto(URL, { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const wide = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.right > 360.5 && r.width > 0) {
        const st = el.closest('section,header,footer');
        out.push({
          tag: el.tagName, cls: el.className && el.className.baseVal !== undefined ? 'svg' : String(el.className).slice(0, 40),
          right: +r.right.toFixed(1), w: +r.width.toFixed(1),
          section: st ? st.tagName + (st.id ? '#' + st.id : '') : 'body',
          inStrip: !!el.closest('#strip'),
        });
      }
    }
    return out.filter(x => !x.inStrip);
  });
  console.log(JSON.stringify(wide, null, 1));
  await b.close();
})();
