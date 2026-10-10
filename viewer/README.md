# 3D zahrada z layoutu

Three.js r128 stránka, která staví zahradu z `layout.json` z editoru. Nahoře jde vybrat, který layout zobrazit:
- **Editor – vždy poslední uložená verze** (výchozí, když běží vedle editoru),
- **konkrétní verze** z historie editoru (čas, název z „Uložit verzi…“, počet prvků),
- **Výchozí model (z projektu)** = `layout-default.json`.

Volba je i v adrese (`?layout=latest`, `?layout=layout-20261010-091500.json`, `?layout=model`), takže jde poslat odkaz na konkrétní verzi.

Z layoutu se bere trávník, záhony, kačírek, nášlapné desky, vyvýšené záhony, domek, dřevník, ohniště a všechny rostliny a stromy. Dům, garáž, terasa, bazén, příjezd a ploty jsou architektura ze `scene.glb` (export z `index.html`). Zastřešení bazénu je podle Mountfieldu (3 segmenty).

Vzhled a část kódu převzaté z Codexovy studie `experiments/realism` (větev `codex/reality-comparison`): PBR textury, HDR obloha, prototypy rostlin z Blender geometrie (`build_plants.py` → `assets/plants.bin`), skenovaný strom a kámen, stébla trávy, procházení šipkami s kolizemi (`walk.js`, `navigation.mjs`).

## Assety (`viewer/assets/`, nejsou v gitu)

| Soubor | Odkud |
|---|---|
| `scene.glb` | `tools/preview/export.mjs` → `tools/blender/data/scene.glb` |
| `plants.json`, `plants.bin` | `python3 viewer/build_plants.py` (z kořene repa, potřebuje numpy) |
| `leafy_grass/`, `aerial_wood_snips/`, `wood_floor_deck/` | Poly Haven textury (`tools/blender/fetch_assets.py`) |
| `models/tree_small_02.glb`, `models/boulder_01.glb`, `sky.hdr` | zmenšené Blenderem: `blender -b --python viewer/prepare_web_assets.py -- tools/blender/assets viewer/assets/models` |
| `../layout-default.json` | kopie `tools/editor/layout.json` |

Na Dellu jsou assety v `~/Projects/gardenvisu/viewer/assets/`, kontejner je kopíruje při buildu.
