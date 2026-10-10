// Headless smoke test of editor.html: loads it, drives a few interactions and saves screenshots.
//
//   PW_CHANNEL=chrome node test.mjs     (needs npm install in tools/preview)
import { chromium } from '../preview/node_modules/playwright/index.mjs';   // uses the preview tool's install
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(HERE, '../preview/out');
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL });
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('console', m => m.type() === 'error' && errors.push(m.text()));
await page.goto('file://' + path.join(HERE, 'editor.html'));
await page.evaluate(() => localStorage.clear());
await page.reload();
await page.waitForTimeout(500);
await page.screenshot({ path: path.join(OUT, 'editor-1.png') });

const box = await page.locator('#plan').boundingBox();
const toScreen = async (x, z) => page.evaluate(([x, z]) => {
  const s = document.getElementById('plan'), p = s.createSVGPoint(); p.x = x; p.y = z;
  const q = p.matrixTransform(s.getScreenCTM()); return [q.x, q.y];
}, [x, z]);

// select the lawn and show its vertices
await page.evaluate(() => { const id = EDITOR.layout.items.find(i => i.role === 'lawn').id; EDITOR.select([id]); });
await page.waitForTimeout(200);
await page.screenshot({ path: path.join(OUT, 'editor-2-lawn.png') });

// drag one plant 2 m east
const plant = await page.evaluate(() => EDITOR.layout.items.find(i => i.type === 'plant' && i.layer === 'plants-new'));
let [sx, sy] = await toScreen(plant.x, plant.z);
const [tx, ty] = await toScreen(plant.x + 2, plant.z);
await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(tx, ty, { steps: 8 }); await page.mouse.up();
const moved = await page.evaluate(id => EDITOR.layout.items.find(i => i.id === id), plant.id);

// draw a bed with the polygon tool
await page.keyboard.press('Escape'); await page.keyboard.press('p');
for (const [x, z] of [[18, 20], [20, 20], [20, 22]]) { const [a, b] = await toScreen(x, z); await page.mouse.click(a, b); }
await page.keyboard.press('Enter');
const beds = await page.evaluate(() => EDITOR.layout.items.filter(i => i.role === 'bed').length);

// a dimension and an undo
await page.keyboard.press('d');
for (const [x, z] of [[0, 8.65], [14.9, 8.65]]) { const [a, b] = await toScreen(x, z); await page.mouse.click(a, b); }
const dims = await page.evaluate(() => EDITOR.layout.items.filter(i => i.type === 'dim').length);
await page.keyboard.press('Meta+z');
const dimsAfterUndo = await page.evaluate(() => EDITOR.layout.items.filter(i => i.type === 'dim').length);
await page.keyboard.press('v');
await page.screenshot({ path: path.join(OUT, 'editor-3-edits.png') });

console.log({ moved: [plant.x, moved.x], beds, dims, dimsAfterUndo });
console.log(errors.length ? 'Errors:\n' + errors.join('\n') : 'No errors.');
await browser.close();
