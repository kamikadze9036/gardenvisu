// Draws a 2D plan of the garden as it is modelled (A3, 1 : 150), in the spirit of the hand-drawn planting plan:
// every plant as a circle with a number or letter and a legend. Reads the data exported by export.mjs.
//
//   PW_CHANNEL=chrome node plan.mjs ../blender/data/scene.json out
//
// Writes out/plan-stavajici-stav.pdf, .png and .svg.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const [, , dataFile = '../blender/data/scene.json', outDir = 'out'] = process.argv;
const D = JSON.parse(fs.readFileSync(dataFile, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });

// Page in millimetres; plan coordinates are metres, x east, z south, so north is up without any flip.
const W = 420, Hp = 297, S = 1000 / 150;           // 1 : 150 → 6,667 mm per metre
const X0 = 18, Y0 = 37, MINX = -5.66, MINZ = -4.7;
const X = x => X0 + (x - MINX) * S, Y = z => Y0 + (z - MINZ) * S;
const f = n => n.toFixed(2);
const pts = poly => poly.map(([x, z]) => `${f(X(x))},${f(Y(z))}`).join(' ');
const out = [];
const poly = (p, cls, extra = '') => out.push(`<polygon points="${pts(p)}" class="${cls}" ${extra}/>`);
const rect = (x0, z0, x1, z1, cls, extra = '') => out.push(`<rect x="${f(X(x0))}" y="${f(Y(z0))}" width="${f((x1 - x0) * S)}" height="${f((z1 - z0) * S)}" class="${cls}" ${extra}/>`);
const text = (x, z, s, cls = 'lbl', extra = '') => out.push(`<text x="${f(X(x))}" y="${f(Y(z))}" class="${cls}" ${extra}>${s}</text>`);

// ---- what the generated plants are in the Blender scene (same lists as PROTOS in build_scene.py)
const SHRUB = {
  laurel: ['A', 'bobkovišeň', '#2c5225'], hakuro: ['B', "vrba 'Hakuro Nishiki'", '#b9c7a6'],
  spiraea_orange: ['C', 'tavolník (oranžový)', '#d08a2c'], spiraea_yellow: ['D', 'tavolník (žlutý)', '#b7a33a'],
  rose: ['E', 'růže', '#c86d8a'], green: ['F', 'listnatý keř', '#4f7a3a'], cotinus: ['G', 'ruj vlasatá', '#5b2d3d'],
  amelanchier: ['H', 'muchovník', '#b5402f'], euonymus: ['I', 'brslen křídlatý', '#c0262c'],
  aster: ['J', 'hvězdnice', '#8a5cc0'], grass: ['K', 'okrasná tráva', '#c8ad72'], rock: ['L', 'kámen', '#a39e94'],
};
const VARIANTS = {
  green: ['green', 'laurel', 'hakuro', 'green', 'rose', 'spiraea_orange', 'green', 'spiraea_yellow', 'laurel', 'rose'],
  burg: ['cotinus', 'amelanchier', 'euonymus', 'euonymus'], purple: ['aster'], grass: ['grass'], rock: ['rock'],
};
const shrubOf = p => { const v = VARIANTS[p.type]; return SHRUB[v[Math.floor(p.c * v.length) % v.length]]; };

// ---- ground
poly(D.P, 'bed');
poly(D.LAWN, 'lawn');
[...D.DESIGN_BEDS].forEach(b => poly(b, 'bed'));
[D.DRIVE, D.RAMP].forEach(p => poly(p, 'pave'));
poly(D.PATIO, 'stone');
poly(D.DECK_EDGE, 'deck'); poly(D.DECK, 'deck');
poly(D.POOL, 'pool');
D.GRAVEL.forEach(g => poly(g, 'gravel'));
D.DESIGN_BEDS.forEach(b => poly(b, 'design'));
out.push(`<circle cx="${f(X(D.FIRE.x))}" cy="${f(Y(D.FIRE.z))}" r="${f(D.FIRE.r * S)}" class="gravel"/>`);
D.SLABS.forEach(s => out.push(`<rect x="${f(-D.PATH.along / 2 * S)}" y="${f(-D.PATH.across / 2 * S)}" width="${f(D.PATH.along * S)}" height="${f(D.PATH.across * S)}" class="slab" transform="translate(${f(X(s.x))},${f(Y(s.z))}) rotate(${f(s.ang * 180 / Math.PI)})"/>`));
D.PLANTERS.forEach(([a, b]) => rect(a, -3.8, b, -2.4, 'planter'));

