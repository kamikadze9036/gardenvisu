"""Export Claude's Blender plant geometry for Three.js, without running bpy.

Run from the repository root after tools/preview/export.mjs: python3 viewer/build_plants.py  (needs numpy).
Originally written by Codex for experiments/realism; here it writes viewer/assets/plants.{json,bin}.
Only an explicit allowlist of pure geometry functions is loaded from the source.
Shapes and species dimensions remain those of the repository; counts are reduced
for the interactive preview. Custom shrub/tree prototypes are approximations.
"""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / 'assets'
OUT.mkdir(exist_ok=True)
data = json.loads((ROOT / 'tools/blender/data/scene.json').read_text())
source = (ROOT / 'tools/blender/build_scene.py').read_text()
names = {'unit','leaves','discs','tube','Builder','shell_points','blade_clump',
         'leaf_mound','stems','florets_along','daisy','proto_species','proto_grass_clump'}
nodes = [n for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
assert {n.name for n in nodes} == names
SP = {int(k): v for k,v in data['SPECIES'].items()}
meshes = {}
def mesh_obj(name, v, f, mats, indices, coll=None):
    meshes[name] = (v, f, mats, indices)
    return SimpleNamespace(name=name)
def sp_mats(i):
    s = SP[i]
    return [s['leaf'], s.get('flower',s['leaf']), s.get('eye','#c9a227')]
ns = dict(np=np, mesh_obj=mesh_obj, SP=SP, sp_mats=sp_mats, proto_coll=None, LEAF={'grass':'#859253'})
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'blender-geometry-subset', 'exec'), ns)
# Wrappers reduce independent samples, leaving dimensions and curve profiles intact.
for name, factor in [('leaf_mound',.65),('blade_clump',.7),('stems',.8)]:
    original = ns[name]
    def limited(b,rng,n,*args,_f=original,_factor=factor,**kw):
        return _f(b,rng,max(1,round(n*_factor)),*args,**kw)
    ns[name] = limited
for i in SP:
    o=ns['proto_species'](i, 1000+i)
    meshes[f'species-{i}'] = meshes.pop(o.name)
o=ns['proto_grass_clump'](55)
meshes['grass'] = meshes.pop(o.name)

# Irregular leafy shrubs: branching sub-crowns instead of opaque sphere surfaces.
def rounded_leaves(C, N, L, W, rng):
    N=ns['unit'](N);T=ns['unit'](np.cross(N,rng.normal(size=N.shape)));S=np.cross(N,T)
    L=np.asarray(L)[:,None];W=float(W)
    v=np.stack([C-T*L/2,C-T*L*.15+S*W/2+N*L*.12,
                C+T*L*.25+S*W*.36+N*L*.09,C+T*L/2,
                C+T*L*.25-S*W*.36+N*L*.09,C-T*L*.15-S*W/2+N*L*.12],1)
    return v.reshape(-1,3),np.arange(len(C)*6).reshape(-1,6)

def crown(seed, count=2800, tall=False):
    rng=np.random.default_rng(seed); b=ns['Builder']()
    clusters=[]
    for k in range(9):
        a=k*2.399; radius=rng.uniform(.2,.63)
        c=np.array([np.cos(a)*radius,np.sin(a)*radius,rng.uniform(.5,1.2)])
        clusters.append(c)
        b.add(*ns['tube']([0,0,0],c,.025,.004,5),1)
        C,N=ns['shell_points'](rng,count//9,.22,np.array([.46,.46,.5]),c)
        keep=C[:,2]>.06; C,N=C[keep],N[keep]
        b.add(*rounded_leaves(C,N+[0,0,.45],rng.uniform(.065,.11,len(C)),.045,rng),0)
    return b.obj('crown',['#ffffff','#685444'])
o=crown(221)
meshes['shrub']=meshes.pop(o.name)
# A normalized tree, base y=0, total height=1; JS applies actual h and r.
rng=np.random.default_rng(741); b=ns['Builder']()
b.add(*ns['tube']([0,0,0],[0,0,.79],.035,.009,8),1)
for k in range(17):
    a=k*2.399; rad=rng.uniform(.32,.75); h=rng.uniform(.52,.8)
    c=np.array([np.cos(a)*rad,np.sin(a)*rad,h])
    start=np.array([0,0,rng.uniform(.25,.5)])
    mid=c*.46+np.array([0,0,.27])
    b.add(*ns['tube'](start,mid,.009,.005,5),1)
    b.add(*ns['tube'](mid,c,.005,.0015,5),1)
    C,N=ns['shell_points'](rng,290,.25,np.array([.34,.34,.16]),c)
    b.add(*ns['leaves'](C,N+[0,0,.7],.038,.024,rng),0)
o=b.obj('tree',['#ffffff','#6b5543']); meshes['tree']=meshes.pop(o.name)
# Evergreen branches and short leaf sprays, all in normalized metre coordinates.
rng=np.random.default_rng(421); b=ns['Builder']()
b.add(*ns['tube']([0,0,0],[0,0,1],.025,.004,7),1)
for h in np.linspace(.13,.95,16):
    for a in np.linspace(0,2*np.pi,7,endpoint=False)+h*19:
        tip=np.array([np.cos(a),np.sin(a),-.14])*(1-h)*rng.uniform(.85,1.1)+[0,0,h]
        start=np.array([0,0,h]); b.add(*ns['tube'](start,tip,.006,.001,4),1)
        t=rng.uniform(.12,1,(55,1)); C=start+(tip-start)*t+rng.normal(0,.025,(55,3))
        b.add(*ns['leaves'](C,rng.normal(size=(55,3))+[0,0,1],.065,.027,rng),0)
o=b.obj('conifer',['#ffffff','#6b5543']); meshes['conifer']=meshes.pop(o.name)

# Compact buffers shared by all instances. Color is linear RGB, varied per leaf.
blob=bytearray(); meta={'sourceSHA256':hashlib.sha256(source.encode()).hexdigest(),'meshes':{}}
def put(a,dtype):
    a=np.ascontiguousarray(a,dtype=dtype); offset=len(blob); blob.extend(a.tobytes()); return {'offset':offset,'length':a.size}
def linear(hex):
    v=np.array([int(hex[k:k+2],16)/255 for k in (1,3,5)])
    return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
for name,(v,faces,mats,mi) in meshes.items():
    v=np.asarray(v); pos=np.column_stack((v[:,0],v[:,2],-v[:,1]))
    colors=np.ones_like(pos); triangles=[]; rng=np.random.default_rng(19)
    for f,m in zip(faces,mi):
        colors[f]=linear(mats[m])*rng.uniform(.78,1.18)
        triangles.extend((f[0],f[k],f[k+1]) for k in range(1,len(f)-1))
    assert np.isfinite(pos).all() and np.isfinite(colors).all()
    entry={'position':put(pos,'<f4'),'color':put(colors,'<f4'),'index':put(triangles,'<u4')}
    entry['vertices']=len(pos); entry['triangles']=len(triangles)
    meta['meshes'][name]=entry
(OUT/'plants.bin').write_bytes(blob)
(OUT/'plants.json').write_text(json.dumps(meta))
print(f'{len(meshes)} prototypes, {len(blob)/1e6:.2f} MB, {sum(m["triangles"] for m in meta["meshes"].values()):,} shared triangles')
