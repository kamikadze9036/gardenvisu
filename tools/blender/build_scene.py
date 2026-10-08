# Builds a photorealistic Blender scene from the Three.js model and renders the camera views with Cycles.
#
#   blender -b --factory-startup --python build_scene.py -- [--views bird,street] [--samples 128]
#           [--res 1600x900] [--cpu] [--save out/garden.blend] [--no-render]
#
# Inputs (next to this script):
#   data/scene.glb, data/scene.json   from tools/preview/export.mjs
#   assets/<polyhaven id>/{diff,rough}.jpg, assets/hdri/sky.hdr   CC0 from polyhaven.com
# Output: out/view-<key>.png
#
# Axes: glTF import turns the Three.js Y-up scene to Z-up. Three (x, y, z) -> Blender (x, -z, y),
# so Blender X is east, Y is north, Z is up. Plan data [x, z] from the JSON becomes (x, -z).
import bpy, bmesh, json, math, os, sys
import numpy as np
from mathutils import Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
D = json.load(open(os.path.join(HERE, 'data', 'scene.json')))

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
VIEWS = arg('--views', ','.join(v['key'] for v in D['VIEWS'])).split(',')
SAMPLES = int(arg('--samples', 128))
RES = [int(v) for v in arg('--res', '1600x900').split('x')]
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)

def b2(p): return (p[0], -p[1])                       # plan [x, z] -> Blender (x, y)
def b3(p): return Vector((p[0], -p[2], p[1]))          # Three (x, y, z) -> Blender
def poly(name): return np.array([b2(p) for p in D[name]])

def lin(hexcol):
    h = hexcol.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (1.0,)

def in_poly(x, y, pts):
    inside = np.zeros(x.shape, bool)
    for i in range(len(pts)):
        (xi, yi), (xj, yj) = pts[i], pts[i - 1]
        cross = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        inside ^= cross
    return inside

# ---------------------------------------------------------------- scene, import
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, 'data', 'scene.glb'))
for o in list(bpy.data.objects):
    if o.type == 'LIGHT' or (o.type == 'EMPTY' and not o.children):
        bpy.data.objects.remove(o)

proto_coll = bpy.data.collections.new('prototypes'); scene.collection.children.link(proto_coll)
plant_coll = bpy.data.collections.new('planting'); scene.collection.children.link(plant_coll)

# ---------------------------------------------------------------- materials
_images = {}
def image(path, color=True):
    if path not in _images:
        img = bpy.data.images.load(path)
        if not color: img.colorspace_settings.name = 'Non-Color'
        _images[path] = img
    return _images[path]

def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    return m, nt, bsdf

def link(nt, a, b): nt.links.new(a, b)

def mix_rgb(nt, blend, a, b, fac=1.0):
    n = nt.nodes.new('ShaderNodeMix'); n.data_type = 'RGBA'; n.blend_type = blend
    n.inputs['Factor'].default_value = fac
    ins = [s for s in n.inputs if s.type == 'RGBA']
    for sock, val in zip(ins, (a, b)):
        if isinstance(val, tuple): sock.default_value = val
        else: link(nt, val, sock)
    return [s for s in n.outputs if s.type == 'RGBA'][0]

