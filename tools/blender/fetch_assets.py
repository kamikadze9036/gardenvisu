# Downloads the CC0 textures, sky and models from Poly Haven that build_scene.py uses into assets/ next to this script.
#
#   python3 fetch_assets.py
#
# Textures: assets/<id>/{diff,nor,rough}.jpg (2k) + info.json, sky: assets/hdri/sky.hdr (4k),
# models: assets/models/<id>/ (glTF 2k with its buffers and textures) + info.json. Existing files are skipped.
# Uses curl, because the Poly Haven API refuses Python's default user agent.
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
TEXTURES = ['painted_plaster_wall', 'wood_floor_deck', 'rectangular_paving', 'precast_stone_paving', 'cobblestone_floor_03',
            'concrete_block_wall_02', 'aerial_wood_snips', 'sparse_grass', 'leafy_grass', 'bark_brown_02', 'aerial_rocks_02',
            'asphalt_02', 'concrete_floor_02', 'clean_pebbles', 'weathered_planks', 'concrete_pavement']
HDRI = 'kloofendal_48d_partly_cloudy_puresky'
MODELS = ['tree_small_02', 'boulder_01', 'rock_07']

def api(path):
    return json.loads(subprocess.run(['curl', '-sSf', f'https://api.polyhaven.com/{path}'], capture_output=True, check=True).stdout)

def get(url, dst):
    if os.path.exists(dst): return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(['curl', '-sSfL', '-o', dst, url], check=True)

def save_info(asset, folder):
    dst = os.path.join(folder, 'info.json')
    if not os.path.exists(dst):
        os.makedirs(folder, exist_ok=True)
        json.dump(api(f'info/{asset}'), open(dst, 'w'))

for t in TEXTURES:
    files = api(f'files/{t}')
    for key, name in (('Diffuse', 'diff'), ('nor_gl', 'nor'), ('Rough', 'rough')):
        get(files[key]['2k']['jpg']['url'], os.path.join(ASSETS, t, f'{name}.jpg'))
    save_info(t, os.path.join(ASSETS, t))
    print('texture', t)

get(api(f'files/{HDRI}')['hdri']['4k']['hdr']['url'], os.path.join(ASSETS, 'hdri', 'sky.hdr'))
print('hdri', HDRI)

for m in MODELS:
    g = api(f'files/{m}')['gltf']['2k']['gltf']
    folder = os.path.join(ASSETS, 'models', m)
    get(g['url'], os.path.join(folder, os.path.basename(g['url'])))
    for rel, f in g['include'].items():
        get(f['url'], os.path.join(folder, rel))
    save_info(m, folder)
    print('model', m)
