# Stav projektu a jak pokračovat (předávka, 10. 10. 2026)

Tento soubor je **vstupní bod pro nový chat** (Claude, Codex, ChatGPT nebo člověka). Shrnuje, co projekt je, co běží, kde co leží, jaká padla rozhodnutí a co je další krok. Podrobnosti jsou v [README.md](README.md), [ROADMAP.md](ROADMAP.md), [EDITOR.md](EDITOR.md) a [viewer/README.md](viewer/README.md).

## ⚠ Co v repozitáři chybí: složka `podklady/`

Složka `podklady/` je v `.gitignore` a **na GitHubu ani na Dellu není**. Je jen na Macu majitele v `~/Projects/gardenvisu/podklady/`. Obsahuje osobní údaje a výkresy jsou autorským dílem architekta. Když ji potřebujete, **požádejte o ni majitele** (pošle soubory do chatu nebo je zkopíruje do stejné cesty). Kód bez ní funguje, chybí jen předlohy.

| Cesta | Obsah | Kde je popis bez souborů |
|---|---|---|
| `podklady/vykresy/` | projektová dokumentace DPS (PDF): situace C.2, půdorysy přízemí a podkroví, řezy, pohledy JZ/SV/SZ/JV | rozměry přepsané do `index.html` a do tabulky „Odkud jsou rozměry“ v README |
| `podklady/fotky/letecky-*.jpg`, `ulice-*.png` | letecké snímky (jeden s měřítkem 12 m) a fotky z ulice, ze kterých vznikl první model | README, tabulka rozměrů |
| `podklady/fotky/realita/01–22` + `POPIS.md` | fotky skutečného stavu z října 2026: 01–09 a 21–22 se nemění, 10–20 jsou místa, která se mění | **[docs/FOTKY.md](docs/FOTKY.md)** |
| `podklady/navrh/osazovaci-plan-*.png` | ručně kreslený osazovací plán (paní Králová): rozšíření záhonu, 2 pásy 12 + 6 m, 10 druhů s čísly | přepsaný do `PLAN_BEDS` a `SPECIES` v `index.html`, v layoutu jako druhy 1–10 |
| `podklady/navrh/inspirace-cesta-za-domem.png`, `zastreseni-bazenu.png` | inspirace: nášlapné desky v trvalkách, nízké zastřešení bazénu | STAV.md, rozhodnutí |

Codexův web na Dellu (8082) má kopii 7 fotek z `realita/`. Je to jeho vlastní nasazení, z repozitáře to neplyne.

## Proč projekt existuje

Majitel předělává **bok domu (západ)** a **prostor za domem (sever)** včetně dvorku za garáží a chce si návrh zahrady prohlédnout co nejvěrněji realitě. Postup je: 2D layout v editoru → 3D v prohlížeči → fotorealistické pohledy v Blenderu → video. Výhledově přibude Unreal Engine na stolním PC (viz níže).

Zbytek zahrady se nemění a slouží jako kontext. Musí ale odpovídat skutečnosti (fotky 01–09 a 21–22).

## Co teď běží (Dell Precision 7530, `ssh dell`, Ubuntu 26.04, Docker)

| Služba | Adresa | Popis |
|---|---|---|
| Editor layoutu | http://192.168.20.30:8083 | 2D „jednoduchý AutoCAD“. Vrstvy, přesun tažením, kreslení ploch, rostliny z katalogu, řady, kóty, podklad z obrázku, seznam rostlin, **Půdorys PDF**, ukládání na server s historií 50 verzí a pojmenovanými verzemi |
| 3D zahrada | http://192.168.20.30:8084 | Three.js z layoutu. **Výběr verze: poslední / konkrétní z historie / výchozí model**, detailní rostliny, procházení šipkami. Původní jednoduchý model je na `/jednoduchy/` |
| Codexova studie | http://192.168.20.30:8082 | Samostatný vývoj (Compose projekt `web`, `~/gardenvisu-deploy/web`, větev `codex/reality-comparison`). **Neměnit.** Prvky z ní jsou převzaté do `viewer/` |

