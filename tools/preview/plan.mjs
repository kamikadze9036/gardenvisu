// A3 planting plan (1 : 150) as PDF, PNG and SVG from a layout (tools/editor/layout.json or a file saved from the editor).
// The drawing itself is tools/editor/plan.js, the same code as the editor's "Půdorys PDF" button.
//
//   PW_CHANNEL=chrome node plan.mjs [layout.json] [out]
//   PW_CHANNEL=chrome node plan.mjs http://192.168.20.30:8083/api/layout out     (the latest layout from the editor)
//
// Writes out/plan.pdf, out/plan.png and out/plan.svg.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const [, , src = path.join(HERE, '../editor/layout.json'), outDir = 'out'] = process.argv;
const layout = src.startsWith('http') ? await (await fetch(src)).json() : JSON.parse(fs.readFileSync(src, 'utf8'));
vm.runInThisContext(fs.readFileSync(path.join(HERE, '../editor/plan.js'), 'utf8'));
const svg = globalThis.drawPlan(layout);
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'plan.svg'), svg);
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL });
const page = await browser.newPage({ viewport: { width: 1588, height: 1123 }, deviceScaleFactor: 2.5 });
await page.setContent(`<!doctype html><meta charset="utf-8"><style>@page{size:420mm 297mm;margin:0}body{margin:0}svg{display:block;width:420mm;height:297mm}</style>${svg}`);
await page.pdf({ path: path.join(outDir, 'plan.pdf'), width: '420mm', height: '297mm', printBackground: true });
await page.screenshot({ path: path.join(outDir, 'plan.png'), fullPage: true });
await browser.close();
console.log(`plan.pdf / .png / .svg from ${src}`);
