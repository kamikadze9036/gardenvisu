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

Druhy a rozmístění rostlin v záhonech jsou orientační (generované).

Výkresy a fotky obsahují osobní údaje a výkresy jsou autorským dílem architekta, proto jsou ve složce `podklady/`, kterou git ignoruje.

## Jak je model udělaný

- **Souřadnice v metrech.** Počátek je severozápadní roh domu, `x` vede na východ podél domu, `z` na jih k ulici, `y` nahoru. Čísla z výkresů jdou rovnou do kódu.
- **Data nahoře ve skriptu:** polygony `P` (pozemek), `LAWN`, `DRIVE`, `RAMP`, `PATIO`, `DECK`, `POOL`. Z nich vznikají plochy (`ShapeGeometry`) a desky (`ExtrudeGeometry`).
- **Stavba z kvádrů** (`BoxGeometry`). Střešní plochy jsou desky natočené o sklon, střešní okna jsou na ně připevněná. Okna dělá funkce `opening(face, …)`: tmavý rám a zapuštěné sklo.
- **Textury** (trávník, prkna, dlažba, tvárnice, kostky) jsou nakreslené kódem na `canvas`, nic se nestahuje.
- **Rostliny** generuje algoritmus s pevným semínkem: projde pozemek po 0,72 m a rostlinu dá tam, kde není trávník, dlažba, terasa ani stavba. Kreslí se přes `InstancedMesh`.
- **Knihovny:** three.js r128 a OrbitControls z CDN (cdnjs, jsDelivr).

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
ssh dell 'cd ~/Projects/gardenvisu/tools/blender && ~/Applications/blender/blender -b --factory-startup \
  --python build_scene.py -- --samples 256 --res 1920x1080 --save out/garden.blend'
scp 'dell:Projects/gardenvisu/tools/blender/out/view-*.png' ../blender/out/
```

Volby: `--views bird,street,terrace,top`, `--samples`, `--res 1600x900`, `--cpu`, `--no-render`. Soubor `out/garden.blend` jde otevřít v Blenderu na Dellu a dál upravovat ručně. Textury a obloha jsou v `tools/blender/assets/` (nejsou v gitu, stahují se z Poly Haven API: `assets/<id>/{diff,nor,rough}.jpg`, `assets/hdri/sky.hdr` = kloofendal_48d_partly_cloudy_puresky).

## Unreal Engine (poznámky)

- MacBook Air M1 s 8 GB na Unreal Engine 5.8 nestačí (minimum 16 GB, doporučeno 32 GB a M3).
- Na Linuxu (Ubuntu 22.04+) Unreal běží z hotového zipu pro Linux, bez launcheru. Potřebuje samostatnou grafiku s Vulkanem (NVIDIA ovladač 570+, ideálně 8 GB VRAM) a 32 GB RAM. Ověření: `nvidia-smi`, `free -h`, `lsb_release -a`.
- Model jde z Three.js vyexportovat do glTF (`GLTFExporter`) a importovat do Unrealu. Rozměry v metrech zůstanou.
- Pro začátek může být jednodušší Twinmotion (od Epicu, pro architekty).

Zdroje: [macOS požadavky](https://dev.epicgames.com/documentation/unreal-engine/macos-development-requirements-for-unreal-engine), [Linux požadavky](https://dev.epicgames.com/documentation/unreal-engine/linux-development-requirements-for-unreal-engine?lang=en-US), [Linux quickstart](https://dev.epicgames.com/documentation/unreal-engine/linux-development-quickstart-for-unreal-engine).

## Procházení modelu (plán)

Rendery z Blenderu jsou statické snímky. Jak model procházet, od nejjednodušší varianty:

1. **Walk mód v Blenderu.** `out/garden.blend` přepnout na Eevee a projít ho jako ve hře (`Shift+``, WASD a myš). Funguje hned, jen na Quadro P2000 bude trhanější. Pro procházení je dobré vypnout trávník z instancí (objekt `lawn_points`).
2. **Video průlet.** Kamera po dráze ulice → zahrada → terasa, render v Cycles do MP4. Fotorealistické, ale ne interaktivní. Render řádově hodiny.
3. **Procházení v prohlížeči se zapečeným světlem.** Cycles spočítá stíny a odražené světlo do textur (bake) a výsledek se vrátí do webového modelu s ovládáním WASD. Plynulé i na iPadu a mobilu, jde snadno sdílet. Nejlépe sedí k účelu ukazovat návrh zahrady.
4. **Unreal Engine 5 (do budoucna).** Na Quadro P2000 (4 GB, Pascal) nemá smysl. V záloze je GTX 1070 s 8 GB VRAM, která splňuje doporučených 8 GB. Je to taky Pascal bez RT jader, takže Lumen jen v softwarovém režimu. Je to desktopová karta, takže potřebuje stolní PC, nebo eGPU box přes Thunderbolt 3, pokud ho Dell podporuje (neověřeno). Postup: export `.glb` z Blenderu, import do Unrealu, rozměry v metrech zůstanou.

## Další kroky

- Zakreslit návrh nové zahrady do modelu (záhony, cesty, stromy) jako samostatnou vrstvu.
- Procházení podle plánu výše (Walk mód, video, zapečené světlo pro web).
- Export `.glb` pro Unreal nebo Twinmotion.
