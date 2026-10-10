/* Garden 3D built from a layout (tools/editor) with Three.js r128.
 * Architecture (house, garage, deck, drive, fences) comes from scene.glb exported from index.html; everything the
 * editor owns (lawn, beds, gravel, slabs, structures, plants, trees) is rebuilt from the chosen layout version.
 * Rendering approach, plant prototypes, textures, sky and walking are taken over from Codex's experiments/realism. */
'use strict';
const $ = id => document.getElementById(id);
const RAMP = [[18.4,23.2],[23.7,23.2],[24.9,31.07],[18.4,31.07]];   // sloped part of the drive, part of the architecture
const VIEWS = {
  west: [[.8,1.75,19.5],[-4.2,1.2,9]], detail: [[-1.65,1.15,13],[-3.5,.42,10.2]], north: [[13,1.7,-1.9],[-1,1,-2]],
  yard: [[14.4,1.65,-1.0],[21,.3,1.4]], overview: [[-13,16,27],[3,0,9]], top: [[11.6,48,13.3],[11.6,0,13.2]],
};
async function getJSON(url){ const r = await fetch(url, {cache: 'no-store'}); if (!r.ok) throw new Error(`${url} (${r.status})`); return r.json(); }
function inside(x, z, poly){ let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++){ const [xi, zi] = poly[i], [xj, zj] = poly[j]; if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) c = !c; } return c; }
const fmtDate = s => { const d = new Date(s); return isNaN(d) ? s : d.toLocaleString('cs-CZ', {day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit'}); };

// ---------- which layout ----------
async function listSources(){
  const opts = [['model', 'Výchozí model (z projektu)']];
  try {
    const list = await getJSON('api/versions');
    opts.unshift(['latest', 'Editor – vždy poslední uložená verze']);
    for (const v of list) opts.push([v.id, `${v.id === 'current' ? 'Aktuální: ' : ''}${fmtDate(v.saved)}${v.label ? ' · ' + v.label : ''} · ${v.items} prvků`]);
  } catch (e) { /* no editor API next to the viewer */ }
  return opts;
}
const layoutURL = v => v === 'model' ? 'layout-default.json' : (v === 'latest' || v === 'current') ? 'api/layout' : 'api/layout?v=' + encodeURIComponent(v);

async function init(){
  const stage = $('stage'), status = $('status');
  // ---------- renderer, camera, light (after experiments/realism) ----------
  const renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'high-performance'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputEncoding = THREE.sRGBEncoding; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = .9;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  stage.prepend(renderer.domElement);
  const scene = new THREE.Scene(); scene.background = new THREE.Color('#d4e0e6');
  scene.fog = new THREE.Fog(scene.background.clone().convertSRGBToLinear(), 65, 160);
  const camera = new THREE.PerspectiveCamera(48, 1, .06, 300);
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.maxPolarAngle = Math.PI * .495; controls.minDistance = .5; controls.maxDistance = 120; controls.screenSpacePanning = false;
  scene.add(new THREE.HemisphereLight(0xd9e8fa, 0x7d775c, .55));
  const sun = new THREE.DirectionalLight(0xffeedc, 1.1); sun.position.set(-18, 32, 25); sun.target.position.set(8, 0, 12); scene.add(sun, sun.target);
  sun.castShadow = true; sun.shadow.mapSize.set(4096, 4096); sun.shadow.bias = -.00012; sun.shadow.normalBias = .025;
  Object.assign(sun.shadow.camera, {left: -26, right: 26, top: 26, bottom: -26, near: 1, far: 110});
  let pending = false;
  const render = () => { pending = false; renderer.render(scene, camera); };
  const requestRender = () => { if (!pending){ pending = true; requestAnimationFrame(render); } };
  function resize(){ if (!stage.clientWidth) return; renderer.setSize(stage.clientWidth, stage.clientHeight); camera.aspect = stage.clientWidth / stage.clientHeight; camera.updateProjectionMatrix(); requestRender(); }
  new ResizeObserver(resize).observe(stage); controls.addEventListener('change', requestRender);
  let walker;
  function setView(key){ const v = VIEWS[key]; camera.position.set(...v[0]); controls.target.set(...v[1]); controls.update(); walker?.syncView(!['overview', 'top', 'detail'].includes(key)); $('plant-info').hidden = true; requestRender(); }
  $('view').onchange = e => setView(e.target.value);
  setView('west'); resize();

  // ---------- shared assets ----------
  status.textContent = 'Načítám architekturu, textury a rostliny…';
  const loader = new THREE.TextureLoader(), warnings = [];
  async function texture(path, scale, color = false){ const t = await loader.loadAsync(path); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(scale, scale); t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); if (color) t.encoding = THREE.sRGBEncoding; return t; }
  const pbr = {};
  await Promise.all([['lawn', 'leafy_grass', .5], ['soil', 'aerial_wood_snips', .5], ['deck', 'wood_floor_deck', .5]].map(async ([name, folder, scale]) => {
    try { const [map, normalMap, roughnessMap] = await Promise.all([texture(`assets/${folder}/diff.jpg`, scale, true), texture(`assets/${folder}/nor.jpg`, scale), texture(`assets/${folder}/rough.jpg`, scale)]);
      pbr[name] = new THREE.MeshStandardMaterial({name, map, normalMap, roughnessMap, roughness: 1, envMapIntensity: .3, color: name === 'lawn' ? new THREE.Color(.28, .58, .15) : new THREE.Color(1, 1, 1), normalScale: new THREE.Vector2(.55, .55)});
    } catch (e) { warnings.push(`textura ${name} chybí`); }
  }));
  const gltfLoader = new THREE.GLTFLoader();
  const [gltf, manifest, buffer, models] = await Promise.all([
    gltfLoader.loadAsync('assets/scene.glb'), getJSON('assets/plants.json'), fetch('assets/plants.bin').then(r => r.arrayBuffer()),
    Promise.all(['tree_small_02', 'boulder_01'].map(n => gltfLoader.loadAsync(`assets/models/${n}.glb`).catch(() => { warnings.push(`model ${n} chybí`); return null; }))),
  ]);

  // Architecture: correct colours for linear lighting, hide what the layout replaces
  const arch = gltf.scene; scene.add(arch); arch.updateMatrixWorld(true);
  let waterBox = null;
  arch.traverse(o => { if (o.isMesh && [].concat(o.material).some(m => m.name === 'water')) waterBox = new THREE.Box3().setFromObject(o); });
  arch.traverse(o => {
    if (o.isLight){ o.visible = false; return; }
    if (o.name === 'beds' || o.name === 'lawn'){ o.visible = false; return; }     // planters and lawn come from the layout
    if (!o.isMesh) return;
    o.castShadow = o.receiveShadow = true;
    const mats = [].concat(o.material), names = mats.map(m => m.name);
    if (names.some(n => ['lawn', 'veg', 'cover', 'mesh'].includes(n))){ o.visible = false; return; }
    if (waterBox && names.includes('alu')){ const b = new THREE.Box3().setFromObject(o); if (b.max.y < .9 && waterBox.clone().expandByScalar(.6).containsBox(b)){ o.visible = false; return; } }
    const fixed = mats.map(orig => { if (pbr[orig.name]) return pbr[orig.name]; const m = orig.clone(); m.color.convertSRGBToLinear(); m.envMapIntensity = .45;
      if (m.name === 'water'){ m.roughness = .18; m.metalness = .2; } if (m.name === 'glass'){ m.color.set('#62777e').convertSRGBToLinear(); m.metalness = .75; m.roughness = .16; } return m; });
    o.material = Array.isArray(o.material) ? fixed : fixed[0];
    if (mats.some(m => pbr[m.name])){ const geo = o.geometry.clone(), a = geo.attributes.position, uv = [], v = new THREE.Vector3(); for (let i = 0; i < a.count; i++){ v.fromBufferAttribute(a, i).applyMatrix4(o.matrixWorld); uv.push(v.x, -v.z); } geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); o.geometry = geo; }
  });
  if (waterBox) poolEnclosure(scene, waterBox);

  // Plant prototypes from Blender geometry (plants.bin) and the scanned tree / boulder
  const proto = {};
  for (const [name, m] of Object.entries(manifest.meshes)){
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(buffer, m.position.offset, m.position.length), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(buffer, m.color.offset, m.color.length), 3));
    g.setIndex(new THREE.BufferAttribute(new Uint32Array(buffer, m.index.offset, m.index.length), 1)); g.computeVertexNormals(); g.computeBoundingSphere(); proto[name] = g;
  }
  const scanned = {};
  for (const [name, asset] of [['tree', models[0]], ['rock', models[1]]]){
    if (!asset) continue; asset.scene.updateMatrixWorld(true); const all = new THREE.Box3().setFromObject(asset.scene), parts = [];
    asset.scene.traverse(o => { if (!o.isMesh) return; const g = o.geometry.clone(); g.applyMatrix4(o.matrixWorld);
      const size = all.getSize(new THREE.Vector3()), c = all.getCenter(new THREE.Vector3()), r = Math.max(size.x, size.z) / 2;
      g.translate(-c.x, -all.min.y, -c.z); g.scale(1 / r, 1 / Math.max(.01, size.y), 1 / r); g.computeBoundingSphere();
      const mat = o.material.clone(); mat.side = THREE.DoubleSide; mat.transparent = false; mat.alphaTest = .45; mat.roughness = .87; mat.envMapIntensity = .3; parts.push({g, mat}); });
    scanned[name] = parts;
  }
  const leafMat = new THREE.MeshStandardMaterial({vertexColors: true, side: THREE.DoubleSide, roughness: .86, envMapIntensity: .35});
  const plainMat = new THREE.MeshStandardMaterial({roughness: .95});
  const pebbleMat = new THREE.MeshStandardMaterial({color: new THREE.Color('#d9d7d0').convertSRGBToLinear(), roughness: .9});
  const slabMat = new THREE.MeshStandardMaterial({color: new THREE.Color('#bdbdb8').convertSRGBToLinear(), roughness: .8});
  const woodMat = new THREE.MeshStandardMaterial({color: new THREE.Color('#c9c4b6').convertSRGBToLinear(), roughness: .85});
  const darkMat = new THREE.MeshStandardMaterial({color: new THREE.Color('#4b4f54').convertSRGBToLinear(), roughness: .6});
  const logMat = new THREE.MeshStandardMaterial({color: new THREE.Color('#b98a5e').convertSRGBToLinear(), roughness: .9});
  const corten = new THREE.MeshStandardMaterial({color: new THREE.Color('#8a4a24').convertSRGBToLinear(), roughness: .8});
  const ball = new THREE.SphereGeometry(1, 10, 7), cone = new THREE.ConeGeometry(1, 2, 10), rockGeo = new THREE.DodecahedronGeometry(1, 1);

  // HDR sky for the background and reflections, neighbour house as context
  try { const hdr = await new THREE.RGBELoader().setDataType(THREE.HalfFloatType).loadAsync('assets/sky.hdr'); hdr.mapping = THREE.EquirectangularReflectionMapping;
    const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromEquirectangular(hdr).texture; scene.background = hdr; pm.dispose(); } catch (e) { warnings.push('HDR obloha chybí'); }

  // ---------- the layout-driven part ----------
  const layoutGroup = new THREE.Group(); scene.add(layoutGroup);
  let detailed, simple, pickables = [], quality = 'detailed';
  const { createWalkController } = await import('./walk.js');

  function build(L){
    layoutGroup.traverse(o => { if (o.userData.own) o.geometry.dispose(); });
    layoutGroup.clear(); pickables = [];
    detailed = new THREE.Group(); simple = new THREE.Group(); layoutGroup.add(detailed, simple);
    const items = L.items.filter(i => i.layer !== 'underlay' && i.layer !== 'dims'), cat = L.catalog || {};
    const own = m => { m.userData.own = true; m.castShadow = m.receiveShadow = true; return m; };
    const flat = (pts, y, mat, g = layoutGroup) => { const s = new THREE.Shape(pts.map(([x, z]) => new THREE.Vector2(x, -z))); const m = own(new THREE.Mesh(new THREE.ShapeGeometry(s), mat)); m.rotation.x = -Math.PI / 2; m.position.y = y; m.castShadow = false; g.add(m); return m; };
    const box = (x, z, w, d, y0, h, rot, mat) => { const m = own(new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat)); m.position.set(x, y0 + h / 2, z); m.rotation.y = -(rot || 0) * Math.PI / 180; layoutGroup.add(m); return m; };
    // surfaces and things the editor owns
    for (const it of items){
      if (it.type === 'polygon'){
        if (it.role === 'lawn') flat(it.pts, .012, pbr.lawn || plainMat);
        else if (it.role === 'bed') flat(it.pts, .02, pbr.soil || plainMat);
        else if (it.role === 'gravel') flat(it.pts, .025, pebbleMat);
      } else if (it.type === 'circle'){
        if (it.role === 'gravel'){ const m = own(new THREE.Mesh(new THREE.CircleGeometry(it.r, 40), pebbleMat)); m.rotation.x = -Math.PI / 2; m.position.set(it.x, .03, it.z); layoutGroup.add(m); }
        if (it.role === 'fire'){ const m = own(new THREE.Mesh(new THREE.CylinderGeometry(it.r, it.r * .45, .3, 24), corten)); m.position.set(it.x, .3, it.z); layoutGroup.add(m); }
      } else if (it.type === 'rect'){
        if (it.role === 'slab') box(it.x, it.z, it.w, it.d, 0, .06, it.rot, slabMat);
        else if (it.role === 'planter'){ box(it.x, it.z, it.w, it.d, 0, .45, it.rot, woodMat); box(it.x, it.z, it.w - .16, it.d - .16, .44, .03, it.rot, pbr.soil || plainMat); }
        else if (it.role === 'structure'){
          const shed = /dřevník/i.test(it.label || ''), h = shed ? 2.0 : /domek/i.test(it.label || '') ? 1.2 : 1.5;
          box(it.x, it.z, it.w, it.d, 0, h, it.rot, shed ? logMat : woodMat);
          box(it.x, it.z, it.w + .25, it.d + .25, h, .06, it.rot, darkMat);
        }
      }
    }
    // plants: shared prototypes, one InstancedMesh per prototype and group
    const buckets = new Map(), white = new THREE.Color('white'), col = new THREE.Color(), dummy = new THREE.Object3D();
    const add = (key, geo, mat, group, item, place, tint, pick = true) => { if (!geo) return; const k = key + '|' + group.uuid; if (!buckets.has(k)) buckets.set(k, {geo, mat, group, list: [], pick}); buckets.get(k).list.push({item, place, tint}); };
    // shrub, tree and conifer prototypes have white leaves, so the instance colour is the species colour;
    // the grass prototype already has its own green and only gets a light tint
    const foliage = new THREE.Color('#58763c'), tintOf = hex => new THREE.Color(hex || '#6b8f4a').lerp(foliage, .3);   // autumn colours as accents, not paint
    const grassTint = hex => new THREE.Color(hex || '#c8ad72').lerp(white, .5);
    for (const it of items){
      if (it.type !== 'plant') continue;
      const s = cat[it.sp] || {group: 'shrub', d: .6, h: .6, leaf: '#6b8f4a'}, d = it.d || s.d || .6, r = d / 2, h = it.h || s.h || d, rot = it.rot || 0;
      const at = (y, sx, sy, sz) => o => { o.position.set(it.x, y, it.z); o.rotation.set(0, rot, 0); o.scale.set(sx, sy, sz); };
      if (s.group === 'perennial' && proto[`species-${s.code}`]){ const f = d / (s.d || d); add('sp' + s.code, proto[`species-${s.code}`], leafMat, detailed, it, at(.03, f, f, f), white); }
      else if (s.group === 'tree'){
        if (s.kind === 'conifer') add('conifer', proto.conifer, leafMat, detailed, it, at(0, r, h, r), tintOf(s.leaf));
        else if (scanned.tree) scanned.tree.forEach((p, i) => add('tree' + i, p.g, p.mat, detailed, it, at(.012, r, h, r), white));
        else add('tree', proto.tree, leafMat, detailed, it, at(0, r, h, r), tintOf(s.leaf));
      }
      else if (s.group === 'stone'){ if (scanned.rock) scanned.rock.forEach((p, i) => add('rock' + i, p.g, p.mat, detailed, it, at(.012, r, r * .85, r), white)); else add('rockS', rockGeo, plainMat, detailed, it, at(r * .2, r, r * .55, r), col.set(s.leaf).clone()); }
      else if (s.group === 'grass') add('grass', proto.grass, leafMat, detailed, it, at(.01, r, r, r), grassTint(s.leaf));
      else add('shrub', proto.shrub, leafMat, detailed, it, at(.01, r, r * (s.code === 'J' ? .65 : 1), r), tintOf(s.leaf));
      // simple shapes
      const flower = new THREE.Color(s.flower || s.leaf || '#6b8f4a');
      if (s.group === 'tree') add('sT' + s.kind, s.kind === 'conifer' ? cone : ball, plainMat, simple, it, at(s.kind === 'conifer' ? h / 2 : h - r, r, s.kind === 'conifer' ? h / 2 : r * 1.15, r), flower, false);
      else add(s.group === 'grass' ? 'sG' : 'sB', s.group === 'grass' ? cone : ball, plainMat, simple, it, at(h * .45, r, h / 2, r), flower, false);
    }
    for (const b of buckets.values()){
      const m = new THREE.InstancedMesh(b.geo, b.mat, b.list.length); m.frustumCulled = false; m.castShadow = m.receiveShadow = true;
      b.list.forEach((e, i) => { dummy.position.set(0, 0, 0); dummy.rotation.set(0, 0, 0); dummy.scale.set(1, 1, 1); e.place(dummy); dummy.updateMatrix(); m.setMatrixAt(i, dummy.matrix); m.setColorAt(i, e.tint.clone().convertSRGBToLinear()); });
      m.instanceMatrix.needsUpdate = true; m.userData.items = b.list.map(e => e.item); b.group.add(m); if (b.pick) pickables.push(m);
    }
    // short grass blades on the lawn (after experiments/realism)
    const lawns = items.filter(i => i.role === 'lawn').map(i => i.pts);
    const holes = items.filter(i => i.type === 'polygon' && i.role !== 'lawn' && i.role !== 'plot').map(i => i.pts);
    let seed = 5531; const rand = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
    const V = [], C = [], I = [];
    for (let i = 0; i < 90000; i++){
      const x = -4 + rand() * 32, z = -1 + rand() * 29;
      if (!lawns.some(p => inside(x, z, p)) || holes.some(p => inside(x, z, p))) continue;
      if (x > 1 && rand() > .45) continue;
      const a = rand() * Math.PI * 2, w = .002 + rand() * .004, hh = .018 + rand() * .025, dx = Math.cos(a) * w, dz = Math.sin(a) * w, bend = .009, base = V.length / 3;
      V.push(x - dx, .018, z - dz, x + dx, .018, z + dz, x + dx * .5 + bend, .018 + hh * .6, z + dz * .5, x - dx * .5 + bend, .018 + hh * .6, z - dz * .5, x + bend * 1.5, .018 + hh, z);
      const c = new THREE.Color().setHSL(.23 + rand() * .04, .38 + rand() * .2, .34 + rand() * .1).convertSRGBToLinear();
      for (let k = 0; k < 5; k++) C.push(c.r * (k < 2 ? .6 : 1), c.g * (k < 2 ? .6 : 1), c.b * (k < 2 ? .6 : 1));
      I.push(base, base + 1, base + 2, base, base + 2, base + 3, base + 3, base + 2, base + 4);
    }
    const gg = new THREE.BufferGeometry(); gg.setAttribute('position', new THREE.Float32BufferAttribute(V, 3)); gg.setAttribute('color', new THREE.Float32BufferAttribute(C, 3)); gg.setIndex(I); gg.computeVertexNormals();
    const blades = own(new THREE.Mesh(gg, new THREE.MeshStandardMaterial({vertexColors: true, side: THREE.DoubleSide, roughness: 1, envMapIntensity: .25}))); blades.castShadow = false; detailed.add(blades);
    // wire fence on the two chain-link edges (north, west) of the plot
    const plot = items.find(i => i.role === 'plot');
    if (plot && plot.pts.length > 12){
      const pos = [];
      for (const [a, b] of [[plot.pts[0], plot.pts[1]], [plot.pts[12], plot.pts[0]]]){
        const len = Math.hypot(b[0] - a[0], b[1] - a[1]), dx = (b[0] - a[0]) / len, dz = (b[1] - a[1]) / len;
        for (let t = -1.5; t < len + 1.5; t += .085) for (const sg of [-1, 1]){ const lo = Math.max(0, sg === 1 ? -t : t - len), hi = Math.min(1.5, sg === 1 ? len - t : t); if (hi <= lo) continue; for (const hh of [lo, hi]){ const u = t + sg * hh; pos.push(a[0] + u * dx, hh, a[1] + u * dz); } }
      }
      const fg = new THREE.BufferGeometry(); fg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      const fence = new THREE.LineSegments(fg, new THREE.LineBasicMaterial({color: '#50614b', transparent: true, opacity: .55})); fence.userData.own = true; layoutGroup.add(fence);
    }
    detailed.visible = quality === 'detailed'; simple.visible = !detailed.visible;
    // walking: obstacles and ground from the same layout
    const rects = items.filter(i => i.type === 'rect' && i.role === 'structure').map(i => [[i.x - i.w / 2, i.z - i.d / 2], [i.x + i.w / 2, i.z - i.d / 2], [i.x + i.w / 2, i.z + i.d / 2], [i.x - i.w / 2, i.z + i.d / 2]]);
    const world = {P: plot?.pts || [], OBSTACLES: [...items.filter(i => i.role === 'building' || i.role === 'pool').map(i => i.pts), ...rects],
      DECK_EDGE: items.find(i => i.role === 'deck')?.pts || [], RAMP};
    if (walker) walker.setData(world); else walker = createWalkController({camera, controls, canvas: renderer.domElement, data: world, requestRender, stage});
    const plants = items.filter(i => i.type === 'plant').length;
    $('cornerInfo').textContent = `${plants} rostlin`;
    renderer.shadowMap.needsUpdate = true; requestRender();
    return plants;
  }

  function setQuality(q){ quality = q; detailed.visible = q === 'detailed'; simple.visible = !detailed.visible; document.querySelectorAll('[data-quality]').forEach(b => b.setAttribute('aria-pressed', b.dataset.quality === q)); renderer.shadowMap.needsUpdate = true; $('plant-info').hidden = true; requestRender(); }
  document.querySelectorAll('[data-quality]').forEach(b => b.onclick = () => setQuality(b.dataset.quality));

  // plant info on click
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2(); let down; let current = null;
  renderer.domElement.addEventListener('pointerdown', e => down = [e.clientX, e.clientY]);
  renderer.domElement.addEventListener('pointerup', e => {
    if (!detailed?.visible || !down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
    const r = renderer.domElement.getBoundingClientRect(); ptr.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1); ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(pickables)[0], info = $('plant-info'); info.hidden = !hit; if (!hit) return;
    const it = hit.object.userData.items[hit.instanceId], s = (current.catalog || {})[it.sp] || {cz: it.sp};
    info.replaceChildren(); const b = document.createElement('b'); b.textContent = s.cz; const sm = document.createElement('small');
    sm.textContent = `${s.lat ? s.lat + ' · ' : ''}průměr ${(it.d || s.d || 0).toFixed(2)} m · ${it.layer === 'plants-new' ? 'návrh' : 'stávající'}`; info.append(b, sm);
  });

  // ---------- source selector ----------
  const params = new URLSearchParams(location.search);
  async function fillSources(keep){
    const opts = await listSources(), sel = $('source'); sel.replaceChildren();
    for (const [v, t] of opts){ const o = document.createElement('option'); o.value = v; o.textContent = t; sel.appendChild(o); }
    const want = keep || params.get('layout') || (opts.some(o => o[0] === 'latest') ? 'latest' : 'model');
    sel.value = opts.some(o => o[0] === want) ? want : opts[0][0];
  }
  async function load(){
    const v = $('source').value; status.hidden = false; status.textContent = 'Načítám layout…';
    try { current = await getJSON(layoutURL(v)); const n = build(current);
      $('sourceInfo').textContent = `${current.meta?.label ? '„' + current.meta.label + '“ · ' : ''}${current.meta?.saved ? 'uloženo ' + fmtDate(current.meta.saved) + ' · ' : ''}${n} rostlin`;
      const u = new URL(location.href); u.searchParams.set('layout', v); history.replaceState(null, '', u);
      status.hidden = true;
    } catch (e){ status.textContent = 'Layout se nepodařilo načíst: ' + e.message; }
  }
  $('source').onchange = load;
  $('reload').onclick = async () => { await fillSources($('source').value); await load(); };
  await fillSources(); await load();
  if (warnings.length){ const p = document.createElement('p'); p.className = 'caption'; p.textContent = 'Upozornění: ' + warnings.join(', ') + '.'; stage.after(p); }
  stage.dataset.ready = 'true';
  window.GARDEN3D = {scene, camera, renderer, setView, setQuality, get layout(){ return current; }};
}

