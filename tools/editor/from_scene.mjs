// Builds the editor's starting layout from the current model: tools/blender/data/scene.json (export.mjs) → layout.json.
// Every generated plant is "frozen" into its own item with a species from the catalogue, so it can be moved by hand.
//
//   node from_scene.mjs ../blender/data/scene.json
//
// Writes layout.json (the data) and layout.js (the same data as `window.DEFAULT_LAYOUT`, so editor.html also opens
// straight from disk without a web server).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const [, , dataFile = path.join(HERE, '../blender/data/scene.json')] = process.argv;
const D = JSON.parse(fs.readFileSync(dataFile, 'utf8'));
const r3 = v => Math.round(v * 1000) / 1000;
const P = pts => pts.map(([x, z]) => [r3(x), r3(z)]);
let n = 0; const id = () => `i${++n}`;

// ---- catalogue: plan perennials 1–13, existing shrubs A–L (as drawn in plan.mjs), trees
const catalog = {};
for (const [k, s] of Object.entries(D.SPECIES)) {
  catalog[k] = { code: k, cz: s.cz, lat: s.lat, group: 'perennial', kind: s.kind, h: s.h, d: s.d, leaf: s.leaf, flower: s.flower || null };
}
const SHRUBS = {
  A: ['bobkovišeň', 'Prunus laurocerasus', '#2c5225', 1.6], B: ["vrba 'Hakuro Nishiki'", 'Salix integra', '#b9c7a6', 1.6],
  C: ['tavolník (oranžový)', 'Spiraea', '#d08a2c', 1.0], D: ['tavolník (žlutý)', 'Spiraea', '#b7a33a', 1.0],
  E: ['růže', 'Rosa', '#4f7436', 0.9], F: ['listnatý keř', '', '#4f7a3a', 1.2], G: ['ruj vlasatá', 'Cotinus coggygria', '#5b2d3d', 1.6],
  H: ['muchovník', 'Amelanchier', '#b5402f', 1.8], I: ['brslen křídlatý', 'Euonymus alatus', '#c0262c', 1.2],
  J: ['hvězdnice', 'Aster', '#8a5cc0', 0.5], K: ['okrasná tráva', '', '#c8ad72', 0.8], L: ['kámen', '', '#a39e94', 0.6],
};
for (const [k, [cz, lat, col, d]] of Object.entries(SHRUBS)) {
  catalog[k] = { code: k, cz, lat, group: k === 'L' ? 'stone' : k === 'K' ? 'grass' : 'shrub', kind: k === 'L' ? 'rock' : k === 'K' ? 'grass' : 'shrub', h: d, d, leaf: col, flower: null };
}
const VARIANTS = {   // same lists as PROTOS in build_scene.py
  green: ['F', 'A', 'B', 'F', 'E', 'C', 'F', 'D', 'A', 'E'], burg: ['G', 'H', 'I', 'I'], purple: ['J'], grass: ['K'], rock: ['L'],
};
const slug = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
for (const t of D.TREES) {
  const k = 't-' + slug(t.name || t.kind);
  catalog[k] ??= { code: 'S', cz: t.name || t.kind, lat: '', group: 'tree', kind: t.kind, h: t.h, d: 2 * t.r, leaf: t.c, flower: null };
}

// ---- layers, bottom to top (drawing order). The plot's fill is drawn underneath everything by the editor.
const layers = [
  { id: 'underlay', name: 'Podklad', visible: true, locked: false, opacity: 0.5 },
  { id: 'beds', name: 'Trávník a záhony', visible: true, locked: false, opacity: 1 },
  { id: 'paving', name: 'Zpevněné plochy', visible: true, locked: false, opacity: 1 },
  { id: 'site', name: 'Pozemek a stavby', visible: true, locked: true, opacity: 1 },
  { id: 'plants-existing', name: 'Rostliny – stávající', visible: true, locked: false, opacity: 1 },
  { id: 'plants-new', name: 'Rostliny – návrh', visible: true, locked: false, opacity: 1 },
  { id: 'dims', name: 'Kóty a popisky', visible: true, locked: false, opacity: 1 },
];

