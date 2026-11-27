#!/usr/bin/env node
// Run with an installation of Playwright and Chromium. Generating and viewing reports do not require either.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

function options(args) {
  const [report, ...rest] = args;
  const output = rest[0] && !rest[0].startsWith('--') ? rest.shift() : undefined;
  if (!report || (rest.length && (rest.length !== 2 || rest[0] !== '--baseline'))) {
    throw new Error('用法：node check_slides.cjs report.html [截图目录] [--baseline 基准截图目录]');
  }
  const baseline = rest.length ? fs.realpathSync(rest[1]) : null;
  const folder = output ? path.resolve(output) : fs.mkdtempSync(path.join(os.tmpdir(), 'bxf-check-'));
  fs.mkdirSync(folder, { recursive: true });
  assert.notEqual(fs.realpathSync(folder), baseline, '输出和基准截图须位于不同目录');
  return { report: fs.realpathSync(report), folder, baseline };
}

function tracking(context) {
  const errors = [];
  const external = [];
  context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
  context.on('request', request => { if (/^https?:/.test(request.url())) external.push(request.url()); });
  return { errors, external };
}

async function documentIndex(page) {
  return page.evaluate(() => {
    const pages = Array.from(document.querySelectorAll('main.reveal > .slides > section.slide'));
    const names = Array.from(document.querySelectorAll('[id]'), node => node.id);
    const anchors = Array.from(document.querySelectorAll('.slides a[href^="#"]'), a => a.hash.slice(1));
    const finance = pages.find(p => p.id.startsWith('finance-') || p.dataset.chapter === 'finance' || p.classList.contains('finance'));
    return {
      ids: pages.map(p => p.id), duplicateIds: names.filter((id, i) => names.indexOf(id) !== i),
      badLinks: anchors.filter(id => !document.getElementById(id)),
      untitled: pages.filter(p => !p.querySelector('h1,h2')?.textContent.trim()).map(p => p.id),
      finance: finance?.id, theme: document.documentElement.dataset.theme
    };
  });
}

async function active(page, id) {
  await page.waitForFunction(id => document.querySelector('.slides > section.present')?.id === id, id);
}

async function jump(page, id) {
  await page.evaluate(id => { location.hash = id; }, id);
  await active(page, id);
}

async function navigation(page, ids) {
  const [first, second] = ids;
  const last = ids[ids.length - 1];
  const steps = [['ArrowRight', second], ['ArrowLeft', first], ['ArrowDown', second], ['ArrowUp', first],
                 ['PageDown', second], ['PageUp', first], ['End', last], ['Home', first]];
  for (const [key, target] of steps) {
    await page.keyboard.press(key);
    await active(page, target);
  }
  await page.locator('#next').click();
  await active(page, second);
  await page.locator('#previous').click();
  await active(page, first);
  const link = page.locator('.slides > .present a[href^="#evidence-"]').first();
  if (await link.count()) {
    const href = await link.getAttribute('href');
    await link.click();
    await active(page, href.slice(1));
    assert.equal(new URL(page.url()).hash, href);
    await page.goBack();
    await active(page, first);
  }
}

async function canvasControls(page) {
  await jump(page, 'canvas');
  assert.equal(await page.locator('#canvas .cell[data-cell]').count(), 9, '商业画布须有九格');
  const value = page.locator('#canvas [data-cell="value"] .cell-trigger');
  await value.focus();
  await page.keyboard.press('Enter');
  assert.equal(await value.getAttribute('aria-pressed'), 'true');
  assert(await page.locator('#canvas .is-related').count(), '未高亮关联画布模块');
  await page.keyboard.press('Escape');
  assert.equal(await value.getAttribute('aria-pressed'), 'false');
  if (await page.evaluate(() => document.fullscreenEnabled)) {
    await page.keyboard.press('f');
    await page.waitForFunction(() => document.fullscreenElement);
    await page.keyboard.press('f');
    await page.waitForFunction(() => !document.fullscreenElement);
  }
}

// Read actual layout boxes after applying the theme. Mobile can scroll within a slide and wide tables.
function inspectSlide({ desktop, headingTop }) {
  const problems = [];
  const slide = document.querySelector('.slides > section.present');
  const epsilon = 3;
  const beyond = (a, b) => a - b > epsilon;
  const visible = node => node.getClientRects().length > 0;
  const width = window.innerWidth;
  const height = window.innerHeight;
  const viewport = slide.getBoundingClientRect();
  const heading = slide.querySelector('.page-heading').getBoundingClientRect();
  if (Math.abs(heading.top - viewport.top - headingTop) > 1) problems.push('标题区域的顶部间距与首页不一致');
  if (beyond(Math.abs(viewport.width - width), 0)) problems.push('幻灯片未铺满视口宽度');
  if (desktop && beyond(slide.scrollHeight, slide.clientHeight)) problems.push(`正文超高 ${slide.scrollHeight - slide.clientHeight}px`);
  for (const node of slide.querySelectorAll('h1,h2,h3,p,th,td,figcaption,.cell,.page-body,.page-heading,.table-wrap,.footer')) {
    if (!visible(node)) continue;
    const tag = node.className || node.tagName;
    const bounds = node.getBoundingClientRect();
    const table = node.closest('.table-wrap');
    const scrollableTable = !desktop && table && /auto|scroll/.test(getComputedStyle(table).overflowX);
    if (!scrollableTable && (bounds.left < -epsilon || beyond(bounds.right, width))) problems.push(`${tag} 超出页宽`);
    if (desktop && (bounds.top < -epsilon || beyond(bounds.bottom, height))) problems.push(`${tag} 超出页高`);
    if (desktop && !['TH','TD'].includes(node.tagName) && node.clientWidth && beyond(node.scrollWidth,node.clientWidth)) problems.push(`${tag} 横向内容溢出`);
    if (node.clientHeight && beyond(node.scrollHeight,node.clientHeight) && /hidden|clip/.test(getComputedStyle(node).overflowY)) problems.push(`${tag} 纵向内容被裁切`);
  }
  return [...new Set(problems)];
}

