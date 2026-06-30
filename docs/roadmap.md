# Fejlesztési roadmap

Minden mérföldkő külön jóváhagyási pont. Egy mérföldkő akkor kész, ha a
funkció, a teszt, a dokumentáció és az üzemeltetési ellenőrzés is elkészült.

## Áttekintés

| Verzió | Cél | Állapot |
| --- | --- | --- |
| v0.1 Foundation | Repository, CI, dokumentáció, Hyper-V, Ubuntu | Kész |
| v0.2 Runtime | FastAPI, Ollama és Gemma | Kész |
| v0.3 Conversation | Chat API, streaming és sessionkezelés | Kész |
| v0.4 Knowledge | RAG és PostgreSQL + pgvector | Kész |
| v0.5 Memory | Rövid és hosszú távú memória | Kész |
| v0.6 Agent | Eszközhívások, PowerShell és Git | Tervezett |
| v0.7 Workflow UI | n8n-szerű vizuális folyamatépítő | Tervezett |
| v0.8 Automation Runtime | Workflow futtatás, naplózás és jóváhagyások | Tervezett |
| v1.0 Stable | Stabil, dokumentált offline AI-platform | Tervezett |

## v0.1 Foundation

Elkészült:

- Git repository, feature branch és pull request munkafolyamat;
- projektstruktúra és architekturális dokumentáció;
- FastAPI, Uvicorn és Pydantic Settings alap;
- strukturált naplózás;
- `/`, `/health` és `/version` végpont;
- `uv` környezet és lockfájl;
- pytest, Ruff és mypy ellenőrzés;
- GitHub Actions Ubuntu 24.04 / Python 3.12 alatt;
- Apache-2.0 projektlicenc és licencleltár;
- Hyper-V Generation 2 Ubuntu Server 24.04.4 VM;
- SSH-kulcsos adminisztráció és UFW tűzfal;
- backend telepítése és quality ellenőrzése a saját Ubuntu VM-en;
- újraindítás után automatikusan induló `systemd` szolgáltatás;
- hordozható, korlátozott jogosultságú systemd egység a repositoryban;
- dedikált `kelvin` felhasználós `/opt` telepítés üzemeltetési ellenőrzése.

Későbbi üzemeltetési továbbfejlesztések:

- a VM DHCP-címének tartós foglalása;
- offline Python csomag-előkészítés és ellenőrző összegek;
- mentési és visszaállítási helyek dokumentálása.

Elfogadási feltétel: a dokumentált Ubuntu VM újra létrehozható, a backend
szolgáltatásként elindul, és futás közben nem igényel internetet.

## v0.2 Runtime

Elkészült ezen az ágon:

- általános LLM-port;
- Ollama adapter;
- konfigurálható modell, runtime URL és timeout;
- egységes provider-, elérhetőségi és válaszhibák;
- `/ready` végpont runtime- és modell-ellenőrzéssel;
- mockolt unit tesztek és opcionális élő integrációs ellenőrzés;
- helyi Windows → Ollama kapcsolat ellenőrzése;
- Ubuntu VM → Windows Ollama end-to-end kapcsolat;
- Gemma 4 E4B, 8.0B, Q4_K_M modellválasztás;
- `ollama ps` méréssel igazolt 100% GPU-feldolgozás.

Ellenőrzött end-to-end runtime:

- Windows 11 host;
- Ollama runtime;
- Gemma 4 E4B, 8.0B, Q4_K_M;
- Ubuntu VM-en futó Kelvin backend;
- sikeres generálás és readiness ellenőrzés;
- AMD Radeon RX 6650 XT, `ollama ps` szerint 100% GPU;
- 4096 tokenes context length.

Elfogadási feltételek ellenőrzése:

- [x] a modell konfigurációból cserélhető;
- [x] a backend eléri a hoston futó Ollama API-t;
- [x] az API érthető állapotot ad akkor is, ha az Ollama nem érhető el.

## v0.3 Conversation

Elkészült ezen az ágon:

