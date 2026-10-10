"""Run with Blender --background --python ... -- SOURCE OUTPUT.
Optimizes existing CC0 Poly Haven assets into standalone web GLBs.
Never modifies source files. No render or GPU is required.
"""
import bpy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from normalize_gltf import normalize
args=sys.argv[sys.argv.index('--')+1:]
source,out=map(Path,args);out.mkdir(parents=True,exist_ok=True)
for name,ratio in [('shrub_02',.65),('shrub_03',1),('shrub_04',.25),('tree_small_02',.055),('boulder_01',.4)]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=next((source/'models'/name).glob('*.gltf'))
    bpy.ops.import_scene.gltf(filepath=str(path))
    for obj in list(bpy.context.scene.objects):
        if obj.type!='MESH': continue
        bpy.context.view_layer.objects.active=obj
        if ratio<1:
            mod=obj.modifiers.new('Web geometry budget','DECIMATE');mod.ratio=ratio
            bpy.ops.object.modifier_apply(modifier=mod.name)
        for mat in obj.data.materials:
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type=='BSDF_PRINCIPLED':
                        node.inputs['Roughness'].default_value=.8
    for img in bpy.data.images:
        if img.size[0]>1024:
            factor=1024/max(img.size);img.scale(round(img.size[0]*factor),round(img.size[1]*factor))
        if img.source=='FILE':img.pack()
    bpy.ops.export_scene.gltf(filepath=str(out/f'{name}.glb'),export_format='GLB',export_image_format='JPEG',export_jpeg_quality=85,export_cameras=False,export_lights=False)
    normalize(out/f'{name}.glb')
    print('WEB_ASSET',name,(out/f'{name}.glb').stat().st_size,flush=True)
# HDR environment is reduced to 1K; preserve linear radiance.
bpy.ops.wm.read_factory_settings(use_empty=True)
img=bpy.data.images.load(str(source/'hdri/sky.hdr'));img.scale(1024,512)
img.filepath_raw=str(out.parent/'sky.hdr');img.file_format='HDR';img.save()
