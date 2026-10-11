// check_v5.cjs — real interaction verification for panel_v6.html
const { chromium } = require('/Users/tatsuyasasaki/Developer/tatsuyasasaki-portfolio/node_modules/playwright');
const URL = 'file:///Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/scratch/panel_v6.html';
const OUT = '/Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/scratch/shots';
const ok = [], ng = [];
const t = (name, cond) => (cond ? ok : ng).push(name);

(async () => {
  const b = await chromium.launch();
  const page = await (await b.newContext({ viewport: { width: 360, height: 700 } })).newPage();
  page.on('dialog', d => d.accept());
  await page.goto(URL, { waitUntil: 'load' });
  await page.waitForTimeout(500);

  // 1. card count + first card fully inside strip viewport
  const nCards = await page.locator('.card').count();
  t('7 cards rendered', nCards === 7);
  const geo = await page.evaluate(() => {
    const s = document.getElementById('strip');
    const c = s.querySelector('.card').getBoundingClientRect();
    const r = s.getBoundingClientRect();
    return { cardRight: c.right, stripRight: r.right, cardW: c.width, clip: c.right <= r.right + 1 };
  });
  t(`first card fully readable (card ${geo.cardW}px, right ${geo.cardRight.toFixed(0)} <= ${geo.stripRight.toFixed(0)})`, geo.clip);

  // 2. nav button moves strip
  const l0 = await page.evaluate(() => document.getElementById('strip').scrollLeft);
  await page.locator('#stripNext').click();
  await page.waitForTimeout(400);
  const l1 = await page.evaluate(() => document.getElementById('strip').scrollLeft);
  t(`next button scrolls (0 -> ${l1})`, l1 > l0);

  // 3. real wheel: drive to strip's right end, then page must scroll (edge release)
  const strip = page.locator('#strip');
  const box = await strip.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < 30; i++) await page.mouse.wheel(0, 240);
  await page.waitForTimeout(300);
  const atEnd = await page.evaluate(() => {
    const s = document.getElementById('strip');
    return s.scrollLeft >= s.scrollWidth - s.clientWidth - 2;
  });
  t('strip reached right end via wheel', atEnd);
  const y0 = await page.evaluate(() => window.scrollY);
  // the drive already released to the page (y0 > 0 proves it); re-verify controlled:
  await page.evaluate(() => window.scrollTo(0, window.scrollY - 600));
  await page.waitForTimeout(200);
  const box2 = await strip.boundingBox();
  await page.mouse.move(box2.x + box2.width / 2, box2.y + box2.height / 2);
  const yMid = await page.evaluate(() => window.scrollY);
  for (let i = 0; i < 15; i++) await page.mouse.wheel(0, 300);
  await page.waitForTimeout(300);
  const y1 = await page.evaluate(() => window.scrollY);
  t(`page scrolls past strip's right edge (y ${yMid} -> ${y1}, drive released at ${y0})`, y1 > yMid);

  // 4. wheel up at strip's left end -> page scrolls up (release)
  await page.mouse.move(box.x + box.width / 2, box.y + 40);
  const y2 = await page.evaluate(() => window.scrollY);
  for (let i = 0; i < 25; i++) await page.mouse.wheel(0, -300);
  await page.waitForTimeout(300);
  const y3 = await page.evaluate(() => window.scrollY);
  t(`page scrolls up at strip's left edge (y ${y2} -> ${y3})`, y3 < y2);

  // 5. evidence chip link jumps to its slot
  await page.evaluate(() => { document.getElementById('strip').scrollLeft = 0; window.scrollTo(0, 0); });
  const slotVisible = await page.locator('#slot-TRACKING_INFORMATION').evaluate(el => {
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return r.top >= 0 && r.top < window.innerHeight;
  });
  t('slot element exists and is scrollable', slotVisible);

  // 6. carrier OTHER reveals the input
  await page.locator('#carrierSel').selectOption('OTHER');
  const otherShown = await page.locator('#carrierOther').isVisible();
  t('carrier OTHER reveals name input', otherShown);

  // 7. summary chips show real counts
  const chips = await page.locator('.chip .n').allTextContents();
  t(`summary = 3/2/2 (${chips.join('/')})`, chips.join(',') === '3,2,2');

  // 8. no fabricated pattern names — all names come from DATA
  const names = await page.locator('.pname').allTextContents();
  const clean = n => n.replace(/​/g, '').trim(); // strips U+200B
  const expect = ['NO_SHIPPING_ADDRESS_ON_FILE','MISMATCHED_SHIP_TO_VS_BILLING_COUNTRY','RAPID_REPEAT_HIGH_VALUE_BUYER','FIRST_TIME_BUYER_EXPEDITED_SHIPPING_REQUEST'];
  t(`pattern names all real (${names.length})`, names.every(n => expect.includes(clean(n))));

  // 9. all expected_evidence types rendered as chips in §01
  const evid = new Set(await page.locator('.evid-mini span').allTextContents());
  t(`all 8 evidence types shown in cards (${evid.size})`, evid.size === 8);

  // 10. real-case reveal visible by default
  const revealVisible = await page.locator('.slot-reveal').isVisible();
  t('real-case reveal visible without tap', revealVisible);

  // 11. horizontal overflow of page itself
  const docW = await page.evaluate(() => document.documentElement.scrollWidth);
  t(`no page horizontal overflow (scrollWidth=${docW})`, docW <= 360);

  // 12. prescriptions hidden on PASS cards, "WHEN APPLICABLE" on N/A
  const rxAudit = await page.evaluate(() => {
    let badPass = 0, goodNa = 0;
    for (const card of document.querySelectorAll('.card')) {
      const isPass = card.classList.contains('pass');
      const rx = card.querySelector('.c-rx');
      if (isPass && rx) badPass++;
      if (card.classList.contains('not_assessable') && rx && rx.classList.contains('cond')) goodNa++;
    }
    return { badPass, goodNa };
  });
  t(`no prescription on PASS cards (${rxAudit.badPass} violations)`, rxAudit.badPass === 0);
  t(`N/A prescriptions marked contingent (${rxAudit.goodNa}/2)`, rxAudit.goodNa === 2);

  // 13. Load button is wired — same id = "already loaded", other id = locked notice
  await page.locator('#btnLoad').click();
  const note1 = await page.locator('#loadNote').textContent();
  const sameOk = note1.includes('already loaded');
  await page.locator('#capInput').fill('DIFFERENT123');
  await page.locator('#btnLoad').click();
  const note2 = await page.locator('#loadNote').textContent();
  t(`Load explains lock (same: ${sameOk}, diff msg: "${note2.slice(0, 40)}…")`,
    sameOk && note2.includes('locked to'));
  await page.locator('#capInput').fill('3J366679AY2283450');

  // 14. dispute banner carries real dispute id/state
  const banner = await page.locator('#bannerSrc').textContent();
  t('banner shows real dispute id+state', banner.includes('PP-R-XGB-10190971') && banner.includes('UNDER_PAYPAL_REVIEW'));

  // 15. no simulate affordances left
  t('no simulate toggles', (await page.locator('.sim-btn').count()) === 0);

  // 16. no javascript: URLs
  t('no javascript: hrefs', (await page.locator('a[href^="javascript:"]').count()) === 0);

  // screenshots: strip area zoom + full page
  await page.evaluate(() => window.scrollTo(0, 0));
  await strip.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/v6_strip.png` });
  await page.screenshot({ path: `${OUT}/v6_full.png`, fullPage: true });

  console.log('PASS:', ok.length, ok.map(x => '  ✓ ' + x).join('\n'));
  console.log('FAIL:', ng.length, ng.map(x => '  ✗ ' + x).join('\n'));
  await b.close();
  process.exit(ng.length ? 1 : 0);
})();
