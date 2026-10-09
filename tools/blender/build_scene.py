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
import bpy, bmesh, glob, json, math, os, sys
import numpy as np
from mathutils import Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
D = json.load(open(os.path.join(HERE, 'data', 'scene.json')))

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
# Extra eye-level views of the design (Three.js coordinates, like D['VIEWS'])
D['VIEWS'] += [
    {'key': 'west-bed',   'pos': [-1.2, 1.65, 19.0], 'tgt': [-3.6, 0.5, 4.0]},     # along the new bed by the west fence
    {'key': 'north-path', 'pos': [-3.0, 1.65, -1.85], 'tgt': [9.0, 0.2, -1.95]},   # along the stepping stones behind the house
    {'key': 'yard',       'pos': [14.4, 1.65, -1.0], 'tgt': [21.0, 0.3, 1.4]},     # the yard behind the garage, fire bowl, play house     # along the stepping stones behind the house
    {'key': 'pool',       'pos': [9.6, 1.6, 18.8],   'tgt': [3.0, 0.3, 13.6]},     # the deck and pool enclosure from the lawn
]
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

def tex_mat(name, asset, size, tint=None, tint_fac=1.0, rough=1.0, bump=0.3, metallic=0.0, rot=0.0, sat=1.0, detile=False):
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
    if detile:   # blend in a second, rotated and rescaled sample through large-scale noise to hide the repeat
        mp2 = nt.nodes.new('ShaderNodeMapping'); mp2.inputs['Scale'].default_value = (0.57 / size,) * 3
        mp2.inputs['Rotation'].default_value = (0, 0, rot + 0.9); mp2.inputs['Location'].default_value = (0.31, 0.77, 0)
        link(nt, tc.outputs['Object'], mp2.inputs['Vector'])
        d2 = nt.nodes.new('ShaderNodeTexImage'); d2.image = diff.image; d2.projection = 'BOX'; d2.projection_blend = 0.25
        link(nt, mp2.outputs['Vector'], d2.inputs['Vector'])
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.08 * 3 / size * 3; nz.inputs['Detail'].default_value = 3
        link(nt, tc.outputs['Object'], nz.inputs['Vector'])
        ramp = nt.nodes.new('ShaderNodeMapRange'); ramp.inputs['From Min'].default_value = 0.4; ramp.inputs['From Max'].default_value = 0.6
        link(nt, nz.outputs['Fac'], ramp.inputs['Value'])
        col = mix_rgb(nt, 'MIX', col, d2.outputs['Color'])
        link(nt, ramp.outputs['Result'], col.node.inputs['Factor'])
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

