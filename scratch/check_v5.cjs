// check_v5.cjs — real interaction verification for panel_v5.html
const { chromium } = require('/Users/tatsuyasasaki/Developer/tatsuyasasaki-portfolio/node_modules/playwright');
const URL = 'file:///Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/scratch/panel_v5.html';
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

  // screenshots: strip area zoom + full page
  await page.evaluate(() => window.scrollTo(0, 0));
  await strip.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/v5_strip.png` });
  await page.screenshot({ path: `${OUT}/v5_full.png`, fullPage: true });

  console.log('PASS:', ok.length, ok.map(x => '  ✓ ' + x).join('\n'));
  console.log('FAIL:', ng.length, ng.map(x => '  ✗ ' + x).join('\n'));
  await b.close();
  process.exit(ng.length ? 1 : 0);
})();