async function verifyLayout(page, index, width, height) {
  await page.setViewportSize({ width, height });
  await jump(page, index.ids[0]);
  const headingTop = await page.locator('.slides > section.present').evaluate(slide =>
    slide.querySelector('.page-heading').getBoundingClientRect().top - slide.getBoundingClientRect().top);
  const errors = [];
  for (const [i, id] of index.ids.entries()) {
    await jump(page, id);
    const number = `${String(i + 1).padStart(2,'0')} / ${String(index.ids.length).padStart(2,'0')}`;
    assert.equal((await page.locator('#position').textContent()).trim(), number, `${id} 页码错误`);
    const problems = await page.evaluate(inspectSlide, { desktop: width >= 1200, headingTop });
    if (problems.length) errors.push(`${width}×${height} #${id}：${problems.join('，')}`);
  }
  return errors;
}

async function checkPlainDocument(browser, url, expected) {
  const context = await browser.newContext({ offline: true, javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto(url);
    const visible = await page.locator('.slides > section.slide').evaluateAll(slides => slides.filter(s => s.getBoundingClientRect().height > 0).length);
    assert.equal(visible, expected, '禁用 JavaScript 后存在不可读的幻灯片');
  } finally { await context.close(); }
}

async function snapshots(context, url, folder, baseline, index) {
  // Start from the baseline viewport. Reusing the mobile layout check can capture stale
  // compositor tiles immediately after resizing, even when the DOM bounds are correct.
  const page = await context.newPage();
  await page.goto(url);
  await page.waitForSelector('html.enhanced', { state: 'attached' });
  const targets = { cover: index.ids[0], canvas: 'canvas' };
  if (index.finance) targets.finance = index.finance;
  for (const [name, id] of Object.entries(targets)) {
    await jump(page, id);
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const file = name + '.png';
    const rendered = await page.screenshot({ path: path.join(folder, file), animations: 'disabled', caret: 'hide' });
    if (baseline) assert(rendered.equals(fs.readFileSync(path.join(baseline,file))), `${file} 与基准图不同`);
  }
  await page.close();
  if (baseline && !index.finance) assert(!fs.existsSync(path.join(baseline,'finance.png')), '基准含财务页，本次缺少对应页');
}

async function check(browser, cfg) {
  const url = pathToFileURL(cfg.report).href;
  const context = await browser.newContext({ offline: true, viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const { errors, external } = tracking(context);
  try {
    const page = await context.newPage();
    page.setDefaultTimeout(6500);
    await page.goto(url);
    await page.waitForSelector('html.enhanced', { state: 'attached' });
    await page.evaluate(() => document.fonts.ready);
    const index = await documentIndex(page);
    assert(index.ids.length >= 2 && index.ids.includes('canvas'), '缺少封面或单页商业画布');
    assert.deepEqual(index.duplicateIds, [], '存在重复锚点');
    assert.deepEqual(index.badLinks, [], '存在失效的页内引用');
    assert.deepEqual(index.untitled, [], '存在未命名的页面');
    await navigation(page, index.ids);
    await canvasControls(page);
    const layout = [];
    for (const [width,height] of [[1440,900],[1280,720],[390,844]]) {
      layout.push(...await verifyLayout(page, index, width, height));
    }
    await snapshots(context, url, cfg.folder, cfg.baseline, index);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.emulateMedia({ media: 'print' });
    const pdf = await page.pdf({ path: path.join(cfg.folder,'report.pdf'), printBackground: true, preferCSSPageSize: true });
    const printedPages = (pdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length;
    assert.equal(printedPages, index.ids.length, '打印分页数与幻灯片数不同');
    await checkPlainDocument(browser, url, index.ids.length);
    assert.deepEqual(errors, [], '浏览器脚本错误');
    assert.deepEqual(external, [], '离线展示请求了外部资源');
    assert(!layout.length, layout.join('\n'));
    console.log(`${index.theme}：${index.ids.length} 页通过。截图与打印核对件已保存到 ${cfg.folder}`);
  } finally { await context.close(); }
}

async function main() {
  const cfg = options(process.argv.slice(2));
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, headless: true });
  try { await check(browser, cfg); } finally { await browser.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