- `POST /api/v1/chat` nem streamelt végpont;
- `POST /api/v1/chat/stream` SSE streaming végpont;
- szerver által létrehozott UUID sessionazonosító;
- cserélhető `SessionStore` port és első memóriabeli adapter;
- alkalmazási `ChatService`, amely elkülönül a FastAPI route-tól;
- többfordulós kontextusablak-kezelés;
- párhuzamos sessionmódosítás kezelése;
- stabil 404, 409, 422, 502 és 503 API-válaszok;
- unit, API-szerződés és élő többfordulós modellteszt;
- Ubuntu VM-telepítés és end-to-end többfordulós ellenőrzés;
- elfogadott SSE streaming szerződés;
- elfogadott minimális frontendarchitektúra;
- minimális, framework nélküli chat UI a `/ui` útvonalon;
- frontend streaming válaszfeldolgozás;
- konfigurálható asszisztens rendszerprompt;
- Windows fejlesztői és Ubuntu production validáció.

Elfogadási feltétel: új és meglévő sessionben is folytatható a beszélgetés,
az ismeretlen session és modellhiba stabil HTTP-választ ad, a streaming
pedig megszakítható anélkül, hogy félkész fordulót mentene.

Eredmény: a v0.3 elfogadási feltételei teljesültek. A sessiontár még
folyamatmemóriában él; perzisztens session és hosszú távú memória a v0.5
része lesz.

## v0.4 Knowledge

Elkészült ezen az ágon:

- PostgreSQL 16 + pgvector alapú tudástár;
- kézzel olvasható SQL séma `knowledge_*` táblákkal;
- `.txt`, `.md` és `.markdown` dokumentumbetöltő;
- determinisztikus paragraph/Markdown heading alapú chunkolás;
- `nomic-embed-text` embedding adapter Ollamán keresztül;
- PostgreSQL repository dokumentumokhoz, chunkokhoz, embeddingekhez és kereséshez;
- `kelvin-import-document` CLI dokumentumimporthoz;
- `kelvin-search-knowledge` CLI szemantikus kereséshez;
- konfigurálható RAG chat-kontekstus;
- VM-en validált import, embedding, pgvector keresés és chat RAG.

Későbbi bővítések:

- PDF és DOCX feldolgozás;
- webes dokumentumfeltöltés;
- dokumentum törlés és újraindexelés;
- fejlettebb ranking/reranking;
- források strukturált visszaadása az API-válaszban.

Elfogadási feltétel: egy indexelt dokumentumból visszakeresett válasz
ellenőrizhető forráshivatkozást tartalmaz.

Első tervezési dokumentum: [v0.4 Knowledge adatmodell-terv](knowledge-data-model.md).

Infrastruktúra-terv: [PostgreSQL + pgvector telepítési terv](postgresql-pgvector.md).

VM-validáció: PostgreSQL 16.14 és pgvector 0.6.0 telepítve, lokális
adatbázis-kapcsolat és Kelvin API újraindítás ellenőrizve.

Knowledge séma: az első `knowledge_*` táblák és a HNSW pgvector index VM-en
validálva.

Kézi RAG adatpróba: dummy embeddingekkel a pgvector cosine distance keresés a
várt chunkot rangsorolta első helyre.

Embedding modell: első jelöltként a `nomic-embed-text` lett kiválasztva;
Ollama alatt mért embedding dimenziója `768`, ami illeszkedik az aktuális
pgvector sémához.

Valódi embeddinges próba: a `nomic-embed-text` query embedding és a pgvector
cosine keresés a PostgreSQL/pgvector chunkot rangsorolta első helyre.

Python kapcsolat: `KELVIN_DATABASE_URL` konfiguráció és külön
`/ready/database` readiness végpont készül PostgreSQL ellenőrzéshez.

Production validáció:

- a VM-en futó Kelvin API `/ready/database` végpontja
  `{"status":"ready","provider":"postgresql"}` választ adott;
- `kelvin-import-document` sikeresen importált egy Markdown dokumentumot a
  `manual_test` collectionbe;
