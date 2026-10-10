"""Make secondary-UV materials compatible with the project's Three.js r128.
Moves the selected UV accessor to TEXCOORD_0; preserves the binary geometry.
"""
import json
from pathlib import Path
import struct
import sys

def normalize(path):
    path=Path(path);raw=path.read_bytes();magic,version,total=struct.unpack_from('<III',raw)
    assert magic==0x46546c67 and version==2 and total==len(raw)
    length,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a
    doc=json.loads(raw[20:20+length]);tail=raw[20+length:];channels={}
    for i,mat in enumerate(doc.get('materials',[])):
        refs=[]
        def visit(node):
            if isinstance(node,dict):
                for k,v in node.items():
                    if k.endswith('Texture') and isinstance(v,dict) and 'index' in v:refs.append(v)
                    else:visit(v)
            elif isinstance(node,list):
                for v in node:visit(v)
        visit(mat)
        uv={r.get('texCoord',0) for r in refs}
        if uv=={1}:
            channels[i]=1
            for ref in refs:ref['texCoord']=0
    for mesh in doc.get('meshes',[]):
        for prim in mesh['primitives']:
            if prim.get('material') in channels:
                prim['attributes']['TEXCOORD_0']=prim['attributes']['TEXCOORD_1']
                prim['attributes'].pop('TANGENT',None)
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
    path.write_bytes(struct.pack('<III',magic,version,20+len(encoded)+len(tail))+struct.pack('<II',len(encoded),kind)+encoded+tail)
    print(f'{path.name}: remapped {len(channels)} material UV channels')
if __name__=='__main__':
    for path in sys.argv[1:]:normalize(path)