Compose projekt: `~/Projects/gardenvisu/deploy/compose.yaml` (`name: gardenvisu`). Aktualizace z Macu:

```
git ls-files -co --exclude-standard > /tmp/files.txt
rsync -a --files-from=/tmp/files.txt ./ dell:Projects/gardenvisu/
ssh dell 'cd ~/Projects/gardenvisu/deploy && docker compose up -d --build'
```

Layout uložený v editoru leží ve svazku `gardenvisu_layout` (`/data/layout.json` + `/data/history/`). Assety 3D (25 MB) nejsou v gitu, na Dellu jsou v `~/Projects/gardenvisu/viewer/assets/` (původ viz `viewer/README.md`).

## Tok dat

```
index.html (konstanty: dům, pozemek, plochy, rostliny)  ──export.mjs──►  tools/blender/data/scene.json + scene.glb
                                                                                │
tools/editor/from_scene.mjs  ◄──────────────────────────────────────────────────┘
        │  (jednorázově: výchozí layout.json, rostliny „zmrazené“ na kusy)
        ▼
EDITOR (layout.json, server s historií)  ──►  3D viewer (vybraná verze)    ← hotovo
                                         ──►  Půdorys PDF (plan.js)         ← hotovo
                                         ──►  Blender pohledy a video        ← ZATÍM NE (čte scene.json)
```

- **Zdroj pravdy pro zahradu je teď `layout.json` z editoru.** Konstanty v `index.html` jsou původní model, ze kterého vznikl výchozí layout. Architekturu (dům, garáž, terasa, bazén, příjezd, ploty) bere 3D viewer ze `scene.glb`, tedy z `index.html`.
- Souřadnice: metry, `x` na východ, `z` na jih k ulici, počátek v SZ rohu domu. V Blenderu `y = −z`.

## Hlavní soubory

| Cesta | Co to je |
|---|---|
| `tools/editor/editor.html` | editor (jeden soubor, bez knihoven, SVG) |
| `tools/editor/plan.js` | kreslení výkresu A3 z layoutu, sdílí ho editor i `plan.mjs` |
| `tools/editor/layout.json`, `layout.js` | výchozí layout (855 prvků, 37 druhů) |
| `tools/editor/from_scene.mjs` | výroba výchozího layoutu z modelu |
| `tools/editor/test.mjs` | automatický test editoru (`PW_CHANNEL=chrome node test.mjs`) |
| `deploy/editor/server.py` | API editoru: `GET/PUT /api/layout` (revize `X-Rev` / `X-Base-Rev`, 409 při konfliktu), `GET /api/layout?v=ID`, `GET /api/versions` |
| `deploy/viewer/Caddyfile` | statický 3D web + read-only proxy `/api/*` do editoru |
| `viewer/` | 3D z layoutu (`viewer.js`), procházení (`walk.js`, `navigation.mjs` od Codexe), příprava rostlin (`build_plants.py`) a assetů |
| `index.html` | původní webový model (Three.js r128) se všemi rozměry z výkresů |
| `tools/preview/export.mjs` | export modelu do glTF + JSON |
| `tools/preview/plan.mjs` | půdorys PDF z `layout.json`, souboru nebo `http://…/api/layout` |
| `tools/blender/build_scene.py`, `flythrough.py`, `encode_video.py`, `fetch_assets.py` | Blender: scéna, pohledy, video, assety (běží na Dellu) |
| `podklady/` (jen lokálně, v `.gitignore`) | výkresy, fotky skutečnosti 01–22 s popisem `podklady/fotky/realita/POPIS.md`, osazovací plán a inspirace `podklady/navrh/` |

## Rozhodnutí a fakta, která nejsou vidět v kódu

