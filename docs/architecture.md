# Architektúra

## Célok

A Kelvin Assistant architektúrájának a következő tulajdonságokat kell
megőriznie:

- internetkapcsolat nélküli futás;
- cserélhető nyelvi modellek és adattárak;
- tesztelhető alkalmazási logika;
- különválasztott Windows és Linux biztonsági határ;
- később hozzáadható hang- és automatizálási modulok;
- egyszerű helyi üzemeltetés és visszaállíthatóság.

## Telepítési nézet

### Windows 11 host

- PowerShell terminál és későbbi `kelvin` kliens;
- felhasználói jóváhagyások kezelése;
- engedélyezett PowerShell-, Git- és fájleszközök végrehajtása;
- munkakönyvtár-korlátozás és műveleti napló.

### Ubuntu Server 24.04 LTS guest

- Ollama és a telepített helyi modellek;
- Kelvin FastAPI backend;
- ChromaDB perzisztens adatai;
- Open WebUI;
- naplók és szolgáltatáskonfigurációk.

Az összeköttetés kizárólag a host és a VM közötti, korlátozott hálózati
interfészen történik. A szolgáltatások alapértelmezetten nem publikusak.

## Logikai rétegek

### Domain

Technológiától független fogalmak és szabályok. Nem importálhat FastAPI-,
Ollama- vagy ChromaDB-kódot.

### Application

Használati esetek koordinálása: beszélgetés, dokumentumindexelés,
visszakeresés és memóriakezelés. Függőségeit portokon keresztül kapja meg.

### Ports

Protokollok és interfészek a cserélhető komponensekhez:

- nyelvi modell;
- embedding-szolgáltató;
- vektortár;
- dokumentumbetöltő;
- memória;
- agent eszköz.

### Adapters

Külső technológiák implementációi, például Ollama és ChromaDB. Az adapterek
fordítják le a külső formátumokat a belső domain modellekre.

### API

Verziózott HTTP-szerződések, kérésellenőrzés és hibaválaszok. Nem
tartalmazhat közvetlen modell- vagy adatbázis-hívásokat.

### Agent és eszközök

Az agentciklus a felhasználói célt, a modell válaszát és az engedélyezett
eszközhívásokat koordinálja. Az eszközleírás és az eszköz végrehajtása
elkülönül. A Windows-eszközök tényleges végrehajtója a PowerShell-kliens.

## Fő adatfolyamok

### Chat

1. A kliens elküldi a kérést a verziózott API-nak.
2. Az alkalmazási réteg betölti a szükséges munkameneti kontextust.
3. Az LLM-port meghívja a konfigurált modelladaptert.
4. A válasz streamelve vagy egyben visszakerül a klienshez.

### RAG

1. Egy dokumentumbetöltő kinyeri és normalizálja a szöveget.
2. A feldolgozó metaadatokkal ellátott részekre bontja.
3. Az embedding-adapter vektorokat készít.
4. A vektortár külön dokumentum-collectionben menti az adatokat.
5. Kérdezéskor a releváns részek forrásazonosítóval kerülnek a promptba.

### Agent eszközhívás

1. A modell strukturált eszközkérést javasol.
2. A backend és a kliens ellenőrzi a sémát és a jogosultsági szabályokat.
3. Szükség esetén a kliens felhasználói jóváhagyást kér.
4. A kliens korlátozott környezetben végrehajtja a műveletet.
5. A kimenet és az auditadat visszakerül a munkamenethez.

## Függőségi szabály

A belső rétegek nem függhetnek külső keretrendszerektől. A függőségek
iránya:

```text
API/adapters -> application -> domain
                  |
                  -> ports
```

A konkrét implementációkat az alkalmazás indításakor dependency injection
kapcsolja a portokhoz.

## Adatkezelés

- A dokumentumok és a memória külön ChromaDB collectiont kapnak.
- A modellfájlok és a vektoradatok nem kerülnek Gitbe.
- A memória törölhető és később külön megőrzési szabályt kap.
- A naplók nem tartalmazhatnak titkokat vagy teljes dokumentumtartalmat.
- A fájlformátumokat és méreteket betöltés előtt ellenőrizni kell.

## Biztonsági alapelvek

- legkisebb szükséges jogosultság;
- alapértelmezett tiltás az ismeretlen eszközökre;
- jóváhagyás állapotváltoztató műveletek előtt;
- kanonikus munkakönyvtár-ellenőrzés fájlműveletek előtt;
- parancsargumentumok strukturált átadása;
- minden végrehajtás auditálása;
- titkok csak lokális környezeti konfigurációban.

## Minőségi követelmények

- Python 3.12 vagy újabb;
- teljes type hint az alkalmazáskódban;
- publikus elemekhez docstring;
- központi, strukturált logging;
- domain-specifikus kivételek;
- unit tesztek külső szolgáltatás nélkül;
- elkülönített integrációs tesztek helyi szolgáltatásokkal.

## Döntésnapló

Az elfogadott döntések a [decisions](decisions/README.md) könyvtárban
találhatók.