// ---- buildings and structures
poly(D.HOUSE, 'house'); poly(D.GARAGE, 'house');
text(7.45, 4.6, 'RODINNÝ DŮM', 'big'); text(7.45, 5.6, '14,90 × 8,65 m', 'small');
text(18.95, 8.4, 'GARÁŽ', 'big'); text(18.95, 9.4, '8,10 × 8,50 m', 'small');
rect(0, 8.65, 7.95, 11.25, 'pergola'); text(3.97, 10.2, 'pergola', 'small');
const [px0, pz0] = D.POOL[0], [px1, pz1] = D.POOL[2];
rect(px0 - 0.15, pz0 - 0.2, px1 + 0.15, pz1 + 0.2, 'cover'); text((px0 + px1) / 2, (pz0 + pz1) / 2 + 0.35, 'bazén se zastřešením', 'small');
for (const fu of D.FURNITURE) {
  if (fu.w) { rect(fu.x - fu.w / 2, fu.z - fu.d / 2, fu.x + fu.w / 2, fu.z + fu.d / 2, 'struct'); text(fu.x, fu.z + 0.15, fu.type === 'playhouse' ? 'domek' : 'dřevník', 'tiny'); }
  else if (fu.type === 'firebowl') { out.push(`<circle cx="${f(X(fu.x))}" cy="${f(Y(fu.z))}" r="${f(fu.r * S)}" class="fire"/>`); text(fu.x, fu.z + 0.95, 'ohniště', 'tiny'); }
  else if (fu.type === 'boulder') out.push(`<circle cx="${f(X(fu.x))}" cy="${f(Y(fu.z))}" r="${f(fu.r * S)}" class="stone-dot"/>`);
}
text(17.25, 2.75, 'posezení', 'tiny');
text(16.6, -2.95, 'vyvýšené záhony', 'tiny');

// ---- plants: existing (letters), plan species (numbers), trees (crowns)
const used = new Set();
for (const p of D.PLANTS) {
  const [k, , col] = shrubOf(p); used.add(k);
  const r = p.r * 0.9;
  out.push(`<circle cx="${f(X(p.x))}" cy="${f(Y(p.z))}" r="${f(r * S)}" fill="${col}" class="plant"/>`);
  if (r * S > 1.1) out.push(`<text x="${f(X(p.x))}" y="${f(Y(p.z) + r * S * 0.35)}" class="pl" style="font-size:${f(Math.min(r * S, 2.4))}px">${k}</text>`);
}
for (const p of D.DESIGN_PLANTS) {
  const s = D.SPECIES[p.sp]; const r = s.d / 2;
  out.push(`<circle cx="${f(X(p.x))}" cy="${f(Y(p.z))}" r="${f(r * S)}" fill="${s.flower || s.leaf}" class="plant${p.existing ? '' : ' new'}"/>`);
  out.push(`<text x="${f(X(p.x))}" y="${f(Y(p.z) + r * S * 0.38)}" class="pl" style="font-size:${f(Math.min(r * S * 1.05, 2.2))}px">${p.sp}</text>`);
}
D.TREES.forEach((t, i) => {
  out.push(`<circle cx="${f(X(t.x))}" cy="${f(Y(t.z))}" r="${f(t.r * S)}" fill="${t.c}" class="tree"/>`);
  out.push(`<circle cx="${f(X(t.x))}" cy="${f(Y(t.z))}" r="0.7" class="trunk"/>`);
  out.push(`<text x="${f(X(t.x) + 1.4)}" y="${f(Y(t.z) - 1.2)}" class="tl">S${i + 1}</text>`);
});

// ---- boundary, fences, surroundings
out.push(`<polygon points="${pts(D.P)}" class="plot"/>`);
text(16, 32.6, 'ULICE', 'side'); text(30.0, 14, 'ULICE', 'side', `transform="rotate(90 ${f(X(30.0))} ${f(Y(14))})"`);
text(14, -5.3, 'sousední parcela (pole)', 'side2'); text(-7.3, 11, 'soused', 'side2', `transform="rotate(-90 ${f(X(-7.3))} ${f(Y(11))})"`);

// ---- dimensions
function dim(x0, z0, x1, z1, label, off = 0) {   // dimension line with ticks, label in the middle
  const a = [X(x0), Y(z0)], b = [X(x1), Y(z1)], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len, nx = -uy * off, ny = ux * off;
  const A = [a[0] + nx, a[1] + ny], B = [b[0] + nx, b[1] + ny];
  out.push(`<line x1="${f(A[0])}" y1="${f(A[1])}" x2="${f(B[0])}" y2="${f(B[1])}" class="dim"/>`);
  for (const P of [A, B]) out.push(`<line x1="${f(P[0] - 1.1 * (ux - uy) / 1.414)}" y1="${f(P[1] - 1.1 * (uy + ux) / 1.414)}" x2="${f(P[0] + 1.1 * (ux - uy) / 1.414)}" y2="${f(P[1] + 1.1 * (uy + ux) / 1.414)}" class="dim"/>`);
  const ang = Math.atan2(uy, ux) * 180 / Math.PI, mx = (A[0] + B[0]) / 2 + nx * 0.5, my = (A[1] + B[1]) / 2 + ny * 0.5;
  out.push(`<text x="${f(mx)}" y="${f(my - 0.8)}" class="dimt" transform="rotate(${f(ang > 90 || ang < -90 ? ang + 180 : ang)} ${f(mx)} ${f(my - 0.8)})">${label}</text>`);
}
dim(D.P[0][0], D.P[0][1], D.P[1][0], D.P[1][1], '28,65 m', -3.2);
dim(0, -4.7, 0, 0, '4,71 m', 4);
dim(0, 0, 14.9, 0, '14,90', 3.5);
dim(-5.66, 24.48, -5.66, -4.7, '29,18 m', -5);

