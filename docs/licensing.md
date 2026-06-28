# Licencelési irányelvek

## Saját projektkód

A Kelvin Assistant eredeti forráskódja és dokumentációja Apache License 2.0
alatt érhető el, kivéve, ha egy adott fájl ettől eltérő feltételt jelöl.
A szabványos SPDX-azonosító: `Apache-2.0`.

Az Apache-2.0 megengedi a használatot, módosítást és kereskedelmi
terjesztést. Előírja többek között a licenc és a releváns értesítések
megőrzését, a módosított fájlok jelölését, valamint explicit szabadalmi
engedélyt tartalmaz.

## Mi nem kerül automatikusan Apache-2.0 alá?

- Python- és rendszerfüggőségek;
- Ollama által kezelt modellfájlok és modellváltozatok;
- Open WebUI és más önálló alkalmazások;
- Whisper- és Piper-modellek, illetve hangadatok;
- felhasználói dokumentumok és adatbázisok;
- külső szolgáltatásokhoz tartozó API-k és felhasználási feltételek;
- a modell által létrehozott tartalom, amennyiben arra más szabály vonatkozik.

Ezeket mindig a saját licencük vagy felhasználási feltételeik szerint kell
kezelni. A projektlicenc nem írja felül őket.

## Új függőség felvétele

Új komponens hozzáadása előtt:

1. azonosítani kell a pontos csomagot, verziót és forrást;
2. ellenőrizni kell a licencet és az offline terjesztés feltételeit;
3. rögzíteni kell a verziót az `uv.lock` fájlban vagy a megfelelő
   infrastruktúra-leltárban;
4. szükség esetén frissíteni kell a `THIRD_PARTY_NOTICES.md` fájlt;
5. modell vagy adatállomány esetén külön kell kezelni a használati
   korlátozásokat és az előírt értesítéseket.

## Terjesztési ellenőrzőlista

Offline telepítőcsomag vagy kiadás készítése előtt:

- szerepeljen benne a `LICENSE` és `NOTICE`;
- készüljön teljes függőségi és licencleltár;
- kerüljenek bele a kötelező harmadik féltől származó licencszövegek;
- külön legyen dokumentálva minden modell és adatállomány eredete;
- titok, személyes adat és felhasználói dokumentum ne kerüljön a csomagba;
- ellenőrizni kell a külső szolgáltatások aktuális felhasználási feltételeit.

Ez a dokumentum fejlesztési irányelv, nem jogi tanács.
