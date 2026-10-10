# Editor layoutu – zadání a návod

Zjednodušený AutoCAD pro zahradu: vrstvy přes sebe, přesouvání tažením, kreslení ploch, rostliny z katalogu a kóty. Celý plán je v [ROADMAP.md](ROADMAP.md), editor je fáze 2.

## Spuštění

Otevřít `tools/editor/editor.html` dvojklikem. Nepotřebuje server ani internet: výchozí layout se načte z `layout.js` vedle něj. Změny se průběžně ukládají v prohlížeči. Tlačítko **Uložit** stáhne `layout.json` a **Otevřít…** ho zase načte. **Výchozí** zahodí změny a načte layout z modelu.

Na Dellu běží editor v kontejneru na http://192.168.20.30:8083 (viz README, „Nasazení na Dell“). Tam tlačítko **Uložit** (Ctrl+S) ukládá layout na server, **Uložit verzi…** uloží s názvem, aby šla verze snadno vybrat ve 3D a stavový řádek ukazuje, jestli jsou změny uložené. Neuložené změny drží prohlížeč, dokud se neuloží. Když mezitím uložil někdo jiný, editor se zeptá, jestli jeho verzi přepsat. **Stáhnout** uloží `layout.json` do počítače.

API editoru (`deploy/editor/server.py`): `GET /api/layout` vrátí layout a revizi v hlavičce `X-Rev`, `PUT /api/layout` s hlavičkou `X-Base-Rev` uloží (409, pokud se revize mezitím změnila). Předchozí verze jdou do `/data/history`.

## Soubory

| Soubor | Co dělá |
|---|---|
| `tools/editor/editor.html` | Editor, jeden soubor (HTML + CSS + JS, bez knihoven). Plán je SVG v metrech |
| `tools/editor/from_scene.mjs` | Z modelu (`tools/blender/data/scene.json` z `export.mjs`) udělá výchozí `layout.json` a `layout.js`. Generované rostliny „zmrazí“ na jednotlivé kusy |
| `tools/editor/layout.json` | Výchozí layout (data) |
| `tools/editor/layout.js` | Totéž jako `window.DEFAULT_LAYOUT`, aby editor fungoval i otevřený ze souboru |
| `tools/editor/test.mjs` | Automatický test v Chrome: načtení, výběr, přesun, kreslení plochy, kóta, krok zpět. Ukládá screenshoty do `tools/preview/out/` |

Obnovení výchozího layoutu z modelu:

```
cd tools/preview && PW_CHANNEL=chrome node export.mjs ../../index.html ../blender/data
cd ../editor && node from_scene.mjs
PW_CHANNEL=chrome node test.mjs
```

## Datový formát `layout.json`

Souřadnice v metrech: `x` na východ, `z` na jih k ulici, počátek v SZ rohu domu (stejně jako `index.html`).

```jsonc
{
  "version": 1, "units": "m",
  "meta": { "name": "…", "created": "2026-10-10", "saved": "…" },
  "layers": [ { "id": "beds", "name": "Trávník a záhony", "visible": true, "locked": false, "opacity": 1 }, … ],
  "catalog": {
    "6": { "code": "6", "cz": "Třapatka nachová", "lat": "Echinacea purpurea", "group": "perennial",
           "kind": "daisy", "h": 0.9, "d": 0.5, "leaf": "#4b6a30", "flower": "#c4508f" },
    "A": { "code": "A", "cz": "bobkovišeň", "group": "shrub", … },
    "t-briza": { "code": "S", "cz": "bříza", "group": "tree", … }
  },
  "items": [
    { "id": "i1", "layer": "site", "type": "polygon", "role": "plot", "pts": [[x, z], …], "label": "pozemek" },
    { "id": "i9", "layer": "site", "type": "rect", "role": "structure", "x": 20.9, "z": -3.1, "w": 1.2, "d": 1.2, "rot": 0, "label": "domek" },
    { "id": "i12", "layer": "site", "type": "circle", "role": "fire", "x": 20.6, "z": 1.55, "r": 0.4 },
    { "id": "i300", "layer": "plants-new", "type": "plant", "sp": "6", "x": -3.63, "z": 0.2, "rot": 1.4, "d": 0.5 },
    { "id": "i850", "layer": "dims", "type": "dim", "a": [x, z], "b": [x, z], "off": 0.5 },
    { "id": "i900", "layer": "underlay", "type": "image", "src": "data:image/…", "x": 0, "z": 0, "w": 30, "h": 22, "rot": 0 },
    { "id": "i901", "layer": "dims", "type": "text", "x": 0, "z": 0, "text": "…", "size": 0.4 }
  ]
}
```

