# GardenVisu — produktová vize a možnosti rozvoje

> **„Než vám dům postavíme, můžete v něm strávit celý víkend.“**

## Proč GardenVisu vzniká

Při plánování vlastního domu a zahrady je obtížné představit si prostor jen z půdorysu, osazovacího plánu a několika vizualizací. Rozhodnutí o velikosti terasy, umístění bazénu, výhledu z kuchyně, průchodech nebo výsadbě přitom mohou být po realizaci drahá či nevratná.

Cílem není jen vytvářet pěkné obrázky. **Cílem je umožnit lidem budoucí domov zažít, měnit a ověřovat ještě před stavbou a během ní.** Vlastní dům a zahrada slouží jako demonstrační projekt.

## Základní uživatelská cesta

1. **Podklady a 2D návrh:** architekt nebo majitel založí projekt podle situačního výkresu, půdorysu, modelu domu a rozměrů pozemku. V editoru rozmístí cesty, terasy, bazén, záhony a jednotlivé rostliny.
2. **Interaktivní 3D:** stejná data se zobrazí ve Three.js. Uživatel prochází budoucím pozemkem, mění pohled a porovnává varianty.
3. **Fotorealistická prezentace:** z konkrétního pohledu se vytvoří kvalitní render (např. Blender), případně AI vizualizace (např. přes externí image-to-image API). AI výstup je **ilustrativní** a nemusí přesně zachovat každý detail geometrie či výsadby.
4. **Video a VR:** filmový průlet pro prezentaci; do budoucna skutečná interaktivní prohlídka domu a zahrady ve VR headsetu (např. Three.js/WebXR). AI video samo o sobě nenahrazuje volný pohyb ve VR.
5. **Projekt během realizace:** klient ukládá varianty, vrací se k návrhu, konzultuje změny s architektem a případně předává data zahradnímu projektantovi.

## Co už existuje (říjen 2026)

- **2D editor** s detailním osazovacím plánem, katalogem rostlin, polohami a rozměry prvků, verzemi návrhu a exportem plánu.
- **Three.js 3D viewer** s procházkou po zahradě a zobrazením vegetace.
- **Blender renderovací pipeline** a ukázkové realistické pohledy / video.
- **Demonstrační projekt skutečného domu a pozemku** s vlastními podklady a návrhem výsadby.

### Co je teprve plán

- Zobecnit editor pro libovolný pozemek a importovat modely domů od architektů.
- Propojit Blender s aktuálním `layout.json`, aby render vždy odpovídal vybrané verzi návrhu.
- Otestovat AI image-to-image (např. Higgsfield nebo jiný poskytovatel), porovnat vizuální kvalitu **i věrnost geometrie**.
- Přidat WebXR režim, ověřit výkon na samostatném headsetu a způsob bezpečného zapůjčení.
- Zavést samostatné projekty, sdílení, role klient/architekt a případně placené služby.

## Pro koho to může být užitečné

**Architekti rodinných domů:** mohou klientovi ke studii nabídnout interaktivní model domu zasazeného do konkrétního pozemku. Klient si ho může projít, lépe pochopit dispozice a plánovat okolí už od začátku.

**Majitelé domů:** dostanou projekt, ke kterému se mohou vracet během celé stavby a při dokončování zahrady; mohou porovnávat varianty a komunikovat je s projektantem.

**Zahradní architekti a realizační firmy:** mohou navázat na existující situaci a podklady, připravit či upřesnit výsadbu a ukázat klientovi prostorový výsledek. GardenVisu není náhradou odborného osazovacího plánu.

## Možný obchodní model (hypotéza k ověření)

Nejzajímavější první cesta je **B2B2C**: architekt založí projekt pro klienta a nabídne mu přístup jako doplněk ke studii domu. Alternativně může studio platit licenci nebo poplatek za jednotlivý projekt. Přímý online editor pro veřejnost může následovat později.

**Ilustrační scénář, nikoliv předpověď:**

| Položka | Příklad |
| --- | ---: |
| Cena interaktivního projektu pro klienta | 4 900 Kč |
| Počet prodaných projektů za měsíc | 10 |
| Měsíční tržby | 49 000 Kč |
| Roční tržby při stejném tempu | 588 000 Kč |

**Tržby nejsou zisk.** Z výsledku je třeba odečíst přípravu a převod 3D modelů, podporu, hosting, API kredity, případné provize architektům, marketing, daně a další náklady. Ceny ani poptávka zatím nejsou ověřené. VR může být samostatný placený doplněk, ale znamená i logistiku, servis a riziko poškození headsetu.

## Navržený postup ověření

1. Dokončit přesvědčivou demonstraci vlastního domu: 2D plán → Three.js → render → krátké video.
2. Na jednom záběru otestovat AI fotorealismus proti přesnému renderu.
3. Připravit jednoduchý VR prototyp z existující Three.js scény.
4. Ukázat demonstraci 3–5 menším architektonickým studiím; zjistit, zda by službu skutečně nabídla klientům a za jakých podmínek.
5. Teprve podle výsledků investovat do obecného multi-projektového produktu a komerční infrastruktury.

## Důležité zásady

- **Přesná data jsou zdroj pravdy:** 2D/3D geometrie, druhy a polohy rostlin; AI obrázky jsou pouze prezentace.
- **Rozlišovat současné funkce a vizi.** VR a přímé AI generování nejsou automaticky hotové jen proto, že existuje 3D viewer.
- **Ověřit licence** 3D assetů, modelů a externích AI služeb před komerčním použitím.
- **Soukromí klientů:** modely soukromých domů, situační plány a fotografie nesmí být veřejné bez souhlasu; komerční provoz potřebuje řízení přístupu.

---

*Tento dokument zachycuje pracovní produktovou vizi a diskusi z 10. října 2026. Není to závazný roadmap ani finanční prognóza.*