def tex_mat(name, asset, size, tint=None, tint_fac=1.0, rough=1.0, bump=0.3, metallic=0.0, rot=0.0, sat=1.0):
    """Poly Haven texture, box-projected in object space at real-world size (m)."""
    m, nt, bsdf = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1 / size,) * 3
    mp.inputs['Rotation'].default_value = (0, 0, rot)
    link(nt, tc.outputs['Object'], mp.inputs['Vector'])
    def img(file, color):
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = image(os.path.join(ASSETS, asset, file), color)
        n.projection = 'BOX'; n.projection_blend = 0.25
        link(nt, mp.outputs['Vector'], n.inputs['Vector']); return n
    diff = img('diff.jpg', True); rgh = img('rough.jpg', False)
    col = diff.outputs['Color']
    if sat != 1.0:
        hs = nt.nodes.new('ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = sat
        link(nt, col, hs.inputs['Color']); col = hs.outputs['Color']
    if tint: col = mix_rgb(nt, 'MULTIPLY', col, lin(tint), tint_fac)
    link(nt, col, bsdf.inputs['Base Color'])
    rm = nt.nodes.new('ShaderNodeMath'); rm.operation = 'MULTIPLY'; rm.inputs[1].default_value = rough
    link(nt, rgh.outputs['Color'], rm.inputs[0]); link(nt, rm.outputs[0], bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = metallic
    if bump:
        bw = nt.nodes.new('ShaderNodeRGBToBW'); bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.02
        link(nt, diff.outputs['Color'], bw.inputs[0]); link(nt, bw.outputs[0], bp.inputs['Height'])
        link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def flat_mat(name, col, rough=0.5, metallic=0.0, **extra):
    m, nt, bsdf = new_mat(name)
    bsdf.inputs['Base Color'].default_value = lin(col)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    for k, v in extra.items(): bsdf.inputs[k].default_value = v
    return m

def standing_seam(name, col):
    """Anthracite sheet-metal roof: seams every 0,5 m along the object's X."""
    m, nt, bsdf = new_mat(name)
    bsdf.inputs['Base Color'].default_value = lin(col)
    bsdf.inputs['Roughness'].default_value = 0.42; bsdf.inputs['Metallic'].default_value = 0.6
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    link(nt, tc.outputs['Object'], sep.inputs[0])
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'PINGPONG'; m1.inputs[1].default_value = 0.25
    link(nt, sep.outputs['X'], m1.inputs[0])
    m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'LESS_THAN'; m2.inputs[1].default_value = 0.012
    link(nt, m1.outputs[0], m2.inputs[0])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6; bp.inputs['Distance'].default_value = 0.02
    link(nt, m2.outputs[0], bp.inputs['Height']); link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def leaf_mat(name, col, hue_var=0.04, val_var=0.25, transl=0.35, gradient=None):
    """Two-sided foliage: Principled mixed with a translucent lobe, per-object colour variation.
    gradient=(col_bottom, col_top, height) blends the colour along the object's local Z instead."""
    m, nt, bsdf = new_mat(name)
    out = nt.nodes['Material Output']
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    if gradient:
        tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        link(nt, tc.outputs['Object'], sep.inputs[0])
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Max'].default_value = gradient[2]
        link(nt, sep.outputs['Z'], mr.inputs['Value'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = lin(gradient[0]); ramp.color_ramp.elements[1].color = lin(gradient[1])
        ramp.color_ramp.elements[0].position = 0.15
        link(nt, mr.outputs['Result'], ramp.inputs['Fac']); base = ramp.outputs['Color']
    else:
        rgb = nt.nodes.new('ShaderNodeRGB'); rgb.outputs[0].default_value = lin(col); base = rgb.outputs[0]
    hs = nt.nodes.new('ShaderNodeHueSaturation')
    link(nt, base, hs.inputs['Color'])
    mh = nt.nodes.new('ShaderNodeMapRange'); mh.inputs['To Min'].default_value = 0.5 - hue_var; mh.inputs['To Max'].default_value = 0.5 + hue_var
    mv = nt.nodes.new('ShaderNodeMapRange'); mv.inputs['To Min'].default_value = 1 - val_var; mv.inputs['To Max'].default_value = 1 + val_var * 0.6
    link(nt, oi.outputs['Random'], mh.inputs['Value']); link(nt, oi.outputs['Random'], mv.inputs['Value'])
    link(nt, mh.outputs['Result'], hs.inputs['Hue']); link(nt, mv.outputs['Result'], hs.inputs['Value'])
    link(nt, hs.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.7; bsdf.inputs['Specular IOR Level'].default_value = 0.3
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); link(nt, hs.outputs['Color'], tr.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = transl
    link(nt, bsdf.outputs[0], mix.inputs[1]); link(nt, tr.outputs[0], mix.inputs[2])
    link(nt, mix.outputs[0], out.inputs['Surface'])
    return m

def water_mat():
    m, nt, bsdf = new_mat('water_pbr')
    bsdf.inputs['Base Color'].default_value = (1, 1, 1, 1)
    bsdf.inputs['Transmission Weight'].default_value = 1.0
    bsdf.inputs['Roughness'].default_value = 0.02; bsdf.inputs['IOR'].default_value = 1.333
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.04
    link(nt, nz.outputs['Fac'], bp.inputs['Height']); link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    vol = nt.nodes.new('ShaderNodeVolumeAbsorption'); vol.inputs['Color'].default_value = lin('#5fb8c4'); vol.inputs['Density'].default_value = 0.25
    link(nt, vol.outputs[0], nt.nodes['Material Output'].inputs['Volume'])
    return m

def wire_mesh_mat():
    """Welded mesh fence: 5 cm grid of thin wires, the rest transparent."""
    m, nt, bsdf = new_mat('wire_mesh')
    bsdf.inputs['Base Color'].default_value = lin('#2f3b33'); bsdf.inputs['Roughness'].default_value = 0.5
    bsdf.inputs['Metallic'].default_value = 0.4
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    link(nt, tc.outputs['Object'], sep.inputs[0])
    def wire(axis):
        a = nt.nodes.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; a.inputs[1].default_value = 20
        link(nt, sep.outputs[axis], a.inputs[0])
        f = nt.nodes.new('ShaderNodeMath'); f.operation = 'FRACT'; link(nt, a.outputs[0], f.inputs[0])
        l = nt.nodes.new('ShaderNodeMath'); l.operation = 'LESS_THAN'; l.inputs[1].default_value = 0.08
        link(nt, f.outputs[0], l.inputs[0]); return l.outputs[0]
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'
    link(nt, wire('X'), mx.inputs[0]); link(nt, wire('Z'), mx.inputs[1])
    tp = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader')
    link(nt, mx.outputs[0], mix.inputs['Fac']); link(nt, tp.outputs[0], mix.inputs[1]); link(nt, bsdf.outputs[0], mix.inputs[2])
    link(nt, mix.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m

GLASS = flat_mat('glass_pbr', '#0d1216', rough=0.02, **{'Specular IOR Level': 0.6})
MATS = {
    'wall':     tex_mat('plaster', 'painted_plaster_wall', 2.0, tint='#f6f4ee', rough=1.0, bump=0.08),
    'roof':     standing_seam('roof_pbr', '#2e3236'),
    'frame':    flat_mat('frame_pbr', '#383e42', rough=0.35, metallic=0.3),
    'glass':    GLASS,
    'door':     flat_mat('door_pbr', '#4a5056', rough=0.4, metallic=0.4),
    'groove':   flat_mat('groove_pbr', '#3d4247', rough=0.5, metallic=0.2),
    'sill':     flat_mat('sill_pbr', '#8f9396', rough=0.4, metallic=0.6),
    'pv':       flat_mat('pv_pbr', '#0b1424', rough=0.08, metallic=0.2),
    'lawn':     tex_mat('lawn_ground', 'sparse_grass', 2.0, tint='#9ab27a', rough=1.0, bump=0.2),
    'soil':     tex_mat('mulch', 'aerial_wood_snips', 3.0, tint='#8a6f58', rough=1.0, bump=0.5),
    'pave':     tex_mat('paving', 'rectangular_paving', 2.0, tint='#e2ddd2', rough=1.0, bump=0.25),
    'stone':    tex_mat('stone_paving', 'precast_stone_paving', 2.24, rough=1.0, bump=0.25),
    'deck':     tex_mat('decking', 'wood_floor_deck', 1.8, tint='#d8cbbb', rough=1.0, bump=0.2, sat=0.45),
    'edge':     tex_mat('coping', 'precast_stone_paving', 2.24, tint='#f0ece4', rough=1.0, bump=0.15),
    'water':    water_mat(),
    'cover':    flat_mat('polycarbonate', '#e8f4f7', rough=0.08, **{'Transmission Weight': 0.95}),
    'alu':      flat_mat('alu_pbr', '#c8ccd0', rough=0.3, metallic=1.0),
    'wood':     tex_mat('wood_light', 'wood_floor_deck', 1.8, tint='#d8b08a', rough=1.0, bump=0.15),
    'woodDark': tex_mat('wood_dark', 'wood_floor_deck', 1.8, tint='#7a5a3c', rough=1.0, bump=0.15),
    'block':    tex_mat('concrete_block', 'concrete_block_wall_02', 2.0, tint='#d4d6da', rough=1.0, bump=0.3),
    'cobble':   tex_mat('cobble', 'cobblestone_floor_03', 2.4, rough=1.0, bump=0.4),
    'field':    tex_mat('field', 'sparse_grass', 3.0, tint='#a8a070', rough=1.0, bump=0.3),
    'neigh':    tex_mat('neighbour_lawn', 'sparse_grass', 2.0, tint='#8fb070', rough=1.0, bump=0.3),
    'mesh':     wire_mesh_mat(),
    'post':     flat_mat('post_pbr', '#2f3b33', rough=0.4, metallic=0.5),
    'pot':      flat_mat('pot_pbr', '#3a3c3f', rough=0.55),
    'cabinet':  flat_mat('cabinet_pbr', '#ecebe6', rough=0.45),
    'membrane': flat_mat('membrane_pbr', '#3c3f42', rough=0.8),
    'veg':      leaf_mat('lettuce', '#6f9a3e'),
    'potplant': leaf_mat('pot_leaves', '#4f7a3a'),
}
BARK = tex_mat('bark', 'bark_brown_02', 1.0, rough=1.0, bump=0.8)
ROCK = tex_mat('rock', 'aerial_rocks_02', 4.0, tint='#c9c4ba', rough=1.0, bump=0.6)
TILE = flat_mat('pool_tile', '#a9cdd6', rough=0.25)

imported = [o for o in scene.objects if o.type == 'MESH']
for o in imported:
    for slot in o.material_slots:
        if slot.material:
            key = slot.material.name.split('.')[0]
            if key in MATS: slot.material = MATS[key]
    o.data.polygons.foreach_set('use_smooth', [False] * len(o.data.polygons))

def objs_with(key):
    return [o for o in imported if any(s.material == MATS[key] for s in o.material_slots)]

# ---------------------------------------------------------------- geometry helpers
def mesh_obj(name, verts, faces, mat_list, mat_idx=None, coll=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    for m in mat_list: me.materials.append(m)
    if mat_idx is not None: me.polygons.foreach_set('material_index', list(mat_idx))
    me.polygons.foreach_set('use_smooth', [smooth] * len(me.polygons))
    me.update()
    o = bpy.data.objects.new(name, me); (coll or scene.collection).objects.link(o)
    return o

def unit(v): return v / np.linalg.norm(v, axis=-1, keepdims=True)

def leaves(C, N, L, W, rng, cup=0.12):
    """Diamond-shaped leaf cards: centres C, facing roughly N, length L, width W (arrays or scalars)."""
    n = len(C); N = unit(N)
    T = unit(np.cross(N, rng.normal(size=(n, 3)))); S = np.cross(N, T)
    L = np.broadcast_to(L, (n,))[:, None]; W = np.broadcast_to(W, (n,))[:, None]
    v = np.stack([C - T * L / 2, C + S * W / 2 + N * L * cup, C + T * L / 2, C - S * W / 2 + N * L * cup], 1)
    return v.reshape(-1, 3), np.arange(n * 4).reshape(n, 4)

def discs(C, N, R, rng, k=8):
    n = len(C); N = unit(N)
    T = unit(np.cross(N, rng.normal(size=(n, 3)))); S = np.cross(N, T)
    a = np.linspace(0, 2 * np.pi, k, endpoint=False)
    R = np.broadcast_to(R, (n,))[:, None, None]
    v = C[:, None, :] + R * (np.cos(a)[None, :, None] * T[:, None, :] + np.sin(a)[None, :, None] * S[:, None, :])
    return v.reshape(-1, 3), np.arange(n * k).reshape(n, k)

def tube(p0, p1, r0, r1, sides=8):
    p0, p1 = np.array(p0, float), np.array(p1, float); d = unit(p1 - p0)
    a = unit(np.cross(d, [0.3, 0.2, 1.0] if abs(d[2]) < 0.9 else [1.0, 0, 0])); b = np.cross(d, a)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    ring = np.cos(ang)[:, None] * a + np.sin(ang)[:, None] * b
    v = np.vstack([p0 + ring * r0, p1 + ring * r1])
    f = [[i, (i + 1) % sides, sides + (i + 1) % sides, sides + i] for i in range(sides)]
    return v, np.array(f)

class Builder:
    """Accumulates verts/faces/material indices for one mesh."""
    def __init__(self): self.v, self.f, self.m, self.n = [], [], [], 0
    def add(self, v, f, mat=0):
        self.v.append(v); self.f += (np.asarray(f) + self.n).tolist(); self.m += [mat] * len(f); self.n += len(v)
    def obj(self, name, mats, coll=None):
        return mesh_obj(name, np.vstack(self.v), self.f, mats, self.m, coll)

def shell_points(rng, n, rmin, scale, center):
    d = unit(rng.normal(size=(n, 3)))
    r = rng.uniform(rmin, 1.0, (n, 1)) ** 0.5
    return center + d * r * scale, d

# ---------------------------------------------------------------- plant prototypes (unit size, origin at the ground)
LEAF = {
    'green':  leaf_mat('leaf_green', '#3f6a30'),
    'burg':   leaf_mat('leaf_burgundy', '#5a2a2a', hue_var=0.02),
    'aster':  leaf_mat('leaf_aster', '#41612f'),
    'flower': leaf_mat('aster_flower', '#8a5cc0', transl=0.2),
    'eye':    flat_mat('aster_eye', '#d9a521', rough=0.7),
    'grass':  leaf_mat('ornamental_grass', None, transl=0.3, val_var=0.2, gradient=('#6d7a3e', '#c8ad72', 1.3)),
}

def proto_shrub(seed, mat, sy):
    rng = np.random.default_rng(seed); b = Builder()
    C, d = shell_points(rng, 2600, 0.35, np.array([1, 1, sy]), np.array([0, 0, sy * 0.92]))
    keep = C[:, 2] > 0.04; C, d = C[keep], d[keep]
    N = d + np.array([0, 0, 0.6]) + rng.normal(scale=0.5, size=d.shape)
    b.add(*leaves(C, N, rng.uniform(0.11, 0.16, len(C)), rng.uniform(0.06, 0.09, len(C)), rng))
    return b.obj(f'shrub_{mat.name}_{seed}', [mat], proto_coll)

def proto_aster(seed):
    rng = np.random.default_rng(seed); b = Builder(); sy = 0.6
    C, d = shell_points(rng, 2000, 0.3, np.array([1, 1, sy]), np.array([0, 0, sy * 0.85]))
    keep = C[:, 2] > 0.03; C, d = C[keep], d[keep]
    b.add(*leaves(C, d + [0, 0, 0.8], 0.1, 0.045, rng), 0)
    F, fd = shell_points(rng, 900, 0.85, np.array([1, 1, sy]), np.array([0, 0, sy * 0.85]))
    keep = F[:, 2] > sy * 0.9; F, fd = F[keep], fd[keep]
    N = fd + [0, 0, 1.2] + rng.normal(scale=0.3, size=fd.shape)
    b.add(*discs(F, N, rng.uniform(0.035, 0.05, len(F)), rng, 10), 1)
    b.add(*discs(F + unit(N) * 0.004, N, 0.012, rng, 6), 2)
    return b.obj(f'aster_{seed}', [LEAF['aster'], LEAF['flower'], LEAF['eye']], proto_coll)

def proto_grass_clump(seed):
    """Ornamental grass: ~170 arching blades, height ~1.6 at unit radius."""
    rng = np.random.default_rng(seed); b = Builder(); K = 7
    for _ in range(170):
        az = rng.uniform(0, 2 * np.pi); tilt = rng.uniform(0.05, 0.75); L = rng.uniform(1.1, 1.75); w = rng.uniform(0.012, 0.022)
        out = np.array([np.cos(az), np.sin(az), 0]); side = np.array([-np.sin(az), np.cos(az), 0])
        base = out * rng.uniform(0, 0.13)
        s = np.linspace(0, 1, K + 1)[:, None]
        p = base + out * (np.sin(tilt) * s * L + 0.35 * tilt * (s * L) ** 2) + np.array([0, 0, 1]) * (np.cos(tilt) * s * L - 0.3 * tilt * (s * L) ** 2)
        half = (w * (1 - s ** 1.6) + 0.0015) / 2
        v = np.vstack([np.hstack([p - side * half, p + side * half]).reshape(-1, 3)])
        f = np.array([[2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2] for k in range(K)])
        b.add(v, f)
    return b.obj(f'grass_{seed}', [LEAF['grass']], proto_coll)

def proto_rock(seed):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    off = Vector((seed * 7.3, seed * 1.7, seed * 3.1))
    for v in bm.verts:
        v.co *= 1 + 0.28 * noise.noise(v.co * 1.3 + off) + 0.08 * noise.noise(v.co * 4 + off)
        v.co.x *= 1.0; v.co.y *= 0.8; v.co.z = v.co.z * 0.55 + 0.25
    me = bpy.data.meshes.new(f'rock_{seed}'); bm.to_mesh(me); bm.free()
    me.materials.append(ROCK); me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    o = bpy.data.objects.new(me.name, me); proto_coll.objects.link(o); return o

PROTOS = {
    'green':  [proto_shrub(s, LEAF['green'], 0.85) for s in (1, 2, 3)],
    'burg':   [proto_shrub(s, LEAF['burg'], 1.0) for s in (4, 5)],
    'purple': [proto_aster(s) for s in (6, 7, 8)],
    'grass':  [proto_grass_clump(s) for s in (9, 10, 11)],
    'rock':   [proto_rock(s) for s in (12, 13, 14)],
}
for lst in PROTOS.values():
    for o in lst: o.hide_render = True; o.hide_viewport = True

def place(proto, x, y, z, r, rot):
    o = bpy.data.objects.new(proto.name + '_i', proto.data); plant_coll.objects.link(o)
    o.location = (x, y, z); o.rotation_euler = (0, 0, rot); o.scale = (r, r, r); return o

for p in D['PLANTS']:
    variants = PROTOS[p['type']]
    x, y = b2((p['x'], p['z']))
    place(variants[int(p['c'] * len(variants)) % len(variants)], x, y, 0.0, p['r'], p['rot'])

# Lettuce in the raised planters and plants in the entrance pots: swap the spheres for shrubs
for key, kind in (('veg', 'green'), ('potplant', 'green')):
    for i, o in enumerate(objs_with(key)):
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = Vector([min(c[k] for c in bb) for k in range(3)]); hi = Vector([max(c[k] for c in bb) for k in range(3)])
        proto = PROTOS['purple' if key == 'potplant' and i == 1 else kind][i % 3 if kind != 'burg' else 0]
        place(proto, (lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + (0.0 if key == 'veg' else 0.12), (hi.x - lo.x) / 2 * 1.1, i)
        o.hide_render = True; o.hide_viewport = True

# ---------------------------------------------------------------- trees
def deciduous(t, seed):
    rng = np.random.default_rng(seed); b = Builder()
    x, y = b2((t['x'], t['z'])); h, r = t['h'], t['r']
    top = h * 0.58; cz = h - r * 1.05
    b.add(*tube([x, y, 0], [x, y, top], 0.11 * h / 4, 0.06 * h / 4, 10), 0)
    tips = []
    for i in range(9):
        az = i / 9 * 2 * np.pi + rng.uniform(-0.3, 0.3)
        z0 = top - rng.uniform(0, 0.4)
        tip = np.array([x + np.cos(az) * r * 0.75, y + np.sin(az) * r * 0.75, cz + rng.uniform(-0.3, 0.7) * r])
        b.add(*tube([x, y, z0], tip, 0.035, 0.012, 6), 0); tips.append(tip)
        for _ in range(3):
            mid = np.array([x, y, z0]) + (tip - [x, y, z0]) * rng.uniform(0.45, 0.8)
            t2 = mid + unit(rng.normal(size=3) + [0, 0, 0.6]) * r * 0.45
            b.add(*tube(mid, t2, 0.012, 0.005, 5), 0)
    C, d = shell_points(rng, int(9000 * r * r), 0.45, np.array([r, r, r * 1.15]), np.array([x, y, cz]))
    lobes = np.array([noise.noise(Vector(v) * 1.8 + Vector((seed, 0, 0))) for v in d])
    C = np.array([x, y, cz]) + (C - [x, y, cz]) * (1 + 0.22 * lobes)[:, None]
    N = d + [0, 0, 0.5] + rng.normal(scale=0.6, size=d.shape)
    b.add(*leaves(C, N, rng.uniform(0.08, 0.12, len(C)), rng.uniform(0.045, 0.065, len(C)), rng), 1)
    return b.obj(f'tree_{seed}', [BARK, leaf_mat(f'tree_leaf_{seed}', t['c'])], plant_coll)

def conifer(t, seed):
    rng = np.random.default_rng(seed); b = Builder()
    x, y = b2((t['x'], t['z'])); h, r = t['h'], t['r']
    b.add(*tube([x, y, 0], [x, y, h], 0.09, 0.015, 8), 0)
    C, N = [], []
    z = h * 0.12
    while z < h * 0.97:
        frac = (z - h * 0.12) / (h * 0.85)
        for k in range(6):
            az = rng.uniform(0, 2 * np.pi); Lb = r * (1 - frac) * rng.uniform(0.85, 1.1) + 0.1
            d = np.array([np.cos(az), np.sin(az), -0.35])
            p0 = np.array([x, y, z]); p1 = p0 + unit(d) * Lb + [0, 0, -0.12 * Lb]
            b.add(*tube(p0, p1, 0.016, 0.005, 5), 0)
            for s in np.arange(0.12, 1.0, 0.045):
                c = p0 + (p1 - p0) * s
                for _ in range(4):
                    C.append(c + rng.normal(scale=0.045, size=3)); N.append(np.array([0, 0, 1.0]) + rng.normal(scale=0.5, size=3))
        z += rng.uniform(0.1, 0.14)
    C, N = np.array(C), np.array(N)
    b.add(*leaves(C, N, rng.uniform(0.08, 0.11, len(C)), 0.035, rng, cup=0.05), 1)
    return b.obj(f'conifer_{seed}', [BARK, leaf_mat(f'needles_{seed}', t['c'], val_var=0.15, transl=0.15)], plant_coll)

for i, t in enumerate(D['TREES']):
    (conifer if t['kind'] == 'conifer' else deciduous)(t, 100 + i)

# ---------------------------------------------------------------- lawn: instanced grass clumps
def grass_patch(seed):
    rng = np.random.default_rng(seed); b = Builder(); K = 3
    for _ in range(45):
        c = np.append(rng.uniform(-0.06, 0.06, 2), 0); az = rng.uniform(0, 2 * np.pi)
        lean = np.array([np.cos(az), np.sin(az), 0]); side = np.array([-np.sin(az), np.cos(az), 0])
        hgt = rng.uniform(0.03, 0.065); bend = rng.uniform(0.15, 0.5); w = rng.uniform(0.0025, 0.004)
        s = np.linspace(0, 1, K + 1)[:, None]
        p = c + lean * bend * hgt * s ** 2 + np.array([0, 0, hgt]) * s
        half = w * (1 - s * 0.9) / 2
        v = np.hstack([p - side * half, p + side * half]).reshape(-1, 3)
        b.add(v, np.array([[2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2] for k in range(K)]))
    return b.obj('lawn_patch', [lawn_blade_mat()], proto_coll)

def lawn_blade_mat():
    m = leaf_mat('lawn_blade', '#4f7a2e', hue_var=0.03, val_var=0.3, transl=0.3)
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']; hs = nt.nodes['Hue/Saturation/Value']
    # Patchy lawn: world-space noise between a deep and a dry green
    tc = nt.nodes.new('ShaderNodeNewGeometry'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.35
    link(nt, tc.outputs['Position'], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = lin('#3e6b26'); ramp.color_ramp.elements[1].color = lin('#7a9442')
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.7
    link(nt, nz.outputs['Fac'], ramp.inputs['Fac']); link(nt, ramp.outputs['Color'], hs.inputs['Color'])
    return m

LAWN_P = poly('LAWN')
blocked = [poly(k) for k in ('DRIVE', 'RAMP', 'PATIO', 'DECK_EDGE', 'HOUSE', 'GARAGE')]
rng = np.random.default_rng(7)
xmin, ymin = LAWN_P.min(0); xmax, ymax = LAWN_P.max(0)
DENSITY = 110      # patches per m²
n = int((xmax - xmin) * (ymax - ymin) * DENSITY)
X = rng.uniform(xmin, xmax, n); Y = rng.uniform(ymin, ymax, n)
ok = in_poly(X, Y, LAWN_P)
for bp in blocked: ok &= ~in_poly(X, Y, bp)
X, Y = X[ok], Y[ok]
pts = mesh_obj('lawn_points', np.c_[X, Y, np.full(len(X), 0.012)], [], [])
patch = grass_patch(21); patch.hide_render = True; patch.hide_viewport = True

ng = bpy.data.node_groups.new('scatter', 'GeometryNodeTree')
ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi = ng.nodes.new('NodeGroupInput'); go = ng.nodes.new('NodeGroupOutput')
iop = ng.nodes.new('GeometryNodeInstanceOnPoints'); oi = ng.nodes.new('GeometryNodeObjectInfo')
oi.inputs['Object'].default_value = patch
rr = ng.nodes.new('FunctionNodeRandomValue'); rr.data_type = 'FLOAT_VECTOR'
rr.inputs['Max'].default_value = (0, 0, 2 * math.pi); rr.inputs['Min'].default_value = (0, 0, 0)
rs = ng.nodes.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
[s for s in rs.inputs if s.name == 'Min' and s.type == 'VALUE'][0].default_value = 0.7
[s for s in rs.inputs if s.name == 'Max' and s.type == 'VALUE'][0].default_value = 1.35
ng.links.new(gi.outputs[0], iop.inputs['Points']); ng.links.new(oi.outputs['Geometry'], iop.inputs['Instance'])
ng.links.new(rr.outputs['Value'], iop.inputs['Rotation'])
ng.links.new([s for s in rs.outputs if s.type == 'VALUE'][0], iop.inputs['Scale'])
ng.links.new(iop.outputs[0], go.inputs[0])
pts.modifiers.new('grass', 'NODES').node_group = ng
print(f'lawn: {len(X)} grass patches')

# ---------------------------------------------------------------- pool basin (Three.js only has a flat water plane)
px0, py0 = poly('POOL').min(0); px1, py1 = poly('POOL').max(0)
POOL_FLOOR, WATER = -0.85, 0.06
cutter = mesh_obj('pool_cut', [], [], [])
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(cutter.data); bm.free()
cutter.location = ((px0 + px1) / 2, (py0 + py1) / 2, (POOL_FLOOR + 0.13) / 2)
cutter.scale = (px1 - px0, py1 - py0, 0.13 - POOL_FLOOR)
cutter.hide_render = True; cutter.hide_viewport = True
for o in objs_with('soil') + objs_with('edge'):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]   # local axes are rotated, so measure in world space
    if max(c.x for c in bb) - min(c.x for c in bb) > 5 and max(c.y for c in bb) - min(c.y for c in bb) > 5:
        bm = bmesh.new(); bm.from_mesh(o.data)          # Three.js extrusions have split vertices; weld so the boolean sees a solid
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4); bm.to_mesh(o.data); bm.free()
        mod = o.modifiers.new('pool', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = cutter
c = [(px0, py0), (px1, py0), (px1, py1), (px0, py1)]
v = [(x, y, POOL_FLOOR) for x, y in c] + [(x, y, 0.15) for x, y in c]
mesh_obj('pool_basin', v, [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], [TILE], smooth=False)
# Water as a closed volume so the absorption tints it; the flat Three.js plane is hidden
wv = mesh_obj('pool_water', [(x, y, POOL_FLOOR + 0.01) for x, y in c] + [(x, y, WATER) for x, y in c],
              [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], [MATS['water']], smooth=False)
for o in objs_with('water'):
    if o != wv: o.hide_render = True

# ---------------------------------------------------------------- world: HDRI sky, rotated so the sun matches the Three.js sun
world = bpy.data.worlds.new('sky'); scene.world = world; world.use_nodes = True
wn = world.node_tree; bg = wn.nodes['Background']
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(ASSETS, 'hdri', 'sky.hdr'))
img = env.image; w, hh = img.size
px = np.empty(w * hh * 4, np.float32); img.pixels.foreach_get(px); px = px.reshape(hh, w, 4)
lum = px[..., 0] * 0.2126 + px[..., 1] * 0.7152 + px[..., 2] * 0.0722
row, col = np.unravel_index(np.argmax(lum), lum.shape); del px, lum
u, vv = (col + 0.5) / w, (row + 0.5) / hh
phi, el = (u - 0.5) * 2 * math.pi, (vv - 0.5) * math.pi
az_h = -phi   # Blender equirect: u = 0.5 - atan2(y, x) / 2π
sun_dir = b3([-14, 34, 38]) - b3([11.6, 0, 13.2])
az_w = math.atan2(sun_dir.y, sun_dir.x)
tc = wn.nodes.new('ShaderNodeTexCoord'); mp = wn.nodes.new('ShaderNodeMapping')
mp.inputs['Rotation'].default_value = (0, 0, az_h - az_w)
wn.links.new(tc.outputs['Generated'], mp.inputs['Vector']); wn.links.new(mp.outputs['Vector'], env.inputs['Vector'])
wn.links.new(env.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.0
print(f'HDRI sun: elevation {math.degrees(el):.1f}°, rotated by {math.degrees(az_h - az_w):.1f}°')

# ---------------------------------------------------------------- render settings
scene.render.engine = 'CYCLES'
cy = scene.cycles
if '--cpu' not in argv:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = kind; prefs.get_devices()
            for d in prefs.devices: d.use = d.type == kind
            if any(d.use for d in prefs.devices): cy.device = 'GPU'; break
        except TypeError:
            continue
cy.samples = SAMPLES; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.02
cy.use_denoising = True
cy.sample_clamp_indirect = 8
cy.max_bounces = 8; cy.transparent_max_bounces = 16
scene.render.use_persistent_data = True
scene.render.resolution_x, scene.render.resolution_y = RES; scene.render.resolution_percentage = 100
try: scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
except TypeError: pass
scene.render.image_settings.file_format = 'PNG'

# ---------------------------------------------------------------- cameras
cams = {}
for v in D['VIEWS']:
    cd = bpy.data.cameras.new(v['key']); cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(45)
    cd.clip_start = 0.05; cd.clip_end = 600
    co = bpy.data.objects.new('cam_' + v['key'], cd); scene.collection.objects.link(co)
    pos, tgt = b3(v['pos']), b3(v['tgt'])
    co.location = pos; co.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()
    cams[v['key']] = co
scene.camera = cams[VIEWS[0]]

save = arg('--save')
if save: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, save) if not os.path.isabs(save) else save)

if '--no-render' not in argv:
    for key in VIEWS:
        scene.camera = cams[key]
        scene.render.filepath = os.path.join(OUT, f'view-{key}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', scene.render.filepath)