// Custom Mountfield enclosure: three low segments, slightly sloping sides, a flat arch, milky panels (photos 21, 22)
function poolEnclosure(scene, box){
  const x0 = box.min.x - .15, x1 = box.max.x + .15, zc = (box.min.z + box.max.z) / 2, top = .15, n = 3, len = (x1 - x0) / n + .12;
  const panel = new THREE.MeshStandardMaterial({color: '#eef3f2', transparent: true, opacity: .55, roughness: .35, envMapIntensity: .6, side: THREE.DoubleSide, depthWrite: false});
  const frame = new THREE.MeshStandardMaterial({color: new THREE.Color('#45494e').convertSRGBToLinear(), roughness: .4, metalness: .5});
  const rail = new THREE.MeshStandardMaterial({color: '#d5d7d8', roughness: .3, metalness: .8});
  for (let i = 0; i < n; i++){
    const half = 2.02 - i * .07, side = .36 - i * .05, rise = .16 - i * .01, inner = half - .06, xa = x0 + i * (len - .12), xb = xa + len;
    const prof = [[-half, 0]]; for (let k = 0; k <= 16; k++){ const y = -inner + 2 * inner * k / 16; prof.push([y, side + rise * (1 - (y / inner) ** 2)]); } prof.push([half, 0]);
    const v = [], idx = [];
    prof.forEach(([y, h]) => v.push(xa, top + h, zc + y, xb, top + h, zc + y));
    for (let k = 0; k < prof.length - 1; k++){ const a = 2 * k; idx.push(a, a + 1, a + 3, a, a + 3, a + 2); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3)); g.setIndex(idx); g.computeVertexNormals();
    const m = new THREE.Mesh(g, panel); m.renderOrder = 2; scene.add(m);
    for (const xx of [xa, xb]){ const pts = prof.map(([y, h]) => new THREE.Vector3(xx, top + h, zc + y)); const t = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0), 40, .028, 5), frame); t.castShadow = true; scene.add(t); }
    for (const s of [-1, 1]){ const b = new THREE.Mesh(new THREE.BoxGeometry(len, .07, .06), frame); b.position.set((xa + xb) / 2, top + .035, zc + s * half); scene.add(b);
      const e = new THREE.Mesh(new THREE.BoxGeometry(len, .05, .05), frame); e.position.set((xa + xb) / 2, top + side, zc + s * inner); scene.add(e); }
  }
  for (const s of [-1, 1]) for (let k = 0; k < 3; k++){ const r = new THREE.Mesh(new THREE.BoxGeometry(11.6, .022, .035), rail); r.position.set(5.5, top + .011, zc + s * (2.12 + k * .05)); scene.add(r); }
}

init().catch(e => { console.error(e); const s = $('status'); s.hidden = false; s.textContent = 'Model se nepodařilo načíst: ' + e.message; });
