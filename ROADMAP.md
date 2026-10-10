# Plán: od layoutu k videu

Cíl: zahradu navrhovat ve 2D layoutu přetahováním rostlin a úpravou trávníku a záhonů. Ze stejných dat se pak vykreslí 3D model v prohlížeči, fotorealistické pohledy z Blenderu a video průlet.

```
layout.json  ──►  editor (2D, drag & drop)  ──►  živý 3D náhled (Three.js)
     │
     ├──►  půdorys PDF (plan.mjs)
     └──►  Blender: pohledy (build_scene.py)  ──►  video (flythrough.py)
```

## Kde jsme teď (říjen 2026)

- Data layoutu jsou konstanty přímo v `index.html` (`P`, `LAWN`, `DRIVE`, `PLAN_BEDS`, `NORTH_BED`, `NE_YARD`, `SPECIES`, `TREES`, …).
- `tools/preview/export.mjs` je vyexportuje do `tools/blender/data/scene.json` + `scene.glb`.
- Z exportu se kreslí půdorys (`plan.mjs`), Blender scéna, pohledy (`build_scene.py`) a video (`flythrough.py`, `encode_video.py`).
- Rostliny ve stávajících záhonech generuje algoritmus, nejsou to konkrétní zakreslené kusy.
- Okraj trávníku je podle náčrtu majitele (10. 10. 2026): rovně podél nového pásu na boku, obloukem do záhonu u ulice a za garáží končí v linii severní zdi garáže. 3D rendery a video jsou ještě ze stavu před touto úpravou.

## Fáze 1 – data layoutu do samostatného souboru

- `layout.json` jako jediný zdroj pravdy. Obsahuje pozemek a hranice, stavby (dům, garáž, pergola, terasa, bazén), zpevněné plochy, trávník, záhony, kačírek, nášlapné desky, mobiliář, stromy a **každou rostlinu jako samostatný kus** (druh, x, z, natočení, velikost).
- Stávající generované rostliny jednou „zmrazit“ do konkrétních kusů, aby šly ručně posouvat a mazat.
- `catalog.json` s katalogem druhů: český a latinský název, výška, šířka, barva listu a květu, doba kvetení, stálezelená ano/ne a typ 3D tvaru pro Blender (tráva, klasy, kopretina, polštář, hortenzie, keř, strom…).
- `index.html`, `export.mjs`, `plan.mjs` a `build_scene.py` čtou `layout.json` místo konstant v kódu.

## Fáze 2 – editor layoutu (2D)

Stránka `editor.html` ve stylu půdorysu z `plan.mjs`:

- **Rostliny:** panel s katalogem, přetažením na plán vznikne rostlina ve skutečné velikosti. Jde ji posouvat, otáčet, mazat a kopírovat. Hromadný výběr a „vysadit řadu po 0,5 m“ jako v osazovacím plánu.
- **Plochy:** okraj trávníku, záhonů a cest jako křivky. Body jde táhnout, přidávat a mazat, okraje vyhlazovat do oblouků. Změna trávníku automaticky změní záhon a naopak.
- **Pomůcky:** mřížka a přichytávání (0,1 m), měření vzdáleností, kóty, vrstvy (stávající stav / návrh), zamčení staveb.
- **Varianty:** „stávající stav“, „návrh A“, „návrh B“ a jejich porovnání vedle sebe.
- **Ukládání:** export a import `layout.json`, průběžné ukládání v prohlížeči, historie kroků zpět. Volitelně sdílené úložiště, aby šlo editovat i z iPadu.
- **Výstupy:** tisk půdorysu do PDF (A3, 1 : 150) a seznam rostlin k nákupu (druh, počet).
- Ovládání myší i dotykem (iPad).

## Fáze 3 – živý 3D náhled

- Scénu z `index.html` rozdělit na modul, který postaví 3D model z `layout.json`.
- V editoru rozdělená obrazovka: vlevo 2D plán, vpravo 3D. Každá změna se hned promítne do 3D.
- Rostliny ve 3D podle typu z katalogu (zjednodušené tvary, aby to běželo plynule i na iPadu).

## Fáze 4 – Blender pohledy

- `build_scene.py` čte rostliny jednotlivě z `layout.json` a pro každý druh v katalogu má 3D prototyp, který už dnes umí generovat (trávy, klasy, kopretiny, hortenzie, keře, stromy).
- Kamery: stávající pohledy + možnost uložit kameru přímo z 3D náhledu v editoru.
- Jeden příkaz `render.sh`: export → rsync na Dell → render přes `nohup` → stažení obrázků.

## Fáze 5 – Blender video

- Trasu kamery kreslit v editoru (body na plánu + výška a kam se kamera dívá, rychlost) a uložit do `layout.json` místo pole `ROUTE`.
- Rychlý náhled v nízké kvalitě (asi 2 h), finální verze přes noc (1280×720, asi 6 h) se snímky do PNG s možností pokračovat po přerušení.

## Otevřené otázky

- Kde editor poběží: jen lokálně jako soubor, jako sdílená webová stránka, nebo na NAS (Docker)?
- Má editor umět i rendery spouštět (tlačítko → render na Dellu), nebo stačí příkaz v terminálu?
- Přesnější zaměření stávajících keřů a záhonů (měření metrem nebo letecký snímek z dronu), než se stávající stav „zmrazí“.
