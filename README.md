# gardenvisu

Interaktivní 3D model rodinného domu a zahrady pro návrh nové zahrady. Model běží v prohlížeči (Three.js), nic se neinstaluje. Dům je postavený podle projektové dokumentace, zahrada podle leteckého snímku s měřítkem a fotek z ulice.

**Otevření:** dvakrát klikněte na `index.html` (potřebuje internet kvůli knihovně Three.js z CDN). Tažením otáčíte, kolečkem nebo dvěma prsty přibližujete. Dole jsou pohledy (ptačí, z ulice, z terasy, shora) a vrstvy, které jdou vypnout. Mřížka 1 m pomáhá při kreslení nových záhonů.

## Obsah

| Cesta | Co to je |
|---|---|
| `index.html` | Aktuální model (verze 6 artifaktu), jeden soubor, HTML + CSS + JS |
| `verze/01-mockup.html` | První ukázka Three.js, smyšlená zahrada 16 × 12 m |
| `verze/02-podle-snimku-odhad.html` | První pokus podle leteckých snímků, rozměry odhadem |
| `verze/03-podle-snimku-meritko.html` | Totéž přepočítané podle lišty měřítka 0–12 m |
| `verze/04-fotky-z-ulice.html` | Doplněno podle fotek z ulice (sedlová střecha, garáž, plot) |
| `podklady/vykresy/` | Projektová dokumentace DPS (PDF, 1 : 50). **Jen lokálně, není v repozitáři** |
| `podklady/fotky/` | Letecké snímky a fotky z ulice, ze kterých je zahrada. **Jen lokálně, není v repozitáři** |
| `tools/measure_elevations.py` | Vyměření oken z pohledů (najde šedě vyplněná skla a převede na metry) |
| `tools/preview/` | Headless náhled modelu, uloží screenshot každého pohledu. `export.mjs` vyexportuje model pro Blender |
| `tools/blender/build_scene.py` | Sestaví fotorealistickou scénu v Blenderu a vyrenderuje pohledy v Cycles |
| `tools/blender/flythrough.py` | Video průlet zahradou (MP4), spouští se po `build_scene.py` |
| `tools/preview/plan.mjs` | Půdorys stávajícího stavu podle modelu (A3, 1 : 150, PDF + PNG), rostliny očíslované jako v osazovacím plánu. Spuštění: `PW_CHANNEL=chrome node plan.mjs ../blender/data/scene.json out` po exportu |
| `tools/blender/fetch_assets.py` | Stáhne textury, oblohu a modely z Poly Haven do `tools/blender/assets/` |
| `tools/editor/editor.html` | **Editor layoutu** (vrstvy, přesun, plochy, rostliny z katalogu, kóty). Otevřít dvojklikem, návod v [EDITOR.md](EDITOR.md) |
| `ROADMAP.md` | Plán: editor layoutu s drag & drop rostlin, živé 3D, Blender pohledy a video ze stejných dat |
| `podklady/navrh/` | Osazovací plán, inspirační fotky (cesta za domem, zastřešení bazénu). **Jen lokálně** |
| `podklady/fotky/realita/` | Fotky skutečného stavu 01–22 a jejich popis `POPIS.md`. **Jen lokálně** |

Starší verze vznikaly postupně během jednoho rozhovoru. Každá další přidávala podklady, takže je vidět, jak se přesnost zlepšovala.

## Odkud jsou rozměry

