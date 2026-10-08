// Exports the model for Blender (tools/blender): the scene as glTF and the generated data as JSON.
// Trees, bed planting and the grid are left out of the glTF; Blender builds them from the JSON.
//
//   node export.mjs ../../index.html ../blender/data
//   PW_CHANNEL=chrome node export.mjs …   uses the installed Chrome when Playwright's bundled Chromium won't start
//
// Writes scene.glb (Y-up, metres; Blender's importer turns it to Z-up with north = +Y) and scene.json.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const [, , file = '../../index.html', outDir = '../blender/data'] = process.argv;
fs.mkdirSync(outDir, { recursive: true });
const three = fs.readFileSync('node_modules/three/build/three.min.js');
const orbit = fs.readFileSync('node_modules/three/examples/js/controls/OrbitControls.js');
const exporter = fs.readFileSync('node_modules/three/examples/js/exporters/GLTFExporter.js', 'utf8');

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL, args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage();
page.on('pageerror', e => console.error(String(e)));
await page.route('**/three.min.js', r => r.fulfill({ body: three, contentType: 'application/javascript' }));
await page.route('**/OrbitControls.js', r => r.fulfill({ body: orbit, contentType: 'application/javascript' }));
await page.route('**/fonts.googleapis.com/**', r => r.abort());

let html = fs.readFileSync(file, 'utf8');
if (!/^\s*<!doctype/i.test(html)) html = '<!doctype html><meta charset="utf-8">' + html;
await page.setContent(html, { waitUntil: 'load' });
await page.waitForFunction(() => window.GARDEN);
await page.addScriptTag({ content: exporter });

const { glb, data } = await page.evaluate(() => new Promise(resolve => {
  const { scene, G } = window.GARDEN;
  scene.traverse(o => { if (o.isInstancedMesh) o.visible = false; });
  G.trees.visible = false; G.grid.visible = false;
  Object.values(G).forEach(g => { if (g !== G.trees && g !== G.grid) g.visible = true; });
  const data = { PLANTS, TREES, VIEWS, H, P, LAWN, DRIVE, RAMP, PATIO, DECK, DECK_EDGE, POOL, HOUSE, GARAGE, PLANTERS };
  new THREE.GLTFExporter().parse(scene, buf => {
    const bytes = new Uint8Array(buf); let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    resolve({ glb: btoa(s), data });
  }, { binary: true, onlyVisible: true });
}));
fs.writeFileSync(path.join(outDir, 'scene.glb'), Buffer.from(glb, 'base64'));
fs.writeFileSync(path.join(outDir, 'scene.json'), JSON.stringify(data));
console.log(`scene.glb ${(Buffer.from(glb, 'base64').length / 1e6).toFixed(1)} MB, ${data.PLANTS.length} plants, ${data.TREES.length} trees`);
await browser.close();