- az import 3 chunkot és 3 darab `nomic-embed-text` embeddinget mentett;
- mindhárom embedding dimenziója `768`;
- `kelvin-search-knowledge` a "Hol fut az Ollama?" kérdésre a `Runtime` chunkot
  rangsorolta első helyre;
- RAG bekapcsolása után a chat válasz már a tudásbázisban tárolt információt
  használta: az Ollama a Windows hoston fut.

Megfigyelés: a jelenlegi Gemma modell magyar válaszminősége néha töredezett.
Ez nem RAG-funkcionális hiba, hanem modell/prompt finomítási feladat, amelyet
v0.4 után külön érdemes kezelni.

## v0.5 Memory

Elkészült:

- típusos memória domain modell;
- PostgreSQL alapú `memory_items` és `memory_embeddings` séma;
- PostgreSQL memory repository;
- alkalmazási `MemoryService`;
- `POST /api/v1/memory` kézi memória létrehozásához;
- `GET /api/v1/memory` aktív memóriák listázásához;
- `DELETE /api/v1/memory/{memory_id}` soft delete művelethez;
- aktív `user` memóriák chat kontextusba illesztése;
- nyelvsemleges chat context promptok;
- unit és API contract tesztek;
- Ubuntu VM production validáció.

Elfogadási feltétel: Kelvin képes legalább egy kézzel felvett memóriát
eltárolni, listázni, törölni, majd releváns chat-kontekstusként használni úgy,
hogy a felhasználó számára dokumentált, mit tárol és hogyan törölhető.

Eredmény: a v0.5 első használható memory loopja elkészült és VM-en validált.
Az embedding alapú memory search, a frontend memory panel és az automatikus
memória-jelölt készítés későbbi bővítés.

Részletesen: [v0.5 Memory](memory-design.md).

## v0.6 Agent

- agentciklus és eszközregiszter;
- `kelvin` PowerShell-parancs;
- fájl-, keresési és Git-eszközök;
- szabályozott PowerShell-végrehajtó;
- jóváhagyási módok és auditnapló;
- diffalapú változásellenőrzés.

Elfogadási feltétel: az agent csak a megadott munkakönyvtárban és a
jóváhagyott jogosultságokkal tud állapotot változtatni.

## v0.7 Workflow UI

- n8n-szerű, de Kelvin-specifikus vizuális folyamatépítő;
- workflow definíciók mentése JSON vagy YAML formában;
- alap node-ok:
  - prompt / chat;
  - RAG keresés;
  - fájl beolvasás;
  - HTTP kérés;
  - shell / PowerShell előkészítés jóváhagyási ponttal;
- manuális workflow futtatás;
- egyszerű futási eredmény és hibanapló megjelenítése.

Elfogadási feltétel: a felhasználó webes felületen össze tud rakni egy egyszerű
workflow-t, amely legalább egy prompt/RAG lépést és egy fájl- vagy HTTP-lépést
tartalmaz, majd kézzel el tudja indítani.

## v0.8 Automation Runtime

- workflow futtatómotor;
- node input/output adatátadás;
- futási naplók és hibák tárolása;
- biztonságos jóváhagyási pontok veszélyes műveletek előtt;
- alap retry és megszakítás;
- későbbi ütemezés előkészítése.

Elfogadási feltétel: egy mentett workflow újrafuttatható, a futás eredménye
visszanézhető, és a potenciálisan veszélyes műveletek nem futnak le jóváhagyás
nélkül.

## Post-1.0 opcionális Voice

- Whisper beszédfelismerő adapter;
- Piper TTS adapter;
- hangfolyam és megszakítás;
- eszközválasztás és késleltetési mérés.

A hangvezérlés kikerült az 1.0 előtti fő útvonalból, mert jelenleg nincs
mikrofon a fejlesztői gépen, és a projekt számára értékesebb irány a vizuális
automatizáció.

## v1.0 Stable

- stabil és verziózott API;
- dokumentált telepítés, frissítés, mentés és visszaállítás;
- offline kiadási és licencleltár-folyamat;
- biztonsági és jogosultsági alapértelmezések;
- ütemezhető, korlátozott automatizálás;
- teljes regressziós és üzemeltetési ellenőrzés.
