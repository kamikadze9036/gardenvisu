// Renders the model headlessly and saves a screenshot of each camera view.
// Useful to check a change without opening a browser.
//
//   cd tools/preview && npm install && npx playwright install chromium
//   node preview.mjs ../../index.html out
//
// Three.js is served from node_modules instead of the CDN, so it also works offline.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const [, , file = '../../index.html', outDir = 'out'] = process.argv;
fs.mkdirSync(outDir, { recursive: true });
const three = fs.readFileSync('node_modules/three/build/three.min.js');
const orbit = fs.readFileSync('node_modules/three/examples/js/controls/OrbitControls.js');

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1100, height: 1300 } });
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('console', m => { if (m.type() === 'error' && !m.text().includes('ERR_FAILED')) errors.push(m.text()); });
await page.route('**/three.min.js', r => r.fulfill({ body: three, contentType: 'application/javascript' }));
await page.route('**/OrbitControls.js', r => r.fulfill({ body: orbit, contentType: 'application/javascript' }));
await page.route('**/fonts.googleapis.com/**', r => r.abort());

let html = fs.readFileSync(file, 'utf8');
if (!/^\s*<!doctype/i.test(html)) html = '<!doctype html><meta charset="utf-8">' + html;
await page.setContent(html, { waitUntil: 'load' });
await page.waitForTimeout(3000);
await page.screenshot({ path: path.join(outDir, 'page.png') });

const buttons = await page.$$('#views button');
for (let i = 0; i < buttons.length; i++) {
  const name = (await buttons[i].textContent()).trim().toLowerCase().replace(/\s+/g, '-');
  await buttons[i].click();
  await page.waitForTimeout(3000);
  await page.locator('#stage').screenshot({ path: path.join(outDir, `view-${i + 1}-${name}.png`) });
}
console.log(errors.length ? 'Errors:\n' + errors.join('\n') : 'No errors.');
await browser.close();
