// Draws the A3 planting plan (1 : 150) from a layout as an SVG string, with numbered plants and a legend.
// Shared by the editor (button "Půdorys PDF") and by tools/preview/plan.mjs (PDF from the command line).
// Plain script: defines globalThis.drawPlan(layout, {title, subtitle}).
(function(){
  const W = 420, Hp = 297, S = 1000 / 150, X0 = 18, Y0 = 37;
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
  const f = n => (+n).toFixed(2);
  const ROLE_CLASS = {plot: 'plot', lawn: 'lawn', bed: 'bed', pave: 'pave', stone: 'stone', gravel: 'gravel', slab: 'slab', deck: 'deck',
    pool: 'pool', building: 'house', pergola: 'pergola', planter: 'planter', structure: 'struct', fire: 'fire'};
  const ORDER = {plot: 0, lawn: 1, bed: 2, pave: 3, stone: 3, gravel: 4, deck: 5, slab: 5, pool: 6, building: 7, pergola: 8, planter: 8, structure: 8, fire: 9};

  function drawPlan(L, opt = {}){
    const items = L.items.filter(i => { const l = L.layers.find(x => x.id === i.layer); return l && l.visible !== false && i.layer !== 'underlay'; });
    const cat = L.catalog || {}, plot = items.find(i => i.role === 'plot');
    const xs = plot ? plot.pts.map(p => p[0]) : [0], zs = plot ? plot.pts.map(p => p[1]) : [0];
    const MINX = Math.min(...xs), MINZ = Math.min(...zs);
    const X = x => X0 + (x - MINX) * S, Y = z => Y0 + (z - MINZ) * S;
    const pts = p => p.map(([x, z]) => `${f(X(x))},${f(Y(z))}`).join(' ');
    const out = [];
    // surfaces and structures
    for (const it of items.filter(i => i.type !== 'plant' && i.type !== 'dim' && i.type !== 'text').sort((a, b) => (ORDER[a.role] ?? 5) - (ORDER[b.role] ?? 5))){
      const cls = ROLE_CLASS[it.role] || 'bed';
      if (it.type === 'polygon'){
        out.push(`<polygon points="${pts(it.pts)}" class="${it.role === 'plot' ? 'plotfill' : cls}"/>`);
        if (it.role === 'building' && it.label){ const c = it.pts.reduce((a, p) => [a[0] + p[0] / it.pts.length, a[1] + p[1] / it.pts.length], [0, 0]); out.push(`<text x="${f(X(c[0]))}" y="${f(Y(c[1]))}" class="big">${esc(it.label.toUpperCase())}</text>`); }
      } else if (it.type === 'rect'){
        out.push(`<rect x="${f(-it.w / 2 * S)}" y="${f(-it.d / 2 * S)}" width="${f(it.w * S)}" height="${f(it.d * S)}" class="${cls}" transform="translate(${f(X(it.x))},${f(Y(it.z))}) rotate(${f(it.rot || 0)})"/>`);
        if (it.label && it.role !== 'slab') out.push(`<text x="${f(X(it.x))}" y="${f(Y(it.z) + .8)}" class="tiny">${esc(it.label)}</text>`);
      } else if (it.type === 'circle'){
        out.push(`<circle cx="${f(X(it.x))}" cy="${f(Y(it.z))}" r="${f(it.r * S)}" class="${cls}"/>`);
        if (it.role === 'fire') out.push(`<text x="${f(X(it.x))}" y="${f(Y(it.z) + it.r * S + 3)}" class="tiny">${esc(it.label || 'ohniště')}</text>`);
      }
    }
    // plants, big ones first; trees get a dashed crown and an S-number
    const used = {}, trees = [];
    const plants = items.filter(i => i.type === 'plant').sort((a, b) => (b.d || cat[b.sp]?.d || .5) - (a.d || cat[a.sp]?.d || .5));
    for (const p of plants){
      const s = cat[p.sp] || {code: '?', cz: p.sp, leaf: '#999'}, r = (p.d || s.d || .5) / 2;
      if (s.group === 'tree'){ trees.push({p, s, r}); continue; }
      (used[p.sp] ??= {s, n: 0, e: 0})[p.layer === 'plants-new' ? 'n' : 'e']++;
      out.push(`<circle cx="${f(X(p.x))}" cy="${f(Y(p.z))}" r="${f(r * S)}" fill="${s.flower || s.leaf}" class="plant${p.layer === 'plants-new' ? ' new' : ''}"/>`);
      if (r * S > 1.1) out.push(`<text x="${f(X(p.x))}" y="${f(Y(p.z) + r * S * .36)}" class="pl" style="font-size:${f(Math.min(r * S, 2.4))}px">${esc(s.code)}</text>`);
    }
    trees.forEach(({p, s, r}, i) => {
      out.push(`<circle cx="${f(X(p.x))}" cy="${f(Y(p.z))}" r="${f(r * S)}" fill="${s.leaf}" class="tree"/><circle cx="${f(X(p.x))}" cy="${f(Y(p.z))}" r=".7" class="trunk"/>`);
      out.push(`<text x="${f(X(p.x) + 1.4)}" y="${f(Y(p.z) - 1.2)}" class="tl">S${i + 1}</text>`);
    });
    if (plot) out.push(`<polygon points="${pts(plot.pts)}" class="plot"/>`);
    // dimensions and texts
    for (const d of items.filter(i => i.type === 'dim')){
      const a = [X(d.a[0]), Y(d.a[1])], b = [X(d.b[0]), Y(d.b[1])], len = Math.hypot(b[0] - a[0], b[1] - a[1]); if (len < .1) continue;
      const ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len, o = (d.off || 0) * S, A = [a[0] - uy * o, a[1] + ux * o], B = [b[0] - uy * o, b[1] + ux * o];
      out.push(`<line x1="${f(A[0])}" y1="${f(A[1])}" x2="${f(B[0])}" y2="${f(B[1])}" class="dim"/>`);
      for (const P of [A, B]) out.push(`<line x1="${f(P[0] - (ux - uy))}" y1="${f(P[1] - (uy + ux))}" x2="${f(P[0] + (ux - uy))}" y2="${f(P[1] + (uy + ux))}" class="dim"/>`);
      let ang = Math.atan2(uy, ux) * 180 / Math.PI; if (ang > 90 || ang < -90) ang += 180;
      const m = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2 - .8], m2 = Math.hypot(d.b[0] - d.a[0], d.b[1] - d.a[1]);
      out.push(`<text x="${f(m[0])}" y="${f(m[1])}" class="dimt" transform="rotate(${f(ang)} ${f(m[0])} ${f(m[1])})">${m2.toLocaleString('cs-CZ', {minimumFractionDigits: 2, maximumFractionDigits: 2})} m</text>`);
    }
    for (const t of items.filter(i => i.type === 'text')) out.push(`<text x="${f(X(t.x))}" y="${f(Y(t.z))}" class="lbl" style="font-size:${f((t.size || .4) * S)}px">${esc(t.text)}</text>`);
    // legend
    const LX = 262; let ly = 34; const leg = [];
    const head = s => { leg.push(`<text x="${LX}" y="${f(ly)}" class="legh">${esc(s)}</text>`); ly += 6; };
    const sw = (col, code, txt, n) => { leg.push(`<circle cx="${LX + 2.4}" cy="${f(ly - 1.3)}" r="2.3" fill="${col}" class="plant"/><text x="${LX + 2.4}" y="${f(ly - .45)}" class="pl" style="font-size:2.3px">${esc(code)}</text><text x="${LX + 7}" y="${f(ly)}" class="leg">${txt}</text>${n ? `<text x="${LX + 150}" y="${f(ly)}" class="leg n">${n}</text>` : ''}`); ly += 5.2; };
    const groups = [['perennial', 'Trvalky'], ['shrub', 'Keře'], ['grass', 'Trávy'], ['stone', 'Ostatní']];
    for (const [g, name] of groups){
      const list = Object.entries(used).filter(([, u]) => (u.s.group || 'shrub') === g).sort((a, b) => String(a[1].s.code).localeCompare(String(b[1].s.code), 'cs', {numeric: true}));
      if (!list.length) continue; head(name);
      for (const [, u] of list) sw(u.s.flower || u.s.leaf, u.s.code, `${esc(u.s.cz)}${u.s.lat ? ` <tspan class="lat">${esc(u.s.lat)}</tspan>` : ''}`, [u.e && `${u.e}× stáv.`, u.n && `${u.n}× návrh`].filter(Boolean).join(', '));
      ly += 2;
    }
    if (trees.length){ head('Stromy'); const half = Math.ceil(trees.length / 2), y0 = ly;
      trees.forEach(({s}, i) => leg.push(`<text x="${LX + (i < half ? 0 : 74)}" y="${f(y0 + (i % half) * 4.6)}" class="leg"><tspan class="tlb">S${i + 1}</tspan>  ${esc(s.cz)}</text>`)); ly = y0 + half * 4.6 + 3; }
    head('Plochy');
    for (const [cls, txt] of [['lawn', 'trávník'], ['bed', 'záhon, mulč'], ['gravel', 'kačírek, oblázky'], ['pave', 'dlažba'], ['deck', 'terasa'], ['slab', 'nášlapné desky']]){
      leg.push(`<rect x="${LX}" y="${f(ly - 3.6)}" width="5" height="4" class="${cls}"/><text x="${LX + 7}" y="${f(ly)}" class="leg">${txt}</text>`); ly += 5;
    }
    const bar = [0, 1, 2, 3, 4, 5, 10].map(m => `<line x1="${f(X0 + m * S)}" y1="281.5" x2="${f(X0 + m * S)}" y2="284.5" class="dim"/><text x="${f(X0 + m * S)}" y="288" class="dimt">${m}</text>`).join('');
    const title = opt.title || L.meta?.label || L.meta?.name || 'Zahrada';
    const sub = opt.subtitle || `Layout z editoru${L.meta?.saved ? ', uloženo ' + new Date(L.meta.saved).toLocaleString('cs-CZ') : ''}. Měřítko 1 : 150 na A3.`;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}mm" height="${Hp}mm" viewBox="0 0 ${W} ${Hp}">
<defs>
<pattern id="hatch" width="2.2" height="2.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="2.2" stroke="#8d8a83" stroke-width=".35"/></pattern>
<pattern id="dots" width="1.6" height="1.6" patternUnits="userSpaceOnUse"><rect width="1.6" height="1.6" fill="#ecebe6"/><circle cx=".8" cy=".8" r=".32" fill="#b4b1a8"/></pattern>
<pattern id="boards" width="1.2" height="10" patternUnits="userSpaceOnUse"><rect width="1.2" height="10" fill="#c99486"/><line x1="0" y1="0" x2="0" y2="10" stroke="#a5746a" stroke-width=".2"/></pattern>
<pattern id="pavers" width="3" height="2" patternUnits="userSpaceOnUse"><rect width="3" height="2" fill="#dad5ca"/><path d="M0 0H3M0 1H3M1.5 0V1M0 1V2" stroke="#bdb6a8" stroke-width=".18"/></pattern>
</defs>
<style>
text{font-family:Helvetica,Arial,sans-serif;fill:#22281f}.plot{fill:none;stroke:#22281f;stroke-width:.7}.plotfill{fill:#e9dccb}
.lawn{fill:#d5e8c0;stroke:#8fb26c;stroke-width:.25}.bed{fill:#e9dccb;stroke:#7a5c3a;stroke-width:.3;stroke-dasharray:1.6 1}
.pave{fill:url(#pavers);stroke:#9d968a;stroke-width:.25}.stone{fill:#e6e1d6;stroke:#9d968a;stroke-width:.25}.deck{fill:url(#boards);stroke:#8a5a4e;stroke-width:.3}
.pool{fill:#bfe0ea;stroke:#5a9bb0;stroke-width:.3}.gravel{fill:url(#dots);stroke:#a7a59f;stroke-width:.25}.slab{fill:#cfd0cc;stroke:#8f908c;stroke-width:.25}
.planter{fill:#d8c7a8;stroke:#8a7552;stroke-width:.3}.house{fill:url(#hatch);stroke:#22281f;stroke-width:.6}.pergola{fill:none;stroke:#45494e;stroke-width:.35;stroke-dasharray:2 1}
.struct{fill:#e2ddd2;stroke:#5c5850;stroke-width:.35}.fire{fill:#a3562a;stroke:#5a2c16;stroke-width:.25}
.plant{fill-opacity:.82;stroke:#2f3b2a;stroke-width:.18}.plant.new{stroke:#22281f;stroke-width:.28}.tree{fill-opacity:.18;stroke:#2f3b2a;stroke-width:.3;stroke-dasharray:1.2 .7}.trunk{fill:#5e4430}
.pl{text-anchor:middle;font-weight:600;fill:#111}.tl{font-size:2.4px;font-weight:700;fill:#2f3b2a}.big{font-size:3.6px;font-weight:700;text-anchor:middle}
.tiny{font-size:2px;text-anchor:middle;fill:#333}.lbl{text-anchor:middle}.dim{stroke:#22281f;stroke-width:.22}.dimt{font-size:2.4px;text-anchor:middle}
.leg{font-size:2.8px}.leg.n{text-anchor:end;fill:#67705f}.lat{font-style:italic;fill:#67705f}.legh{font-size:3.2px;font-weight:700}.tlb{font-weight:700}
.title{font-size:6.5px;font-weight:700}.sub{font-size:3px;fill:#4a5145}
</style>
<rect width="${W}" height="${Hp}" fill="#fff"/>
<text x="${X0}" y="15" class="title">${esc(title)}</text><text x="${X0}" y="21.5" class="sub">${esc(sub)}</text>
${out.join('\n')}
<g transform="translate(240 48)"><polygon points="0,-8 3,2 0,0 -3,2" fill="#22281f"/><text x="0" y="7" class="big">S</text></g>
<line x1="${X0}" y1="283" x2="${f(X0 + 10 * S)}" y2="283" class="dim"/>${bar}<text x="${f(X0 + 10 * S + 3)}" y="284" class="leg">m · měřítko 1 : 150 (A3)</text>
${leg.join('\n')}
<text x="${LX}" y="288" class="sub">gardenvisu · ${new Date().toLocaleDateString('cs-CZ')}</text>
</svg>`;
  }
  globalThis.drawPlan = drawPlan;
})();