| Prvek | Hodnota | Zdroj |
|---|---|---|
| Dům | 14,9 × 8,65 m | D.1.1.b_101 půdorys přízemí |
| Okap / hřeben / komín | +4,150 / +7,720 / +8,370 | situace C.2, pohledy |
| Sklon střechy | cca 39,5° (dopočteno z okapu a hřebene) | výpočet |
| ±0,000 | podlaha přízemí, terén −0,150 | situace, pohledy |
| Garáž | 8,1 × 8,5 m, z 4,30–12,80, atika +2,970, podlaha −0,150 | půdorys, pohledy SZ a JV |
| Vrata garáže | 6,9 × 2,4 m, 5 lamel, branka vlevo | pohled JZ |
| Zapuštěné prosklení obýváku a vchodu | líc 7,55 m (fasáda 8,65 m), podhled +2,270 | půdorys, pohled SZ |
| Pergola Ž.11 | x 0,03–7,94, z 8,65–10,70, +2,270 až +2,450, 3 sloupky | půdorys, pohled SZ |
| Vikýř O.11 | x 7,82–9,80, lícem ve fasádě, vršek +6,39 | pohledy JZ, SZ, JV |
| Střešní okna | jih x 1,45 / 4,66 + 5,56 / 12,63, sever x 2,76 / 12,27, šířka cca 0,88 m | pohledy JZ, SV |
| Okna ve fasádách | viz komentáře v `index.html` | pohledy JZ, SV, SZ, JV |
| Hranice pozemku, trávník, záhony, terasa, bazén | odečteno z leteckého snímku s lištou 12 m, přesnost cca ±0,5 m | `podklady/fotky/letecky-s-meritkem.jpg` |
| Sklon příjezdu | 9,1 % | situace |
| Plot a zeď | tvárnice + pole z lamel, cca 1,6 m od chodníku | fotky z ulice, výška odhadem |
| Fotovoltaika | 4 řady na jih, cca 10°, schované za atikou | letecký snímek + fotky |

Druhy a rozmístění rostlin ve stávajících záhonech jsou orientační (generované podle fotek). Návrh je popsaný níže.

Výkresy a fotky obsahují osobní údaje a výkresy jsou autorským dílem architekta, proto jsou ve složce `podklady/`, kterou git ignoruje.

## Jak je model udělaný

- **Souřadnice v metrech.** Počátek je severozápadní roh domu, `x` vede na východ podél domu, `z` na jih k ulici, `y` nahoru. Čísla z výkresů jdou rovnou do kódu.
- **Data nahoře ve skriptu:** polygony `P` (pozemek), `LAWN`, `DRIVE`, `RAMP`, `PATIO`, `DECK`, `POOL`. Z nich vznikají plochy (`ShapeGeometry`) a desky (`ExtrudeGeometry`).
- **Stavba z kvádrů** (`BoxGeometry`). Střešní plochy jsou desky natočené o sklon, střešní okna jsou na ně připevněná. Okna dělá funkce `opening(face, …)`: tmavý rám a zapuštěné sklo.
- **Textury** (trávník, prkna, dlažba, tvárnice, kostky) jsou nakreslené kódem na `canvas`, nic se nestahuje.
- **Rostliny** generuje algoritmus s pevným semínkem: projde pozemek po 0,72 m a rostlinu dá tam, kde není trávník, dlažba, terasa ani stavba. Kreslí se přes `InstancedMesh`.
- **Knihovny:** three.js r128 a OrbitControls z CDN (cdnjs, jsDelivr).

## Nasazení na Dell (Docker)

Dva kontejnery v jednom Compose projektu `gardenvisu` (`deploy/compose.yaml`), dostupné v domácí síti:

| Služba | Adresa | Co to je |
|---|---|---|
| `editor` | http://192.168.20.30:8083 | Editor layoutu. Layout se ukládá na server (svazek `gardenvisu_layout`, historie posledních 50 verzí), takže je stejný na všech zařízeních |
| `viewer` | http://192.168.20.30:8084 | 3D model v Three.js (`index.html`) a starší verze v `/verze/` |

Aktualizace po změnách v repu (z Macu):

```
git ls-files -co --exclude-standard > /tmp/files.txt
rsync -a --files-from=/tmp/files.txt ./ dell:Projects/gardenvisu/
ssh dell 'cd ~/Projects/gardenvisu/deploy && docker compose up -d --build'
```

Kontejnery běží bez root práv, s read-only systémem souborů a limitem 256 MB RAM. Codexův samostatný vývoj je jiný Compose projekt (`~/gardenvisu-deploy/web`, port 8082) a tenhle ho nijak neovlivňuje.

## Ověření změn

```
cd tools/preview
npm install
npx playwright install chromium
node preview.mjs ../../index.html out
```

Screenshoty se uloží do `tools/preview/out/`.

## Fotorealistické rendery (Blender)