- **Osazovací plán (paní Králová)** tvoří rovný pás 18 m × 1 m před keři u západního plotu, dvě řady po 0,5 m. Začíná na severu, kde už trvalky rostou, a vede na jih: nejdřív 12m záhon, pak 6m. Širší kus hlíny u terasy (s ukázkovou deskou) bude trávník.
- **Za domem a dvorek za garáží:** kde je hlína, nebude trávník. Výsadba, nášlapné desky a ohniště jsou **návrh Claude, ne plán**. Domek má 1,2 × 1,2 m, stěny 1,2 m + střechu, 1 m od plotu. Od severní zdi k hranici je 2,71 + 2,00 m (situace C.2).
- **Okraj trávníku** je podle náčrtů majitele z 10. 10. (JZ oblouk, linie severní zdi garáže, oblouk u příjezdu).
- **Zastřešení bazénu:** Mountfield na míru, 3 nízké segmenty, mléčný polykarbonát, antracit, stříbrné kolejnice. **Pergola** je bioklimatická, bez prosklení. **Terasa** WPC hnědá, končí v linii domu. Střecha domu z tmavých tašek.
- Stávající keře v záhonech jsou generované a jen orientační (druhy podle fotek: bobkovišeň, vrba Hakuro, tavolníky, růže, ruj, muchovník, brslen…). Přesné zaměření chybí.
- Rutinní práci (stahování, spouštění renderů) mají dělat subagenti s Haiku, modelování Opus (přání majitele).

## Zádrhele

- Na Macu (macOS 27) nejde spustit Chromium přibalené k Playwrightu, proto `PW_CHANNEL=chrome` u `export.mjs`, `preview.mjs`, `plan.mjs` a `test.mjs`.
- Na Dellu blokuje auto-mode `rm`, takže před mazáním se ptát majitele. Dlouhé rendery spouštět přes `nohup … &`, aby je neshodilo přerušené SSH.
- Na Dellu není ffmpeg. Video skládá `encode_video.py` přes sekvencer Blenderu. Eevee bez monitoru jen s `--gpu-backend vulkan`.
- Poly Haven API odmítá výchozí user-agent Pythonu, proto `curl`.

## Další kroky (v tomto pořadí)

1. **Ladit layout v editoru** podle reality. Majitel bude upravovat a ukládat pojmenované verze.
2. **3D:** náhled přímo vedle editoru, živá aktualizace bez ukládání, převzít víc z Codexovy studie (srovnání s fotkou, AI fotostudie).
3. **Blender na `layout.json`:** `build_scene.py` má stavět rostliny a plochy z vybrané verze layoutu (stejný výběr jako ve 3D). Pak pohledy, pak video (`flythrough.py`, trasa nakreslená v editoru).
4. **Unreal Engine** (viz níže).

## Unreal Engine na stolním PC (budoucí plán)

Stroj: desktop s Ryzenem a **GTX 1070 8 GB**. Dell (Quadro P2000 4 GB) na Unreal nestačí.

- GTX 1070 je Pascal bez RT jader. Unreal Engine 5 poběží s **Lumenem v softwarovém režimu** a bez hardwarového ray tracingu. Nanite na Pascalu jde. 8 GB VRAM je hranice doporučení, takže textury do 2K a husté vegetaci instancovat.
- Doporučeno Windows (Epic Launcher) nebo Linux (hotový zip). Ovladač NVIDIA s podporou Vulkanu / DX12, RAM ideálně 32 GB.
- Postup: export `.glb` (architektura ze `scene.glb`, rostliny z Blenderu podle `layout.json`) → import do Unrealu (Datasmith nebo glTF importér, metry zůstanou) → materiály Poly Haven → rostliny přes Foliage / PCG z bodů layoutu → kamera a procházení. Jednodušší alternativa je **Twinmotion**.
- Co připravit: skript, který z `layout.json` udělá seznam instancí (druh, x, z, rotace, velikost) jako CSV nebo JSON pro import do Unrealu. Přepočet: Unreal je v cm, osa Z nahoru.