// ---- legend
const LX = 262; let ly = 34;
const leg = [];
const L = (s, cls = 'leg', dy = 4.6) => { leg.push(`<text x="${LX}" y="${f(ly)}" class="${cls}">${s}</text>`); ly += dy; };
const swatch = (col, label, txt, cls = 'plant') => {
  leg.push(`<circle cx="${LX + 2.4}" cy="${f(ly - 1.3)}" r="2.3" fill="${col}" class="${cls}"/><text x="${LX + 2.4}" y="${f(ly - 0.45)}" class="pl" style="font-size:2.3px">${label}</text>`);
  leg.push(`<text x="${LX + 7}" y="${f(ly)}" class="leg">${txt}</text>`); ly += 5.4;
};
L('Trvalky – osazovací plán (č. 1–10), stávající na dvorku (11–13)', 'legh', 6);
Object.entries(D.SPECIES).forEach(([i, s]) => swatch(s.flower || s.leaf, i, `${s.cz} <tspan class="lat">${s.lat}</tspan>`));
ly += 2; L('Stávající keře a rostliny (orientačně podle fotek)', 'legh', 6);
Object.values(SHRUB).filter(([k]) => used.has(k)).forEach(([k, n, c]) => swatch(c, k, n));
ly += 2; L('Stromy', 'legh', 6);
const colW = 74; let col = 0, ty = ly;
D.TREES.forEach((t, i) => {
  leg.push(`<text x="${LX + col * colW}" y="${f(ty)}" class="leg"><tspan class="tlb">S${i + 1}</tspan>  ${t.name || t.kind}</text>`);
  ty += 4.6; if (i === Math.ceil(D.TREES.length / 2) - 1) { col = 1; ty = ly; }
});
ly += Math.ceil(D.TREES.length / 2) * 4.6 + 3;
L('Plochy', 'legh', 6);
const area = (cls, txt) => { leg.push(`<rect x="${LX}" y="${f(ly - 3.6)}" width="5" height="4" class="${cls}"/><text x="${LX + 7}" y="${f(ly)}" class="leg">${txt}</text>`); ly += 5.4; };
area('lawn', 'trávník'); area('bed', 'záhon, mulč'); area('design', 'nově osázená plocha (dřív trávník)');
area('gravel', 'kačírek, oblázky'); area('pave', 'dlažba příjezdu'); area('deck', 'terasa WPC'); area('slab', 'nášlapné desky 1,0 × 0,4 m');

// ---- title block, north arrow, scale bar
const sbx = X0, sby = 283;
const bar = [0, 1, 2, 3, 4, 5, 10].map(m => `<line x1="${f(sbx + m * S)}" y1="${sby - 1.5}" x2="${f(sbx + m * S)}" y2="${sby + 1.5}" class="dim"/><text x="${f(sbx + m * S)}" y="${sby + 5}" class="dimt">${m}</text>`).join('');
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}mm" height="${Hp}mm" viewBox="0 0 ${W} ${Hp}">
<defs>
  <pattern id="hatch" width="2.2" height="2.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="2.2" stroke="#8d8a83" stroke-width="0.35"/></pattern>
  <pattern id="dots" width="1.6" height="1.6" patternUnits="userSpaceOnUse"><rect width="1.6" height="1.6" fill="#ecebe6"/><circle cx="0.8" cy="0.8" r="0.32" fill="#b4b1a8"/></pattern>
  <pattern id="boards" width="1.2" height="10" patternUnits="userSpaceOnUse"><rect width="1.2" height="10" fill="#c99486"/><line x1="0" y1="0" x2="0" y2="10" stroke="#a5746a" stroke-width="0.2"/></pattern>
  <pattern id="pavers" width="3" height="2" patternUnits="userSpaceOnUse"><rect width="3" height="2" fill="#dad5ca"/><path d="M0 0H3M0 1H3M1.5 0V1M0 1V2" stroke="#bdb6a8" stroke-width="0.18"/></pattern>