Model se z Three.js vyexportuje do glTF a v Blenderu se z něj postaví scéna pro Cycles: PBR materiály a HDRI obloha z [Poly Haven](https://polyhaven.com) (CC0), trávník z instancí stébel, rostliny a stromy generované kódem podle stejných dat jako v prohlížeči. Rendery běží na Dellu (Precision 7530, Quadro P2000, Blender 5.2 LTS v `~/Applications/blender`).

```
cd tools/preview
PW_CHANNEL=chrome node export.mjs ../../index.html ../blender/data    # scene.glb + scene.json
rsync -a ../blender/ dell:Projects/gardenvisu/tools/blender/ --exclude out --exclude assets
ssh dell 'cd ~/Projects/gardenvisu/tools/blender && python3 fetch_assets.py'           # jen poprvé
ssh dell 'cd ~/Projects/gardenvisu/tools/blender && nohup ~/Applications/blender/blender -b --factory-startup \
  --python build_scene.py -- --samples 256 --res 1920x1080 --save out/garden.blend > out/render.log 2>&1 &'
scp 'dell:Projects/gardenvisu/tools/blender/out/view-*.png' ../blender/out/
```

Volby: `--views bird,street,terrace,top,west-bed,north-path,yard,pool`, `--samples`, `--res 1600x900`, `--cpu`, `--no-render`. Soubor `out/garden.blend` jde otevřít v Blenderu na Dellu a dál upravovat ručně. Render přes `nohup`, aby ho nepřerušilo spadlé SSH spojení. Celých 8 pohledů ve Full HD se 256 vzorky trvá asi 20 minut.

Co scéna obsahuje navíc proti webu (všechno podle fotek v `podklady/fotky/realita/`):
- zastřešení bazénu Mountfield na míru: 3 nízké segmenty, mírně šikmé boky, plochý oblouk, mléčný žebrovaný polykarbonát, antracitové profily, stříbrné kolejnice po celé terase (fotky 21, 22),
- bioklimatickou pergolu bez prosklení s lamelovou střechou, hnědou WPC terasu a taškovou střechu domu,
- zeď z tmavých tvárnic, plot z tvárnic a latí na pozinkovaných sloupcích na východě, pletivo na severu a západě, ulici a chodníky ze zámkové dlažby,
- keře podle druhů z fotek (tavolník, vrba Hakuro Nishiki, bobkovišeň, ruj, muchovník, brslen, růže), stromy z fotek, oblázkový záhon u vstupu,
- dvorek za garáží s domkem, dřevníkem, ohništěm a posezením, jahody ve vyvýšených záhonech,
- okolní domy a řadu stromů na obzoru (přibližně).

Pohledy: 4 z webu (`bird`, `street`, `terrace`, `top`) a 4 z výšky očí (`west-bed`, `north-path`, `yard`, `pool`).

Textury, obloha a modely jsou v `tools/blender/assets/`. Nejsou v gitu a stáhne je `fetch_assets.py` (seznam je v něm). Obloha je HDRI kloofendal_48d_partly_cloudy_puresky, natočená tak, aby slunce svítilo od jihozápadu jako ve webu. Modely v `assets/models/<id>/`: tree_small_02 (listnaté stromy, podzimní varianta přebarvením), boulder_01 a rock_07. Keře shrub_01–04 z Poly Haven jsou řídké africké keříky, do zahrady se nehodí, proto jsou keře a trvalky generované kódem.

## Unreal Engine (poznámky)

- MacBook Air M1 s 8 GB na Unreal Engine 5.8 nestačí (minimum 16 GB, doporučeno 32 GB a M3).
- Na Linuxu (Ubuntu 22.04+) Unreal běží z hotového zipu pro Linux, bez launcheru. Potřebuje samostatnou grafiku s Vulkanem (NVIDIA ovladač 570+, ideálně 8 GB VRAM) a 32 GB RAM. Ověření: `nvidia-smi`, `free -h`, `lsb_release -a`.
- Model jde z Three.js vyexportovat do glTF (`GLTFExporter`) a importovat do Unrealu. Rozměry v metrech zůstanou.
- Pro začátek může být jednodušší Twinmotion (od Epicu, pro architekty).

Zdroje: [macOS požadavky](https://dev.epicgames.com/documentation/unreal-engine/macos-development-requirements-for-unreal-engine), [Linux požadavky](https://dev.epicgames.com/documentation/unreal-engine/linux-development-requirements-for-unreal-engine?lang=en-US), [Linux quickstart](https://dev.epicgames.com/documentation/unreal-engine/linux-development-quickstart-for-unreal-engine).

## Video průlet

`tools/blender/flythrough.py` přidá kameru, která jede z ulice přes zeď k bazénu, podél nového záhonu na západě, kolem rohu domu, po nášlapných deskách za domem a na dvorek k ohništi, a vyrenderuje MP4 do `out/flythrough-cycles-*.mp4`:

```
ssh dell 'cd ~/Projects/gardenvisu/tools/blender && nohup ~/Applications/blender/blender -b --factory-startup \
  --python build_scene.py --python flythrough.py -- --no-render --engine cycles --samples 16 --res 960x540 --seconds 28 \
  > out/fly.log 2>&1 &'
```

Volby: `--engine eevee|cycles`, `--seconds 24`, `--fps 25`, `--res`, `--samples`, `--frames 1-50`, `--png`, `--blur`. Rychlost kamery se mění podél trasy (třetí hodnota v `ROUTE`).

Finální kvalita přes noc: s `--png` se ukládají jednotlivé snímky do `out/fly_frames/`. Přerušený render pak po restartu pokračuje, hotové snímky přeskočí. Video z nich složí `encode_video.py` přes sekvencer Blenderu, protože na Dellu není ffmpeg:

```
ssh dell 'cd ~/Projects/gardenvisu/tools/blender && nohup sh -c "~/Applications/blender/blender -b --factory-startup \
  --python build_scene.py --python flythrough.py -- --no-render --engine cycles --samples 32 --res 1280x720 --seconds 28 --png \
  > out/fly_hq.log 2>&1; ~/Applications/blender/blender -b --factory-startup --python encode_video.py -- --fps 25 > out/encode.log 2>&1" &'
```

V 1280×720 se 32 vzorky trvá snímek 20–35 s, 700 snímků tedy asi 5–6 hodin. Motion blur (`--blur`) render zhruba zdvojnásobí. Eevee na Dellu bez monitoru funguje jen s `--gpu-backend vulkan` (s OpenGL se zasekne) a vychází asi na 23 s na snímek, protože každý snímek znovu synchronizuje celou scénu. Cycles se 16 vzorky v 960×540 dá asi 10 s na snímek, 28s průlet (700 snímků) je hotový zhruba za 2 hodiny. Finální verze 1280×720 se 64 vzorky by trvala zhruba 6–8 hodin. Trasa se mění v poli `ROUTE` ve `flythrough.py`.

## Procházení modelu (plán)

Rendery z Blenderu jsou statické snímky. Jak model procházet, od nejjednodušší varianty:

1. **Walk mód v Blenderu.** `out/garden.blend` přepnout na Eevee a projít ho jako ve hře (`Shift+``, WASD a myš). Funguje hned, jen na Quadro P2000 bude trhanější. Pro procházení je dobré vypnout trávník z instancí (objekt `lawn_points`).
2. **Video průlet.** Kamera po dráze ulice → zahrada → terasa, render v Cycles do MP4. Fotorealistické, ale ne interaktivní. Render řádově hodiny.
3. **Procházení v prohlížeči se zapečeným světlem.** Cycles spočítá stíny a odražené světlo do textur (bake) a výsledek se vrátí do webového modelu s ovládáním WASD. Plynulé i na iPadu a mobilu, jde snadno sdílet. Nejlépe sedí k účelu ukazovat návrh zahrady.
4. **Unreal Engine 5 (do budoucna).** Na Quadro P2000 (4 GB, Pascal) nemá smysl. V záloze je GTX 1070 s 8 GB VRAM, která splňuje doporučených 8 GB. Je to taky Pascal bez RT jader, takže Lumen jen v softwarovém režimu. Je to desktopová karta, takže potřebuje stolní PC, nebo eGPU box přes Thunderbolt 3, pokud ho Dell podporuje (neověřeno). Postup: export `.glb` z Blenderu, import do Unrealu, rozměry v metrech zůstanou.

## Návrh zahrady

Vrstva **Návrh** ve webu a stejná data v Blenderu (konstanty `SPECIES`, `PLAN_BEDS`, `NORTH_BED`, `NE_YARD`, `FIRE`, `GRAVEL`, `PATH`, `FURNITURE`, `EXISTING` v `index.html`):

- **Rozšíření záhonu podle osazovacího plánu** (`podklady/navrh/`, jen lokálně): rovný pás 18 m × 1 m před keři u západního plotu, dvě řady po 0,5 m, 10 druhů trvalek. Začíná na severu, kde už jsou trvalky zasazené, a pokračuje na jih k bazénu: nejdřív 12m záhon, pak 6m. Širší kus hlíny u terasy bude zase trávník. Posun = změnit `x0`, `z0` v `PLAN_BEDS`.
- **Za domem a za garáží** (fotky 10–20 v `podklady/fotky/realita/`, popis v `POPIS.md` tamtéž): kde je teď hlína, nebude trávník. Návrh (zatím podle Claude, ne podle plánu): trvalky z osazovacího plánu v mulči, nášlapné betonové desky 1,0 × 0,4 m podél domu a za roh až k oblázkovému kruhu s korten ohništěm. Vzdálenost severní zdi od hranice je 2,71 + 2,00 m podle situace C.2. Domek má 1,2 × 1,2 m, stěny 1,2 m + střechu a stojí 1 m od plotu. Stávající věci zůstávají: vyvýšené záhony s jahodami, dětský domek, dřevník, posezení u garáže, pás dochanů a hortenzií, oblázkové pruhy u zdí.



## Další kroky

- **Editor layoutu:** první verze je v `tools/editor/editor.html`, návod a zadání v [EDITOR.md](EDITOR.md). Další krok je napojit 3D a Blender na `layout.json` (celý plán v [ROADMAP.md](ROADMAP.md)).
- Upřesnit návrh za domem a na dvorku podle skutečného plánu.
- Finální video ve vyšší kvalitě, procházení podle plánu výše (Walk mód, zapečené světlo pro web).
- Export `.glb` pro Unreal nebo Twinmotion.

## Pro jinou AI (ChatGPT, Claude…) nebo nového člověka

**Jak vzniklo:** celé v Claude Code s modelem Claude Opus 5.5 (říjen 2026), rutinní kroky (stahování textur) dělal subagent Claude Haiku 5.5. Historie změn je v `git log`.

**Prostředí:**

| Co | Verze / kde |
|---|---|
| Web | three.js r128 + OrbitControls z CDN, jeden soubor `index.html` |
| Náhled a export | Node.js, Playwright 1.47.2, three 0.128.0 (`tools/preview/package.json`). Na macOS 27 bundled Chromium nejede, proto `PW_CHANNEL=chrome` |
| Rendery | Blender 5.2.2 LTS, Cycles s OptiX, Python skripty v `tools/blender/` |
| Stroj na rendery | Dell Precision 7530 (`ssh dell`, Ubuntu 26.04, i7-8750H, 37 GB RAM, Quadro P2000 4 GB), kopie projektu v `~/Projects/gardenvisu` přes rsync |
| Assety | Poly Haven (CC0), `tools/blender/fetch_assets.py` |

**Tok dat:** `index.html` je jediný zdroj pravdy pro rozměry a polohy (dům z výkresů, zahrada ze snímku a fotek, návrh). `tools/preview/export.mjs` z něj udělá `tools/blender/data/scene.glb` (stavby, plochy) a `scene.json` (rostliny, stromy, kamery, polygony, návrh). `build_scene.py` z toho postaví scénu v Blenderu: přiřadí PBR materiály podle jmen materiálů z webu, vygeneruje rostliny, trávník, stromy, zastřešení bazénu, pergolu, okolí a vyrenderuje pohledy.

**Kde co změnit:**
- rozměry, polohy, rostliny v návrhu, kamery → `index.html`, pak znovu export,
- vzhled (materiály, tvary rostlin, zastřešení, pergola, okolní domy, světlo) → `tools/blender/build_scene.py`, sekce jsou oddělené komentáři `# ----`,
- trasa videa → `ROUTE` ve `tools/blender/flythrough.py`.

**Co jiná AI nebude mít:** složku `podklady/` (výkresy, letecké snímky, fotky skutečnosti a jejich popis `podklady/fotky/realita/POPIS.md`, osazovací plán). Je jen lokálně, protože obsahuje osobní údaje a autorské výkresy. Kdo bude pokračovat, potřebuje ji dostat zvlášť.

**Souřadnice:** web má počátek v SZ rohu domu, x na východ, z na jih k ulici, y nahoru, vše v metrech. V Blenderu je x na východ, y na sever (= −z z webu), z nahoru.