- **Vrstvy** (pořadí = pořadí kreslení): `underlay` podklad, `beds` trávník a záhony, `paving` zpevněné plochy, `site` pozemek a stavby (výchozí zamčená), `plants-existing`, `plants-new`, `dims` kóty a popisky. Výplň pozemku (mulč) se kreslí pod vším.
- **Role ploch:** `plot`, `building`, `deck`, `pool`, `pergola`, `planter`, `structure`, `fire`, `pave`, `stone`, `gravel`, `slab`, `lawn`, `bed`.
- **Rostlina:** `sp` je klíč do katalogu, `d` (průměr) a `h` jen když se kus liší od katalogu.
- **Katalog:** trvalky z osazovacího plánu mají kódy 1–10, stávající na dvorku 11–13, keře A–L, stromy `t-…`. `kind` říká, jakým 3D tvarem se rostlina vykreslí (pro fázi 3 a 4).

## Ovládání

| Nástroj | Klávesa | Použití |
|---|---|---|
| Výběr | V | klik vybere, Shift přidá, tažení z prázdného místa = obdélníkový výběr, tažení prvku = přesun |
| Posun | H, mezerník + tažení, prostřední tlačítko | posun plánu, kolečko zoomuje ke kurzoru |
| Plocha | P | klikat body, Enter nebo dvojklik dokončí, Backspace smaže poslední bod, Esc zruší. Druh plochy vybrat v liště (záhon, trávník, kačírek, dlažba) |
| Řada | W | vybrat druh v katalogu, klik začátek, klik konec, rostliny po rozestupu z lišty (výchozí 0,5 m) |
| Kóta | D | klik, klik. Vybranou kótu jde upravit tažením konců a odsazením |
| Měřit | M | tažením, výsledek ve stavovém řádku |

- Rostlinu z katalogu jde přetáhnout myší rovnou do plánu, padne do aktivní vrstvy rostlin.
- U vybrané plochy jde táhnout body, kolečko uprostřed hrany přidá bod a Alt+klik bod smaže.
- Šipky posouvají výběr o 0,1 m (se Shiftem o 1 m). R otočí výběr o 15° (Shift+R zpět), Ctrl+D zkopíruje, Ctrl+C a Ctrl+V kopírují mezi místy, Delete maže. Ctrl+Z a Ctrl+Shift+Z vrací kroky, Ctrl+S ukládá, Ctrl+A vybere vše v aktivní vrstvě, F ukáže celý plán, G zapíná přichytávání k mřížce.
- Přichytávání: k mřížce 0,1 m a k bodům ploch, středům rostlin a koncům kót do 8 px.
- Vrstvy: oko = zobrazit, zámek = zamknout, posuvník = průhlednost, přepínač = aktivní vrstva.
- **Podklad…** vloží obrázek (letecký snímek, výkres) do vrstvy Podklad. Polohu, šířku v metrech a otočení nastavíte vpravo, pak vrstvu zamknete.
- **Seznam rostlin** spočítá kusy po druzích (stávající / návrh) a jde zkopírovat jako CSV. **Tisk** vytiskne plán bez ovládání (A3 na šířku).

## Hotovo (první verze, 10. 10. 2026)

- [x] `layout.json` a katalog, převod z modelu (`from_scene.mjs`)
- [x] vrstvy: zobrazení, zamčení, průhlednost, aktivní vrstva
- [x] výběr, obdélníkový výběr, přesun tažením, šipky, otočení, kopie, mazání, zpět a znovu
- [x] úprava ploch tažením bodů, přidání a mazání bodů, kreslení nových ploch
- [x] rostliny z katalogu tažením, řada po zadaném rozestupu, změna druhu a velikosti
- [x] kóty, měření, mřížka a přichytávání, zoom a posun
- [x] ukládání do souboru a v prohlížeči, podklad z obrázku, seznam rostlin, tisk

## Další kroky

1. ~~3D~~ hotovo (`viewer/`, výběr verze). **Napojit `plan.mjs` a Blender na `layout.json`.** `index.html` (3D v prohlížeči), `plan.mjs` (PDF) a `build_scene.py` (Blender) mají číst layout místo konstant v `index.html`. Hotovo je, až změna v editoru po uložení vidět ve 3D i v Blenderu bez ručního přepisování.
2. **Oblouky:** vyhladit okraj plochy (Catmull-Rom nebo kvadratické segmenty), aby šlo kreslit plynulé okraje záhonů.
3. **Podklad podle dvou bodů:** kliknout dva body na obrázku a zadat jejich skutečnou vzdálenost, obrázek se sám zvětší a srovná.
4. **Varianty návrhu (A/B)** a jejich porovnání.
5. **Dotykové ovládání** pro iPad (dva prsty = zoom a posun).
6. **3D náhled vedle plánu** (fáze 3 v ROADMAP).