</defs>
<style>
  text{font-family:Helvetica,Arial,sans-serif;fill:#22281f}
  .plot{fill:none;stroke:#22281f;stroke-width:0.7}
  .lawn{fill:#d5e8c0;stroke:#8fb26c;stroke-width:0.25}
  .bed{fill:#e9dccb;stroke:none}
  .design{fill:none;stroke:#7a5c3a;stroke-width:0.35;stroke-dasharray:1.6 1}
  .pave{fill:url(#pavers);stroke:#9d968a;stroke-width:0.25}
  .stone{fill:#e6e1d6;stroke:#9d968a;stroke-width:0.25}
  .deck{fill:url(#boards);stroke:#8a5a4e;stroke-width:0.3}
  .pool{fill:#bfe0ea;stroke:#5a9bb0;stroke-width:0.3}
  .cover{fill:none;stroke:#45494e;stroke-width:0.45}
  .gravel{fill:url(#dots);stroke:#a7a59f;stroke-width:0.25}
  .slab{fill:#cfd0cc;stroke:#8f908c;stroke-width:0.25}
  .planter{fill:#d8c7a8;stroke:#8a7552;stroke-width:0.3}
  .house{fill:url(#hatch);stroke:#22281f;stroke-width:0.6}
  .pergola{fill:none;stroke:#45494e;stroke-width:0.35;stroke-dasharray:2 1}
  .struct{fill:#e2ddd2;stroke:#5c5850;stroke-width:0.35}
  .fire{fill:#a3562a;stroke:#5a2c16;stroke-width:0.25}
  .stone-dot{fill:#c9b68e;stroke:#7d6f52;stroke-width:0.2}
  .plant{fill-opacity:0.8;stroke:#2f3b2a;stroke-width:0.18}
  .plant.new{stroke:#22281f;stroke-width:0.25}
  .tree{fill-opacity:0.18;stroke:#2f3b2a;stroke-width:0.3;stroke-dasharray:1.2 0.7}
  .trunk{fill:#5e4430}
  .pl{text-anchor:middle;font-weight:600;fill:#111}
  .tl{font-size:2.4px;font-weight:700;fill:#2f3b2a}
  .lbl{font-size:3px}
  .big{font-size:3.6px;font-weight:700;text-anchor:middle;fill:#22281f}
  .small{font-size:2.4px;text-anchor:middle;fill:#333}
  .tiny{font-size:2px;text-anchor:middle;fill:#333}
  .side{font-size:3.4px;letter-spacing:0.8px;fill:#67705f;text-anchor:middle}
  .side2{font-size:2.6px;fill:#67705f;text-anchor:middle;font-style:italic}
  .dim{stroke:#22281f;stroke-width:0.22}
  .dimt{font-size:2.4px;text-anchor:middle}
  .leg{font-size:2.8px}
  .lat{font-style:italic;fill:#67705f}
  .legh{font-size:3.2px;font-weight:700}
  .tlb{font-weight:700}
  .title{font-size:6.5px;font-weight:700}
  .sub{font-size:3px;fill:#4a5145}
</style>
<rect width="${W}" height="${Hp}" fill="#fff"/>
<text x="${X0}" y="15" class="title">Zahrada – stávající stav podle 3D modelu</text>
<text x="${X0}" y="21.5" class="sub">Stav podle fotek z října 2026 a projektové dokumentace. Záhony z osazovacího plánu jsou rozmístěné přesně podle plánu, jejich poloha a stávající keře jsou orientační.</text>
${out.join('\n')}
<g transform="translate(240 48)"><polygon points="0,-8 3,2 0,0 -3,2" fill="#22281f"/><text x="0" y="7" class="big">S</text></g>
<line x1="${sbx}" y1="${sby}" x2="${f(sbx + 10 * S)}" y2="${sby}" class="dim"/>${bar}
<text x="${f(sbx + 10 * S + 3)}" y="${sby + 1}" class="leg">m   ·   měřítko 1 : 150 (A3)</text>
${leg.join('\n')}
<text x="${LX}" y="283" class="sub">gardenvisu · tools/preview/plan.mjs · ${new Date().toLocaleDateString('cs-CZ')}</text>
</svg>`;

fs.writeFileSync(path.join(outDir, 'plan-stavajici-stav.svg'), svg);
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL });
const page = await browser.newPage({ viewport: { width: 1588, height: 1123 }, deviceScaleFactor: 2.5 });
await page.setContent(`<!doctype html><meta charset="utf-8"><style>@page{size:420mm 297mm;margin:0}body{margin:0}svg{display:block;width:420mm;height:297mm}</style>${svg}`);
await page.pdf({ path: path.join(outDir, 'plan-stavajici-stav.pdf'), width: '420mm', height: '297mm', printBackground: true });
await page.screenshot({ path: path.join(outDir, 'plan-stavajici-stav.png'), fullPage: true });
await browser.close();
console.log('plan-stavajici-stav.pdf / .png / .svg');