def block_mat():
    """Dark split-face concrete blocks 0,4 × 0,2 m with recessed joints, laid along the wall's local X."""
    m, nt, bsdf = new_mat('split_block')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    p = nt.nodes.new('ShaderNodeSeparateXYZ'); link(nt, tc.outputs['Object'], p.inputs[0])
    n = nt.nodes.new('ShaderNodeSeparateXYZ'); link(nt, tc.outputs['Normal'], n.inputs[0])
    def op(kind, a, b=None):
        node = nt.nodes.new('ShaderNodeMath'); node.operation = kind
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): node.inputs[i].default_value = v
            else: link(nt, v, node.inputs[i])
        return node.outputs[0]
    # u runs along whichever horizontal axis the face lies in
    u = op('ADD', op('MULTIPLY', p.outputs['X'], op('ABSOLUTE', n.outputs['Y'])), op('MULTIPLY', p.outputs['Y'], op('ABSOLUTE', n.outputs['X'])))
    u = op('ADD', u, op('MULTIPLY', p.outputs['X'], op('ABSOLUTE', n.outputs['Z'])))
    v = op('ADD', op('MULTIPLY', p.outputs['Z'], op('SUBTRACT', 1.0, op('ABSOLUTE', n.outputs['Z']))), op('MULTIPLY', p.outputs['Y'], op('ABSOLUTE', n.outputs['Z'])))
    cmb = nt.nodes.new('ShaderNodeCombineXYZ'); link(nt, u, cmb.inputs['X']); link(nt, v, cmb.inputs['Y'])
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.inputs['Scale'].default_value = 1.0; br.inputs['Brick Width'].default_value = 0.4; br.inputs['Row Height'].default_value = 0.2
    br.inputs['Mortar Size'].default_value = 0.007; br.inputs['Mortar Smooth'].default_value = 0.3
    br.inputs['Color1'].default_value = lin('#55585c'); br.inputs['Color2'].default_value = lin('#4a4d51'); br.inputs['Mortar'].default_value = lin('#3f4144')
    link(nt, cmb.outputs[0], br.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 18; nz.inputs['Detail'].default_value = 8; nz.inputs['Roughness'].default_value = 0.65
    link(nt, tc.outputs['Object'], nz.inputs['Vector'])
    shade = nt.nodes.new('ShaderNodeMapRange'); shade.inputs['To Min'].default_value = 0.75; shade.inputs['To Max'].default_value = 1.2
    link(nt, nz.outputs['Fac'], shade.inputs['Value'])
    colr = mix_rgb(nt, 'MULTIPLY', br.outputs['Color'], (1, 1, 1, 1), 1.0)
    link(nt, shade.outputs['Result'], [s for s in colr.node.inputs if s.type == 'RGBA'][1])
    link(nt, colr, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    h = op('ADD', op('MULTIPLY', nz.outputs['Fac'], 0.6), op('SUBTRACT', 1.0, br.outputs['Fac']))
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.7; bp.inputs['Distance'].default_value = 0.01
    link(nt, h, bp.inputs['Height']); link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def clear_panel_mat():
    """Polycarbonate panels of the pool enclosure: see-through but slightly milky, with a soft reflection."""
    m, nt, bsdf = new_mat('polycarbonate_clear')
    out = nt.nodes['Material Output']
    tp = nt.nodes.new('ShaderNodeBsdfTransparent'); tp.inputs['Color'].default_value = lin('#e9f1ef')
    df = nt.nodes.new('ShaderNodeBsdfTranslucent'); df.inputs['Color'].default_value = lin('#dfe8e6')
    milk = nt.nodes.new('ShaderNodeMixShader'); milk.inputs['Fac'].default_value = 0.22
    link(nt, tp.outputs[0], milk.inputs[1]); link(nt, df.outputs[0], milk.inputs[2])
    gl = nt.nodes.new('ShaderNodeBsdfGlossy'); gl.inputs['Roughness'].default_value = 0.08
    fr = nt.nodes.new('ShaderNodeFresnel'); fr.inputs['IOR'].default_value = 1.58
    k = nt.nodes.new('ShaderNodeMath'); k.operation = 'MULTIPLY'; k.inputs[1].default_value = 0.3
    link(nt, fr.outputs[0], k.inputs[0])
    mix = nt.nodes.new('ShaderNodeMixShader')
    link(nt, k.outputs[0], mix.inputs['Fac']); link(nt, milk.outputs[0], mix.inputs[1]); link(nt, gl.outputs[0], mix.inputs[2])
    link(nt, mix.outputs[0], out.inputs['Surface'])
    return m

def far_lawn_mat(name):
    """Mown lawn seen from a distance: two greens mixed by noise, with a fine bump."""
    m, nt, bsdf = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.15; n1.inputs['Detail'].default_value = 6
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 60; n2.inputs['Detail'].default_value = 2
    link(nt, tc.outputs['Object'], n1.inputs['Vector']); link(nt, tc.outputs['Object'], n2.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = lin('#46702c'); ramp.color_ramp.elements[1].color = lin('#7f9a46')
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.7
    link(nt, n1.outputs['Fac'], ramp.inputs['Fac']); link(nt, ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.4
    link(nt, n2.outputs['Fac'], bp.inputs['Height']); link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def roof_tiles(name):
    """Flat anthracite concrete roof tiles, about 0,30 × 0,33 m, laid in staggered courses (photos 02, 07)."""
    m, nt, bsdf = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); link(nt, tc.outputs['Object'], sep.inputs[0])
    cmb = nt.nodes.new('ShaderNodeCombineXYZ'); link(nt, sep.outputs['X'], cmb.inputs['X']); link(nt, sep.outputs['Y'], cmb.inputs['Y'])
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.inputs['Scale'].default_value = 1.0; br.inputs['Brick Width'].default_value = 0.30; br.inputs['Row Height'].default_value = 0.33
    br.inputs['Mortar Size'].default_value = 0.004; br.inputs['Mortar Smooth'].default_value = 0.2
    br.inputs['Color1'].default_value = lin('#2b2d30'); br.inputs['Color2'].default_value = lin('#25272a'); br.inputs['Mortar'].default_value = lin('#121314')
    link(nt, cmb.outputs[0], br.inputs['Vector'])
    link(nt, br.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.75; bsdf.inputs['Specular IOR Level'].default_value = 0.25
    row = nt.nodes.new('ShaderNodeMath'); row.operation = 'WRAP'; row.inputs[1].default_value = 0.0; row.inputs[2].default_value = 0.33
    link(nt, sep.outputs['Y'], row.inputs[0])
    h = nt.nodes.new('ShaderNodeMath'); h.operation = 'SUBTRACT'; link(nt, row.outputs[0], h.inputs[0]); link(nt, br.outputs['Fac'], h.inputs[1])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.5; bp.inputs['Distance'].default_value = 0.05
    link(nt, h.outputs[0], bp.inputs['Height']); link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def street_pavers(name):
    """Interlocking street pavers, about 0,20 × 0,16 m, randomly yellow-beige and grey (photo 07)."""
    m, nt, bsdf = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.inputs['Scale'].default_value = 1.0; br.inputs['Brick Width'].default_value = 0.2; br.inputs['Row Height'].default_value = 0.16
    br.inputs['Mortar Size'].default_value = 0.006; br.inputs['Mortar Smooth'].default_value = 0.5; br.inputs['Bias'].default_value = 0.0
    br.inputs['Color1'].default_value = lin('#c9b27a'); br.inputs['Color2'].default_value = lin('#9b9a96'); br.inputs['Mortar'].default_value = lin('#6d6a63')
    link(nt, tc.outputs['Object'], br.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 30; nz.inputs['Detail'].default_value = 6
    link(nt, tc.outputs['Object'], nz.inputs['Vector'])
    sh = nt.nodes.new('ShaderNodeMapRange'); sh.inputs['To Min'].default_value = 0.8; sh.inputs['To Max'].default_value = 1.1
    link(nt, nz.outputs['Fac'], sh.inputs['Value'])
    col = mix_rgb(nt, 'MULTIPLY', br.outputs['Color'], (1, 1, 1, 1))
    link(nt, sh.outputs['Result'], [s for s in col.node.inputs if s.type == 'RGBA'][1])
    link(nt, col, bsdf.inputs['Base Color']); bsdf.inputs['Roughness'].default_value = 0.85
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6; bp.inputs['Distance'].default_value = 0.01
    link(nt, br.outputs['Fac'], bp.inputs['Height']); link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def asset_size(asset, default):
    """Real-world texture size in metres from Poly Haven's info.json, if it was downloaded."""
    try: return json.load(open(os.path.join(ASSETS, asset, 'info.json')))['dimensions'][0] / 1000
    except (OSError, KeyError, ValueError): return default

def has(asset): return os.path.exists(os.path.join(ASSETS, asset, 'diff.jpg'))

GLASS = flat_mat('glass_pbr', '#0d1216', rough=0.02, **{'Specular IOR Level': 0.6})
MATS = {
    'wall':     tex_mat('plaster', 'painted_plaster_wall', 2.0, tint='#f6f4ee', rough=1.0, bump=0.08),
    'roof':     roof_tiles('roof_tiles'),
    'frame':    flat_mat('frame_pbr', '#383e42', rough=0.35, metallic=0.3),
    'glass':    GLASS,
    'door':     flat_mat('door_pbr', '#4a5056', rough=0.4, metallic=0.4),
    'groove':   flat_mat('groove_pbr', '#3d4247', rough=0.5, metallic=0.2),
    'sill':     flat_mat('sill_pbr', '#8f9396', rough=0.4, metallic=0.6),
    'pv':       flat_mat('pv_pbr', '#0b1424', rough=0.08, metallic=0.2),
    'lawn':     tex_mat('lawn_ground', 'sparse_grass', 2.0, tint='#7fa860', rough=1.0, bump=0.2, sat=1.3, detile=True),
    'soil':     tex_mat('mulch', 'aerial_wood_snips', 3.0, tint='#8a6f58', rough=1.0, bump=0.5, detile=True),
    'pave':     tex_mat('paving', 'rectangular_paving', 2.0, tint='#e2ddd2', rough=1.0, bump=0.25),
    'stone':    tex_mat('stone_paving', 'precast_stone_paving', 2.24, rough=1.0, bump=0.25),
    'deck':     tex_mat('decking_wpc_brown', 'wood_floor_deck', 1.8, tint='#b48170', rough=0.8, bump=0.15, sat=0.4),
    'edge':     tex_mat('decking_wpc_border', 'wood_floor_deck', 1.8, tint='#b48170', rough=0.8, bump=0.15, sat=0.4, rot=math.pi / 2),
    'water':    water_mat(),
    'cover':    flat_mat('polycarbonate', '#e8f4f7', rough=0.08, **{'Transmission Weight': 0.95}),
    'alu':      flat_mat('alu_pbr', '#c8ccd0', rough=0.3, metallic=1.0),
    'wood':     (tex_mat('planter_wood', 'weathered_planks', asset_size('weathered_planks', 2.0), tint='#d9d6cf', rough=1.0, bump=0.3, sat=0.3)
                 if has('weathered_planks') else tex_mat('wood_light', 'wood_floor_deck', 1.8, tint='#d8b08a', rough=1.0, bump=0.15)),
    'woodDark': tex_mat('wood_dark', 'wood_floor_deck', 1.8, tint='#7a5a3c', rough=1.0, bump=0.15),
    'slat':     tex_mat('fence_slat', 'wood_floor_deck', 1.8, tint='#f2c792', rough=0.9, bump=0.15, sat=0.7),
    'galv':     flat_mat('galvanised', '#a9adb0', rough=0.35, metallic=0.85),
    'block':    block_mat(),
    'cobble':   street_pavers('street_pavers'),
    'field':    tex_mat('field', 'leafy_grass', 4.0, tint='#b5b98a', rough=1.0, bump=0.3, sat=0.7, detile=True),
    'neigh':    far_lawn_mat('neighbour_lawn'),
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

def proto_shrub(seed, mat, sy, n=3200, leaf=1.0):
    """Dense leafy shrub with an irregular, lobed outline (unit radius, height ~1,9·sy)."""
    rng = np.random.default_rng(seed); b = Builder()
    C, d = shell_points(rng, n, 0.45, np.array([1, 1, sy]), np.array([0, 0, sy * 0.92]))
    lobes = np.array([noise.noise(Vector(v) * 2.2 + Vector((seed * 3.1, 0, 0))) for v in d])
    C = np.array([0, 0, sy * 0.92]) + (C - [0, 0, sy * 0.92]) * (1 + 0.25 * lobes)[:, None]
    keep = C[:, 2] > 0.04; C, d = C[keep], d[keep]
    N = d + np.array([0, 0, 0.6]) + rng.normal(scale=0.5, size=d.shape)
    b.add(*leaves(C, N, rng.uniform(0.1, 0.15, len(C)) * leaf, rng.uniform(0.055, 0.085, len(C)) * leaf, rng))
    for _ in range(14):   # a few stems showing through at the base
        top = np.append(rng.normal(scale=0.35, size=2), rng.uniform(0.3, 0.9) * sy)
        b.add(*tube([0, 0, 0], top, 0.02, 0.006, 5))
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

def blade_clump(b, rng, n, h, rad, w, tilt, droop=0.35, K=7, mat=0):
    """Arching blades from a tuft of radius rad; h is the blade length, w = (min, max) width."""
    for _ in range(n):
        az = rng.uniform(0, 2 * np.pi); t = rng.uniform(0.03, tilt); L = h * rng.uniform(0.7, 1.05); wd = rng.uniform(*w)
        out = np.array([np.cos(az), np.sin(az), 0]); side = np.array([-np.sin(az), np.cos(az), 0])
        s = np.linspace(0, 1, K + 1)[:, None]
        p = out * rng.uniform(0, rad) + out * (np.sin(t) * s * L + droop * t * s ** 2 * L) + np.array([0, 0, 1.0]) * (np.cos(t) * s * L - droop * 0.85 * t * s ** 2 * L)
        half = (wd * (1 - s ** 1.6) + wd * 0.08) / 2
        b.add(np.hstack([p - side * half, p + side * half]).reshape(-1, 3), np.array([[2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2] for k in range(K)]), mat)

def proto_grass_clump(seed):
    """Ornamental grass for the generated beds: unit radius, height ~1,6."""
    rng = np.random.default_rng(seed); b = Builder()
    blade_clump(b, rng, 170, 1.6, 0.13, (0.012, 0.022), 0.75)
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

# ---------------------------------------------------------------- scanned models from Poly Haven (optional)
models_coll = bpy.data.collections.new('models'); scene.collection.children.link(models_coll)

def load_model(mid):
    """Imports assets/models/<mid>/*.gltf into its own collection, origin moved to the base centre."""
    files = glob.glob(os.path.join(ASSETS, 'models', mid, '*.gltf'))
    if not files: return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=files[0])
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == 'MESH' for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    coll = bpy.data.collections.new(mid); models_coll.children.link(coll)
    for o in new:
        for c in list(o.users_collection): c.objects.unlink(o)
        coll.objects.link(o)
    coll.instance_offset = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
    return {'coll': coll, 'h': hi.z - lo.z, 'r': max(hi.x - lo.x, hi.y - lo.y) / 2}

def recolour(model, name, hue=0.5, sat=1.0, val=1.0, keys=('leaf', 'leaves')):
    """Copy of a model whose foliage materials are shifted in hue (e.g. autumn colours)."""
    coll = bpy.data.collections.new(name); models_coll.children.link(coll); copies = {}
    for o in model['coll'].objects:
        c = o.copy()
        if o.data: c.data = o.data.copy()
        coll.objects.link(c); copies[o] = c
    for o, c in copies.items():
        if o.parent in copies: c.parent = copies[o.parent]
        if c.type != 'MESH': continue
        for slot in c.material_slots:
            if not slot.material or not any(k in slot.material.name.lower() for k in keys): continue
            m = slot.material.copy(); slot.material = m; nt = m.node_tree
            bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'); sock = bsdf.inputs['Base Color']
            hs = nt.nodes.new('ShaderNodeHueSaturation')
            hs.inputs['Hue'].default_value = hue; hs.inputs['Saturation'].default_value = sat; hs.inputs['Value'].default_value = val
            if sock.links: nt.links.new(sock.links[0].from_socket, hs.inputs['Color'])
            else: hs.inputs['Color'].default_value = sock.default_value
            nt.links.new(hs.outputs[0], sock)
    coll.instance_offset = model['coll'].instance_offset
    return dict(model, coll=coll)

def instance(model, x, y, z=0.0, height=None, radius=None, rot=0.0):
    s = height / model['h'] if height else radius / model['r']
    e = bpy.data.objects.new(model['coll'].name + '_i', None)
    e.instance_type = 'COLLECTION'; e.instance_collection = model['coll']
    e.location = (x, y, z); e.rotation_euler = (0, 0, rot); e.scale = (s, s, s)
    plant_coll.objects.link(e); return e

TREE_M = load_model('tree_small_02')
ROCKS_M = [m for m in (load_model('boulder_01'), load_model('rock_07')) if m]

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
    x, y = b2((p['x'], p['z']))
    if p['type'] == 'rock' and ROCKS_M:
        instance(ROCKS_M[int(p['c'] * len(ROCKS_M)) % len(ROCKS_M)], x, y, -0.04, radius=p['r'] * 0.8, rot=p['rot'])
        continue
    variants = PROTOS[p['type']]
    place(variants[int(p['c'] * len(variants)) % len(variants)], x, y, 0.0, p['r'], p['rot'])

# Plants in the entrance pots: swap the spheres for shrubs and asters
for i, o in enumerate(objs_with('potplant')):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector([min(c[k] for c in bb) for k in range(3)]); hi = Vector([max(c[k] for c in bb) for k in range(3)])
    proto = PROTOS['purple'][0] if i == 1 else PROTOS['green'][i % 3]
    place(proto, (lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + 0.12, (hi.x - lo.x) / 2 * 1.1, i)
    o.hide_render = True; o.hide_viewport = True

# ---------------------------------------------------------------- trees
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

AUTUMN = recolour(TREE_M, 'tree_autumn', hue=0.32, sat=1.3, val=1.15) if TREE_M else None
PURPLE = recolour(TREE_M, 'tree_purple', hue=0.05, sat=0.8, val=0.5) if TREE_M else None
for i, t in enumerate(D['TREES']):
    x, y = b2((t['x'], t['z']))
    if t['kind'] == 'conifer':
        conifer(t, 100 + i)
    elif t['x'] < -4 and t['h'] < 3.5:     # the low "trees" in the west border are large shrubs
        sy = t['h'] / (1.9 * t['r'])
        big = proto_shrub(200 + i, LEAF['green'], sy, n=int(5200 * t['r'] ** 1.6), leaf=1 / t['r'])
        big.hide_render = True; big.hide_viewport = True
        place(big, x, y, 0.0, t['r'], i)
    elif TREE_M:
        r_, g_, b_ = (int(t['c'][k:k + 2], 16) for k in (1, 3, 5))
        model = PURPLE if (r_ > g_ and b_ > g_) else AUTUMN if r_ > g_ else TREE_M
        instance(model, x, y, 0.0, height=t['h'], rot=i * 1.7)

# ---------------------------------------------------------------- perennials from the planting plan (real size in metres)
SP = {int(k): v for k, v in D.get('SPECIES', {}).items()}
_sp_mats = {}
def sp_mats(i):
    if i not in _sp_mats:
        s = SP[i]
        _sp_mats[i] = [leaf_mat(f'sp{i}_leaf', s['leaf']), leaf_mat(f'sp{i}_flower', s.get('flower', s['leaf']), transl=0.25, val_var=0.15),
                       flat_mat(f'sp{i}_eye', s.get('eye', '#c9a227'), rough=0.8)]
    return _sp_mats[i]

def leaf_mound(b, rng, n, rad, hgt, L, W, mat=0, rmin=0.35):
    C, d = shell_points(rng, n, rmin, np.array([rad, rad, hgt / 2]), np.array([0, 0, hgt / 2]))
    keep = C[:, 2] > 0.01; C, d = C[keep], d[keep]
    b.add(*leaves(C, d + [0, 0, 0.7] + rng.normal(scale=0.4, size=d.shape), rng.uniform(L * 0.7, L * 1.2, len(C)), W, rng), mat)
    return C, d

def stems(b, rng, n, h, rad, lean=0.25, r=0.0025, mat=0):
    """Thin, slightly curved stems; returns a polyline (5 points) for each."""
    lines = []
    for _ in range(n):
        az = rng.uniform(0, 2 * np.pi); out = np.array([np.cos(az), np.sin(az), 0])
        base = out * rng.uniform(0, rad); top_h = h * rng.uniform(0.8, 1.05); l = rng.uniform(0.3, 1) * lean
        s = np.linspace(0, 1, 5)[:, None]
        pts = base + out * (l * top_h * s ** 1.5) + np.array([0, 0, top_h]) * s
        for a, c in zip(pts[:-1], pts[1:]): b.add(*tube(a, c, r, r * 0.7, 3), mat)
        lines.append(pts)
    return lines

def florets_along(b, rng, a, c, n, r, mat, spiral=0.012):
    """Flower spike: small florets spiralling up the segment a → c."""
    t = np.linspace(0, 1, n)[:, None]; ang = t[:, 0] * n * 2.4
    axis = unit(c - a); side = unit(np.cross(axis, [0.3, 0.1, 1.0] if abs(axis[2]) < 0.9 else [1.0, 0, 0])); side2 = np.cross(axis, side)
    rad = spiral * (1 - 0.6 * t)
    P = a + (c - a) * t + rad * (np.cos(ang)[:, None] * side + np.sin(ang)[:, None] * side2)
    N = unit(P - (a + (c - a) * t) + axis * 0.3)
    b.add(*discs(P, N, r * (1 - 0.4 * t[:, 0]), rng, 6), mat)

def daisy(b, rng, c, up, petal, n, droop, eye_r):
    up = unit(np.array(up, float)); s1 = unit(np.cross(up, [0.2, 0.3, 1.0] if abs(up[2]) < 0.9 else [1.0, 0, 0])); s2 = np.cross(up, s1)
    for k in range(n):
        a = 2 * np.pi * k / n + rng.uniform(-0.1, 0.1); d = np.cos(a) * s1 + np.sin(a) * s2
        tip = c + d * petal - up * droop * petal; w = petal * 0.28; sd = np.cross(up, d)
        b.add(np.array([c + d * eye_r * 0.8, c + d * petal * 0.5 + sd * w / 2 - up * droop * petal * 0.3, tip, c + d * petal * 0.5 - sd * w / 2 - up * droop * petal * 0.3]), np.array([[0, 1, 2, 3]]), 1)
    cone = discs(np.array([c + up * eye_r * 0.6]), np.array([up]), eye_r, rng, 10)
    b.add(*cone, 2)

def proto_species(i, seed):
    s = SP[i]; h, dd, kind = s['h'], s['d'], s['kind']; rng = np.random.default_rng(seed); b = Builder(); R = dd / 2
    if kind == 'plume':          # Calamagrostis: arching leaves, upright stems with narrow feathery plumes
        blade_clump(b, rng, 150, h * 0.6, 0.06, (0.006, 0.01), 0.7)
        for pts in stems(b, rng, 32, h, 0.07, lean=0.12):
            florets_along(b, rng, pts[2] + (pts[4] - pts[2]) * 0.2, pts[4], 26, 0.009, 1, spiral=0.008)
    elif kind == 'grass':        # Sesleria: dense lime-green tuft
        blade_clump(b, rng, 260, h, 0.05, (0.004, 0.007), 0.8, droop=0.45)
    elif kind == 'finegrass':    # Stipa tenuissima: hair-fine, flowing
        blade_clump(b, rng, 650, h, 0.04, (0.0015, 0.0025), 0.95, droop=0.6, K=8)
    elif kind == 'spikes':       # Stachys, Salvia: leafy base, upright flower spikes
        leaf_mound(b, rng, 380, R * 0.9, h * 0.38, 0.06, 0.028)
        for pts in stems(b, rng, 24, h, R * 0.45, lean=0.2):
            florets_along(b, rng, pts[2] + (pts[4] - pts[2]) * 0.1, pts[4], 34, 0.007, 1)
    elif kind == 'daisy':        # Echinacea: tall stems with drooping pink petals around an orange cone
        leaf_mound(b, rng, 260, R * 0.8, h * 0.45, 0.09, 0.04)
        for pts in stems(b, rng, 11, h, R * 0.4, lean=0.2, r=0.004):
            daisy(b, rng, pts[-1], pts[-1] - pts[-2], 0.045, 14, 0.5, 0.018)
    elif kind == 'cloud':        # Calamintha: mound of tiny leaves under a haze of pale flowers
        leaf_mound(b, rng, 1100, R, h * 0.9, 0.025, 0.015)
        F, fd = shell_points(rng, 900, 0.85, np.array([R * 1.02, R * 1.02, h * 0.47]), np.array([0, 0, h * 0.47]))
        keep = F[:, 2] > h * 0.25; b.add(*discs(F[keep], fd[keep] + [0, 0, 0.5], 0.0045, rng, 5), 1)
    elif kind == 'wands':        # Gaura: airy arching wands with small white flowers
        leaf_mound(b, rng, 160, R * 0.4, h * 0.25, 0.05, 0.012)
        for pts in stems(b, rng, 34, h, R * 0.2, lean=0.75, r=0.0018):
            for t in rng.uniform(0.5, 1.0, 6):
                k = min(int(t * 4), 3); p = pts[k] + (pts[k + 1] - pts[k]) * (t * 4 - k)
                b.add(*discs(np.array([p + rng.normal(scale=0.01, size=3)]), np.array(rng.normal(size=(1, 3)) + [0, 0, 0.5]), 0.011, rng, 5), 1)
    elif kind == 'cushion':      # Aster dumosus: dense dome covered in small daisies
        leaf_mound(b, rng, 1300, R, h, 0.03, 0.012)
        F, fd = shell_points(rng, 700, 0.9, np.array([R * 1.03, R * 1.03, h * 0.52]), np.array([0, 0, h * 0.5]))
        keep = F[:, 2] > h * 0.3; F, fd = F[keep], fd[keep]
        N = fd + [0, 0, 0.8]
        b.add(*discs(F, N, rng.uniform(0.011, 0.015, len(F)), rng, 10), 1)
        b.add(*discs(F + unit(N) * 0.002, N, 0.004, rng, 6), 2)
    elif kind == 'pincushion':   # Scabiosa: basal leaves, wiry stems with lavender pincushion heads
        leaf_mound(b, rng, 240, R * 0.7, h * 0.3, 0.07, 0.022)
        for pts in stems(b, rng, 16, h, R * 0.35, lean=0.35, r=0.002):
            up = pts[-1] - pts[-2]
            b.add(*discs(np.array([pts[-1]]), np.array([up]), 0.019, rng, 12), 1)
            b.add(*discs(np.array([pts[-1] + unit(up) * 0.004]), np.array([up]), 0.009, rng, 8), 1)
    elif kind == 'hydrangea':    # Hydrangea paniculata: leafy dome with cone-shaped panicles fading to pink
        leaf_mound(b, rng, 1500, R, h * 0.85, 0.11, 0.065)
        F, fd = shell_points(rng, 26, 0.9, np.array([R, R, h * 0.43]), np.array([0, 0, h * 0.43]))
        for c, dvec in zip(F[F[:, 2] > h * 0.35], fd[F[:, 2] > h * 0.35]):
            up = unit(dvec + [0, 0, 1.6]); n = 60; t = rng.uniform(0, 1, n) ** 0.7
            ang = rng.uniform(0, 2 * np.pi, n); rad = 0.07 * (1 - t)
            s1 = unit(np.cross(up, [0.3, 0.2, 1.0])); s2 = np.cross(up, s1)
            P = c + up[None] * (t[:, None] * 0.22) + (np.cos(ang)[:, None] * s1 + np.sin(ang)[:, None] * s2) * rad[:, None]
            b.add(*discs(P, P - c + up * 0.05, rng.uniform(0.01, 0.014, n), rng, 5), 1)
    o = b.obj(f'sp{i}_{seed}', sp_mats(i), proto_coll); o.hide_render = True; o.hide_viewport = True
    return o

def proto_strawberry(seed):
    rng = np.random.default_rng(seed); b = Builder()
    leaf_mound(b, rng, 140, 0.17, 0.2, 0.07, 0.055)
    F, fd = shell_points(rng, 30, 0.8, np.array([0.17, 0.17, 0.1]), np.array([0, 0, 0.1]))
    b.add(*discs(F[:14], fd[:14] + [0, 0, 1], 0.009, rng, 5), 1)
    b.add(*discs(F[14:] - [0, 0, 0.02], fd[14:], 0.008, rng, 6), 2)
    o = b.obj(f'strawberry_{seed}', [leaf_mat('strawberry_leaf', '#4f7f35'), flat_mat('strawberry_flower', '#f4f1ea', rough=0.6),
                                     flat_mat('strawberry_fruit', '#b8261f', rough=0.25)], proto_coll)
    o.hide_render = True; o.hide_viewport = True; return o

# ---------------------------------------------------------------- design layer: beds, pebble strips, stepping stones, things in the yard
def poly_obj(name, pts, z, mat):
    return mesh_obj(name, [(*b2(p), z) for p in reversed(pts)], [list(range(len(pts)))], [mat], smooth=False)

def rbox(name, cx, cy, z0, sx, sy, sz, rot, mat, bevel=0.0):
    """Box centred on (cx, cy) in plan, from z0 up, rotated about Z."""
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    if bevel: bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES')
    o = mesh_obj(name, [], [], [mat]); bm.to_mesh(o.data); bm.free()
    o.location = (cx, cy, z0 + sz / 2); o.scale = (sx, sy, sz); o.rotation_euler = (0, 0, rot); return o

def corten_mat():
    m, nt, bsdf = new_mat('corten')
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 9; nz.inputs['Detail'].default_value = 8
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = lin('#5a2c16'); ramp.color_ramp.elements[1].color = lin('#a3562a')
    link(nt, nz.outputs['Fac'], ramp.inputs['Fac']); link(nt, ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.8
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.3
    link(nt, nz.outputs['Fac'], bp.inputs['Height']); link(nt, bp.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def furniture(f):
    x, y = b2((f['x'], f['z'])); rot = f.get('rot', 0.0); t = f['type']
    if t == 'playhouse':     # grey-painted timber play house with a blue-grey metal roof (photo 11)
        w, d, h = f['w'], f['d'], f['h']; wall_h = h - 0.4
        paint = tex_mat('playhouse_paint', 'weathered_planks', 2.0, tint='#d8d6cc', rough=1.0, bump=0.3, sat=0.1) if has('weathered_planks') else flat_mat('playhouse_paint', '#c9c7bd')
        rbox('playhouse', x, y, 0.0, w, d, wall_h, rot, paint)
        rbox('playhouse_window', x, y - d / 2 - 0.005, 0.7, 0.6, 0.02, 0.4, rot, GLASS)
        rbox('playhouse_door', x - w * 0.3, y - d / 2 - 0.005, 0.0, 0.5, 0.02, 1.05, rot, flat_mat('playhouse_door', '#b9b7ad', rough=0.8))
        hw, hd = w / 2 + 0.12, d / 2 + 0.15
        v = [(-hw, -hd, wall_h), (hw, -hd, wall_h), (hw, hd, wall_h), (-hw, hd, wall_h), (-hw, 0, h), (hw, 0, h)]
        o = mesh_obj('playhouse_roof', v, [(0, 1, 5, 4), (2, 3, 4, 5)], [flat_mat('roof_bluegrey', '#5d6b7a', rough=0.45, metallic=0.5)], smooth=False)
        o.location = (x, y, 0); o.rotation_euler = (0, 0, rot)
        o.modifiers.new('t', 'SOLIDIFY').thickness = 0.03
        gab = mesh_obj('playhouse_gables', [(-w / 2, -d / 2, wall_h), (w / 2, -d / 2, wall_h), (0, -d / 2, h - 0.03), (-w / 2, d / 2, wall_h), (w / 2, d / 2, wall_h), (0, d / 2, h - 0.03)],
                       [(0, 1, 2), (5, 4, 3)], [paint], smooth=False)
        gab.location = (x, y, 0); gab.rotation_euler = (0, 0, rot)
    elif t == 'woodshed':    # timber lean-to against the east fence, full of split logs (photo 11)
        w, d, h = f['w'], f['d'], f['h']; timber = MATS['woodDark']
        for sy_ in (-1, 1):
            for sx_ in (-1, 1):
                rbox('woodshed_post', x + sx_ * (w / 2 - 0.05), y + sy_ * (d / 2 - 0.05), 0, 0.09, 0.09, h - 0.08, rot, timber)
        rbox('woodshed_back', x + w / 2 - 0.02, y, 0, 0.03, d, h - 0.1, rot, timber)
        rbox('woodshed_roof', x + 0.05, y, h - 0.1, w + 0.25, d + 0.2, 0.05, rot, flat_mat('woodshed_roof', '#3f4347', rough=0.5, metallic=0.4))
        rbox('woodshed_stack', x + 0.05, y, 0.12, w - 0.2, d - 0.2, h - 0.35, rot, flat_mat('log_bark', '#5b4636', rough=0.95))
        rng_ = np.random.default_rng(11); C, N, R = [], [], []
        for zz in np.arange(0.18, h - 0.28, 0.13):
            for yy in np.arange(-d / 2 + 0.18, d / 2 - 0.15, 0.14):
                C.append([x - (w - 0.2) / 2 + 0.05 - 0.001, y + yy + rng_.uniform(-0.02, 0.02), zz + rng_.uniform(-0.02, 0.02)]); N.append([-1, 0, 0]); R.append(rng_.uniform(0.05, 0.075))
        b = Builder(); b.add(*discs(np.array(C), np.array(N, float), np.array(R), rng_, 7)); b.obj('woodshed_log_ends', [flat_mat('end_grain', '#c9a27a', rough=0.9)])
    elif t == 'firebowl':
        r = f['r']; bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.001], context='VERTS')
        o = mesh_obj('fire_bowl', [], [], [corten_mat()]); bm.to_mesh(o.data); bm.free()
        o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
        o.modifiers.new('t', 'SOLIDIFY').thickness = 0.012
        o.location = (x, y, 0.42); o.scale = (1, 1, 0.55)
        b = Builder(); b.add(*tube([x, y, 0.03], [x, y, 0.2], r * 0.45, r * 0.3, 16)); b.obj('fire_bowl_stand', [o.data.materials[0]])
    elif t in ('chair', 'table'):
        black = flat_mat('powder_black', '#1f2123', rough=0.5, metallic=0.3); b = Builder()
        if t == 'table':
            r = f['r']; b.add(*discs(np.array([[x, y, 0.45]]), np.array([[0, 0, 1.0]]), r, np.random.default_rng(1), 24))
            for a in range(3):
                ang = a * 2 * math.pi / 3; b.add(*tube([x + math.cos(ang) * r * 0.8, y + math.sin(ang) * r * 0.8, 0], [x, y, 0.44], 0.01, 0.01, 5))
        else:   # string lounge chair: tube frame, seat and back
            c, s = math.cos(rot), math.sin(rot)
            P = lambda u, v, z: [x + u * c - v * s, y + u * s + v * c, z]
            for u in (-0.3, 0.3):
                b.add(*tube(P(u, -0.3, 0), P(u, -0.3, 0.38), 0.012, 0.012, 5)); b.add(*tube(P(u, 0.3, 0), P(u, 0.2, 0.38), 0.012, 0.012, 5))
                b.add(*tube(P(u, -0.3, 0.38), P(u, 0.3, 0.36), 0.012, 0.012, 5)); b.add(*tube(P(u, 0.3, 0.36), P(u, 0.42, 0.8), 0.012, 0.012, 5))
            b.add(np.array([P(-0.3, -0.3, 0.37), P(0.3, -0.3, 0.37), P(0.3, 0.3, 0.35), P(-0.3, 0.3, 0.35)]), np.array([[0, 1, 2, 3]]))
            b.add(np.array([P(-0.3, 0.3, 0.36), P(0.3, 0.3, 0.36), P(0.3, 0.42, 0.79), P(-0.3, 0.42, 0.79)]), np.array([[0, 1, 2, 3]]))
        b.obj(t, [black])

DESIGN = 'DESIGN_BEDS' in D
if DESIGN:
    for k, bed in enumerate(D['DESIGN_BEDS']): poly_obj(f'design_bed_{k}', bed, 0.022, MATS['soil'])
    GRAVEL_M = (tex_mat('white_pebbles', 'clean_pebbles', asset_size('clean_pebbles', 1.0), rough=1.0, bump=0.6) if has('clean_pebbles')
                else flat_mat('white_pebbles', '#d9d7d0', rough=0.8))
    EDGE_M = flat_mat('concrete_edge', '#a7a59f', rough=0.8)
    for k, g in enumerate(D['GRAVEL']):
        poly_obj(f'pebbles_{k}', g, 0.04, GRAVEL_M)
        b = Builder(); pts = [np.array([*b2(p), 0.0]) for p in g]
        for a, c in zip(pts, pts[1:] + pts[:1]): b.add(*tube(a + [0, 0, 0.03], c + [0, 0, 0.03], 0.03, 0.03, 4))
        b.obj(f'pebble_edge_{k}', [EDGE_M])
    fr = D['FIRE']; fx, fy = b2((fr['x'], fr['z']))
    ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    mesh_obj('fire_circle', [(fx + fr['r'] * math.cos(a), fy + fr['r'] * math.sin(a), 0.035) for a in ang], [list(range(48))], [GRAVEL_M], smooth=False)
    b = Builder()
    for a, c in zip(ang, np.roll(ang, -1)):
        b.add(*tube([fx + fr['r'] * math.cos(a), fy + fr['r'] * math.sin(a), 0.03], [fx + fr['r'] * math.cos(c), fy + fr['r'] * math.sin(c), 0.03], 0.025, 0.025, 4))
    b.obj('fire_circle_edge', [corten_mat()])
    SLAB_M = (tex_mat('concrete_slab', 'concrete_floor_02', asset_size('concrete_floor_02', 2.0), tint='#e4e2dc', rough=1.0, bump=0.1, sat=0.3)
              if has('concrete_floor_02') else flat_mat('concrete_slab', '#b9bab6', rough=0.7))
    pa = D['PATH']
    for k, sl in enumerate(D['SLABS']):
        x, y = b2((sl['x'], sl['z'])); rbox(f'slab_{k}', x, y, 0.0, pa['along'], pa['across'], 0.06, -sl['ang'], SLAB_M, bevel=0.006)
    for f in D['FURNITURE']: furniture(f)
    SP_PROTOS = {i: [proto_species(i, 300 + i * 10 + v) for v in range(2)] for i in SP}
    rs = np.random.default_rng(5)
    for n, p in enumerate(D['DESIGN_PLANTS']):
        x, y = b2((p['x'], p['z']))
        place(SP_PROTOS[p['sp']][n % 2], x, y, 0.022, rs.uniform(0.85, 1.15), p['rot'])
    print(f"design: {len(D['DESIGN_PLANTS'])} plants, {len(D['SLABS'])} stepping stones")

# Raised planters: strawberries instead of the lettuce spheres
STRAW = [proto_strawberry(s) for s in (31, 32)]
rs = np.random.default_rng(9)
for o in objs_with('veg'): o.hide_render = True; o.hide_viewport = True
for a, bx in D['PLANTERS']:
    for xx in np.arange(a + 0.3, bx - 0.15, 0.32):
        for zz in (-3.45, -3.1, -2.75):
            x, y = b2((xx + rs.uniform(-0.05, 0.05), zz + rs.uniform(-0.04, 0.04)))
            place(STRAW[int(rs.integers(2))], x, y, 0.46, rs.uniform(0.85, 1.2), rs.uniform(0, 6.3))

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
    ramp.color_ramp.elements[0].color = lin('#4a8a28'); ramp.color_ramp.elements[1].color = lin('#7fae3c')   # lush, freshly mown (photos 03, 04)
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.7
    link(nt, nz.outputs['Fac'], ramp.inputs['Fac']); link(nt, ramp.outputs['Color'], hs.inputs['Color'])
    return m

LAWN_P = poly('LAWN')
blocked = [poly(k) for k in ('DRIVE', 'RAMP', 'PATIO', 'DECK_EDGE', 'HOUSE', 'GARAGE')]
blocked += [np.array([b2(p) for p in bed]) for bed in D.get('DESIGN_BEDS', []) + D.get('GRAVEL', [])]
rng = np.random.default_rng(7)
xmin, ymin = LAWN_P.min(0); xmax, ymax = LAWN_P.max(0)
DENSITY = 170      # patches per m²
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

# ---------------------------------------------------------------- telescopic pool enclosure (photos 02, 05, 19)
# Four low angular segments sliding over each other, milky clear panels, anthracite profiles and rails.
for o in objs_with('cover'): o.hide_render = True; o.hide_viewport = True
for o in objs_with('alu'):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    if px0 - 0.4 < min(c.x for c in bb) and max(c.x for c in bb) < px1 + 0.4 and py0 - 0.6 < min(c.y for c in bb) and max(c.y for c in bb) < py1 + 0.6 and max(c.z for c in bb) < 0.9:
        o.hide_render = True; o.hide_viewport = True
PANEL = clear_panel_mat()
ALU = flat_mat('anthracite_alu', '#3a3e43', rough=0.35, metallic=0.6)   # profiles are anthracite (photo 05)
yc = (py0 + py1) / 2; DECK_TOP = 0.15
def profile(half, h):
    """Angular low enclosure (photos 02, 05, 19): short upright sides, a chamfer, flat top."""
    side, cham = 0.16, 0.42
    return np.array([[-half, 0.0], [-half, side], [-half + cham, h], [half - cham, h], [half, side], [half, 0.0]])
for i in range(4):
    half, h = 1.98 - i * 0.05, 0.52 - i * 0.035
    xa = px0 - 0.1 + i * 1.62; xb = xa + 1.72
    pr = profile(half, h); n = len(pr)
    verts = [(xa, yc + y, DECK_TOP + z) for y, z in pr] + [(xb, yc + y, DECK_TOP + z) for y, z in pr]
    faces = [(j, j + 1, n + j + 1, n + j) for j in range(n - 1)]
    if i == 0: faces.append(tuple(range(n - 1, -1, -1)))            # closed end towards the house
    if i == 3: faces.append(tuple(range(n, 2 * n)))
    mesh_obj(f'cover_panel_{i}', verts, faces, [PANEL], smooth=False)
    b = Builder()
    for xx in (xa, xb, (xa + xb) / 2):                                # arches at both ends and in the middle
        for (y0_, z0_), (y1_, z1_) in zip(pr[:-1], pr[1:]):
            b.add(*tube([xx, yc + y0_, DECK_TOP + z0_], [xx, yc + y1_, DECK_TOP + z1_], 0.025, 0.025, 4))
    for y_, z_ in pr[1:-1]:                                            # profiles along every break of the shape
        b.add(*tube([xa, yc + y_, DECK_TOP + z_], [xb, yc + y_, DECK_TOP + z_], 0.02, 0.02, 4))
    for s_ in (-1, 1):
        b.add(*tube([xa, yc + s_ * half, DECK_TOP + 0.03], [xb, yc + s_ * half, DECK_TOP + 0.03], 0.035, 0.035, 4))
    b.obj(f'cover_frame_{i}', [ALU])
for s in (-1, 1):   # running rails on the deck
    b = Builder(); b.add(*tube([px0 - 0.15, yc + s * 2.0, DECK_TOP + 0.01], [px1 + 1.2, yc + s * 2.0, DECK_TOP + 0.01], 0.02, 0.02, 4)); b.obj('cover_rail', [ALU])

# ---------------------------------------------------------------- surroundings: sidewalks, kerbs, road, houses across the street, tree line
CHAIN = [(22.99, -70.0)] + [tuple(D['P'][k]) for k in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12)] + [(-70.0, 24.48)]
def offset_chain(chain, w):
    pts = np.array(chain, float); out = []
    nrm = lambda a, c: np.array([c[1] - a[1], -(c[0] - a[0])]) / np.linalg.norm(np.subtract(c, a))   # outward for a clockwise plot
    for i in range(len(pts)):
        ns = ([nrm(pts[i - 1], pts[i])] if i > 0 else []) + ([nrm(pts[i], pts[i + 1])] if i < len(pts) - 1 else [])
        o = ns[0] * w if len(ns) == 1 else (ns[0] + ns[1]) / (1 + ns[0] @ ns[1]) * w
        out.append(pts[i] + o)
    return out
def strip(name, w0, w1, z0, mat, z1=None):
    A, B = offset_chain(CHAIN, w0), offset_chain(CHAIN, w1); n = len(A); z1 = z0 if z1 is None else z1
    v = [(*b2(p), z0) for p in A] + [(*b2(p), z1) for p in B]
    return mesh_obj(name, v, [(n + i, n + i + 1, i + 1, i) for i in range(n - 1)], [mat], smooth=False)
ST = D['H']['street']
SIDEWALK = MATS['cobble']   # the street and pavements are the same interlocking pavers (photo 07)
KERB = flat_mat('kerb', '#a9a7a1', rough=0.8)
VERGE = far_lawn_mat('verge')
for side, (w0, w1) in (('near', (0.02, 2.0)), ('far', (8.6, 10.6))):
    strip(f'sidewalk_{side}', w0, w1, ST + 0.06, SIDEWALK)
    kw = w1 if side == 'near' else w0
    strip(f'kerb_top_{side}', kw - 0.15 if side == 'near' else kw, kw if side == 'near' else kw + 0.15, ST + 0.13, KERB)
    strip(f'kerb_face_{side}', kw, kw, ST + 0.13, KERB, z1=ST)
strip('verge_far', 10.6, 45.0, ST + 0.07, VERGE)
for o in objs_with('cobble'): o.location.z -= 0.0   # the big Three.js street plane is the asphalt road now

def house(x, y, rot, w=10.5, d=8.5, wall_h=3.1, ridge=3.4, seed=0):
    rng = np.random.default_rng(seed); b = Builder()
    hw, hd = w / 2, d / 2
    v = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0), (-hw, -hd, wall_h), (hw, -hd, wall_h), (hw, hd, wall_h), (-hw, hd, wall_h), (-hw, 0, wall_h + ridge), (hw, 0, wall_h + ridge)]
    b.add(np.array(v, float), np.array([[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]), 0)
    b.add(np.array(v, float), np.array([[4, 5, 9, 8][::-1], [6, 7, 8, 9][::-1]]), 1)
    b.add(np.array(v, float), np.array([[5, 6, 9], [7, 4, 8]]), 0)
    for k in range(3):   # a few dark windows on the long sides
        for s in (-1, 1):
            xx = -hw + (k + 0.7) * w / 3.4; yy = s * (hd + 0.02)
            b.add(np.array([(xx, yy, 0.9), (xx + 1.3, yy, 0.9), (xx + 1.3, yy, 2.3), (xx, yy, 2.3)]), np.array([[0, 1, 2, 3] if s > 0 else [3, 2, 1, 0]]), 2)
    o = b.obj(f'neighbour_house_{seed}', [MATS['wall'], MATS['roof'], GLASS])
    o.location = (x, y, ST + 0.07); o.rotation_euler = (0, 0, rot); return o
far = offset_chain(CHAIN, 22.0)
seed = 0
for (ax, az), (bx, bz) in zip(far[:-1], far[1:]):
    seg = np.hypot(bx - ax, bz - az); ang = math.atan2(-(bz - az), bx - ax)
    for t in np.arange(10, seg - 6, 24):
        f = t / seg; x, y = b2((ax + (bx - ax) * f, az + (bz - az) * f))
        if abs(x - 11) > 60 or abs(y + 13) > 60: continue
        house(x, y, ang, seed=seed); seed += 1
house(*b2((-13.5, 9.0)), 0.0, w=10, d=9, wall_h=3.0, ridge=2.6, seed=99)   # west neighbour, gable towards us (photo 17)
if TREE_M:
    rng = np.random.default_rng(3)
    for x in np.arange(-70, 80, 5.5):                    # tree line beyond the field and the neighbours
        instance(TREE_M, x + rng.uniform(-2, 2), 72 + rng.uniform(-6, 6), ST, height=rng.uniform(6, 11), rot=rng.uniform(0, 6.3))
    for yy in np.arange(-60, 70, 6):
        instance(TREE_M, -72 + rng.uniform(-4, 4), yy, ST, height=rng.uniform(6, 10), rot=rng.uniform(0, 6.3))
    for k in range(12):                                  # trees in the gardens across the street
        p = offset_chain(CHAIN, 30 + rng.uniform(0, 10))[int(rng.integers(1, len(CHAIN) - 1))]
        instance(TREE_M, *b2((p[0] + rng.uniform(-8, 8), p[1] + rng.uniform(-8, 8))), ST, height=rng.uniform(4, 8), rot=rng.uniform(0, 6.3))
    for k in range(5):
        instance(TREE_M, *b2((-12 - rng.uniform(0, 30), rng.uniform(-3, 22))), 0.0, height=rng.uniform(4, 7), rot=rng.uniform(0, 6.3))
bpy.context.view_layer.layer_collection.children['models'].exclude = True

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