// ---- items
const items = [];
const poly = (layer, role, pts, label) => items.push({ id: id(), layer, type: 'polygon', role, pts: P(pts), ...(label ? { label } : {}) });
const rect = (layer, role, x, z, w, d, rot = 0, label) => items.push({ id: id(), layer, type: 'rect', role, x: r3(x), z: r3(z), w: r3(w), d: r3(d), rot: r3(rot), ...(label ? { label } : {}) });

poly('site', 'plot', D.P, 'pozemek');
poly('site', 'building', D.HOUSE, 'Rodinný dům');
poly('site', 'building', D.GARAGE, 'Garáž');
poly('site', 'deck', D.DECK_EDGE, 'terasa');
poly('site', 'pool', D.POOL, 'bazén');
rect('site', 'pergola', 3.975, 9.95, 7.95, 2.6, 0, 'pergola');
D.PLANTERS.forEach(([a, b]) => rect('site', 'planter', (a + b) / 2, -3.1, b - a, 1.4, 0, 'vyvýšený záhon'));
for (const f of D.FURNITURE) {
  if (f.type === 'playhouse') rect('site', 'structure', f.x, f.z, f.w, f.d, f.rot || 0, 'domek');
  if (f.type === 'woodshed') rect('site', 'structure', f.x, f.z, f.w, f.d, f.rot || 0, 'dřevník');
  if (f.type === 'firebowl') items.push({ id: id(), layer: 'site', type: 'circle', role: 'fire', x: f.x, z: f.z, r: f.r, label: 'ohniště' });
  if (f.type === 'boulder') items.push({ id: id(), layer: 'plants-existing', type: 'plant', sp: 'L', x: f.x, z: f.z, rot: 0, d: r3(2 * f.r) });
}

[D.DRIVE, D.RAMP].forEach(p => poly('paving', 'pave', p, 'příjezd'));
poly('paving', 'stone', D.PATIO, 'dlažba u vstupu');
D.GRAVEL.forEach(g => poly('paving', 'gravel', g, 'kačírek'));
items.push({ id: id(), layer: 'paving', type: 'circle', role: 'gravel', x: D.FIRE.x, z: D.FIRE.z, r: D.FIRE.r, label: 'oblázky' });
D.SLABS.forEach(s => rect('paving', 'slab', s.x, s.z, D.PATH.along, D.PATH.across, s.ang * 180 / Math.PI));

poly('beds', 'lawn', D.LAWN, 'trávník');
D.DESIGN_BEDS.forEach(b => poly('beds', 'bed', b, 'záhon'));

for (const p of D.PLANTS) {
  const v = VARIANTS[p.type], sp = v[Math.floor(p.c * v.length) % v.length];
  items.push({ id: id(), layer: 'plants-existing', type: 'plant', sp, x: r3(p.x), z: r3(p.z), rot: r3(p.rot), d: r3(2 * p.r * 0.9) });
}
for (const p of D.DESIGN_PLANTS) {
  items.push({ id: id(), layer: p.existing ? 'plants-existing' : 'plants-new', type: 'plant', sp: String(p.sp), x: r3(p.x), z: r3(p.z), rot: r3(p.rot) });
}
for (const t of D.TREES) {
  items.push({ id: id(), layer: 'plants-existing', type: 'plant', sp: 't-' + slug(t.name || t.kind), x: t.x, z: t.z, rot: 0, d: r3(2 * t.r), h: t.h });
}

const dim = (a, b, off) => items.push({ id: id(), layer: 'dims', type: 'dim', a, b, off });
dim(D.P[0], D.P[1], -0.6);
dim([0, -4.7], [0, 0], 0.6);
dim([0, 0], [14.9, 0], 0.5);

const layout = {
  version: 1,
  units: 'm',
  axes: 'x na východ, z na jih k ulici; počátek v SZ rohu domu',
  meta: { name: 'Zahrada – stávající stav', created: new Date().toISOString().slice(0, 10), source: 'tools/editor/from_scene.mjs' },
  layers, catalog, items,
};
fs.writeFileSync(path.join(HERE, 'layout.json'), JSON.stringify(layout));
fs.writeFileSync(path.join(HERE, 'layout.js'), '// Generated by from_scene.mjs, the default layout for editor.html\nwindow.DEFAULT_LAYOUT = ' + JSON.stringify(layout) + ';\n');
console.log(`layout.json: ${items.length} items, ${Object.keys(catalog).length} species`);
