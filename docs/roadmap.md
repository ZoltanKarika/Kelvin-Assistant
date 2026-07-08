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
| v0.6 Agent | Eszközhívások, PowerShell és Git | Kész |
| v0.7 Safe n8n Foundation | Külön automation VM és biztonságos Kelvin API-integráció | Kész |
| v0.8 AI Security & Integration Hardening | AI Firewall, audit és bővített online AI-integrációk | Kész |
| v0.9 UI & Email Notifications | Helyi kezelőfelület és email értesítések | Kész |
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

- agent domain modellek és explicit állapotgép;
- szolgáltatófüggetlen, strukturált `AgentPlanner` port;
- természetes nyelvű célból clarify, tool vagy complete döntés;
- célzott visszakérdezés hiányos vagy kockázatos kéréseknél;
- strukturált eszközregiszter és determinisztikus policy engine;
- `kelvin` PowerShell-kliens a Windows hoston;
- fájl-, keresési és Git-eszközök;
- szabályozott, hostoldali PowerShell-végrehajtás;
- read, write, destructive és privileged kockázati szintek;
- felhasználói jóváhagyás állapotváltoztató műveletek előtt;
- munkakönyvtár-korlátozás;
- diffalapú változásellenőrzés;
- megszakítás, lépésszámkorlát és auditnapló.

Elfogadási feltétel: az agent csak a megadott munkakönyvtárban és a
jóváhagyott jogosultságokkal tud állapotot változtatni. Egyértelmű olvasási
feladatnál nem kérdez vissza feleslegesen, kétértelmű vagy kockázatos kérésnél
viszont pontosítást kér.

Részletes terv: [v0.6 Agent architektúra](agent-architecture.md).

Production validáció:

- a Windows `kelvin` kliens természetes nyelvű célból a `git.status` eszközt
  választotta és helyben végrehajtotta;
- a tool eredménye observationként visszakerült a plannerhez, amely egy második
  körben összefoglalta az eredményt;
- a futás PostgreSQL-ben `completed` állapotban, egy végrehajtott lépéssel
  jelent meg;
- `Ctrl+C` közben a kliens meghívta a cancel API-t, és a futás PostgreSQL-ben
  `cancelled` állapotba került;
- a korábbi aktív tesztfutások szabályosan lezárásra kerültek;
- Ruff, formázás és mypy ellenőrzés sikeres;
- a teljes Windows tesztcsomag `308 passed` eredménnyel futott le;
- a folyamat helyi Windows hostot, Ubuntu VM-et, Ollamát és PostgreSQL-t
  használt, külső AI- vagy felhőszolgáltatás nélkül.

Eredmény: a v0.6 elfogadási feltételei teljesültek.

## v0.7 Safe n8n Foundation

- self-hosted n8n Community Edition egy külön Ubuntu automation VM-en,
  Docker Compose alatt;
- rögzített konténerverzió, tartós volume és külön mentett
  `N8N_ENCRYPTION_KEY`;
- kizárólag a Windows host vagy a megbízható helyi hálózat felől elérhető,
  hitelesített n8n felület;
- dokumentált HTTP-szerződés az n8n és Kelvin verziózott API-ja között;
- képességalapú Kelvin API-jogosultságok, külön read, memory write,
  agent execute, agent write és agent approve scope-pal;
- alapértelmezetten read-only Kelvin credential az n8n kutató workflow-khoz;
- első Kelvin-integráció a beépített HTTP Request node-dal, saját node
  fejlesztése nélkül;
- első kutató workflow engedélyezett RSS-, API- és webes forrásokkal, egyetlen
  online szöveges AI-szolgáltatóval;
- forrás URL, lekérési idő, oldal-, idő- és költségkorlát megőrzése;
- minimum AI Firewall: a külső tartalom adatként kezelése, prompt injection
  elkülönítése, titokminták maszkolása és webes szövegből közvetlen tool-hívás
  tiltása;
- workflow- és agentfutás közös korrelációs azonosítója;
- online szolgáltatások kulcsai kizárólag az n8n credential store-ban;
- az offline Kelvin core és az internetet igénylő workflow-k egyértelmű
  elkülönítése.

Az n8n az időzítésekért, online integrációkért, credentialökért és vizuális
workflow-szerkesztésért felel. Kelvin továbbra is a helyi AI-, RAG-, memória-,
agent-, policy- és jóváhagyási szabályok tulajdonosa. Az n8n nem kapja meg az
online szolgáltatások nyers kulcsait továbbító Kelvin-végpontot, és nem
kerülheti meg a Windows `kelvin` kliens helyi jóváhagyását.

Production validáció:

- a külön automation VM-en futó n8n a `docs/ai/v07-guide.md` dokumentáció
  szerint elkészült és a `health_check` workflow sikeresen futott;
- az API-tokenek és a scope-alapú jogosultságkezelés a `v0.7-ai-firewall`
  ágon validálva lett;
- a `v0.7-updater-workflow` ágon elkészült a teljes v1 és v2 pipeline,
  amely RSS-forrásból képes a Gemini API-n keresztül strukturált agent
  feladatot létrehozni és azt a Kelvin API-nak átadni;
- a `v0.7-correlation-id` bevezette a `X-Correlation-ID` fejlécet, amely
  lehetővé teszi az n8n és a Kelvin közötti kérések összekapcsolását;
- a `chore/v0.7-backup-validation` ágon a `docs/backup-restore.md` és
  a `scripts/backup-kelvin-db.sh` mentési és visszaállítási eljárásokat
  dokumentálja és teszteli.

Elfogadási feltételek:

- [x] külön automation VM fut Ubuntu Server 24.04 LTS rendszerrel;
- [x] n8n és saját PostgreSQL-e Docker Compose alatt fut;
- [x] egyik image sem használ `latest` taget;
- [x] n8n felülete csak a megbízható helyi hálózatról érhető el;
- [x] PostgreSQL port nem kerül publikálásra;
- [x] encryption key és adatbázismentés külön visszaállítható;
- [x] Kelvin API token- és scope-alapú hitelesítést használ;
- [x] a kutató workflow csak read-only Kelvin credentialt kap;
- [x] online AI-kulcs nem kerül Kelvinhez, Gitbe vagy workflow-exportba;
- [x] egy hivatkozott fejlesztési javaslatot készítő workflow sikeresen lefut;
- [x] webes prompt injection nem indíthat Kelvin toolt;
- [x] n8n nem kerülheti meg a Windows agent jóváhagyását;
- [x] n8n kiesése mellett Kelvin helyi funkciói működnek;
- [x] reboot, backup és restore ellenőrzése sikeres;
- [x] a telepítéshez használt ideiglenes checkpointok törlésre kerülnek.

## v0.8 AI Security & Integration Hardening

Elkészült:

- [x] teljes AI Security Gateway, közérthető nevén „Firewall for AI”;
- [x] input guard veszélyes szándék, credential-kérés és prompt injection
  felismerésére;
- [x] context guard webes, RAG- és memóriaforrások megbízhatósági határainak
  megőrzésére;
- [x] output guard jelszavak, API-kulcsok, privát kulcsok és connection stringek
  maszkolására;
- [x] determinisztikus tool guard és emberi jóváhagyás megtartása minden író
  művelet előtt;
- [x] biztonsági döntések auditja a tiltott titok naplózása nélkül;
- [x] n8n és Kelvin közötti kulcsrotáció, scope-vizsgálat és visszavonás;
- [x] idempotens kérések, timeout, retry és dokumentált hibautak;
- [x] workflow-, agent- és eszközfutások összekapcsolt auditja;
- [x] engedélyezett workflow-k, források és webhookok allowlistje;
- [x] online kódoló AI csak minimalizált és megtisztított projektkontextussal;
- [x] opcionális képgeneráló és további szöveges AI-szolgáltatók külön,
  minimális jogosultságú credentialökkel;
- [x] saját Kelvin n8n node csak legalább két stabil HTTP-alapú workflow után;
- [x] Kelvin FastAPI konténerizálási próba külön tesztkörnyezetben, a működő
  systemd telepítés megtartása mellett;
- [x] n8n workflow-k exportja és verziózott mentése titkok nélkül;
- [x] PostgreSQL-, Kelvin-, n8n-adatok és az encryption key dokumentált,
  elkülönített mentési és visszaállítási eljárása;
- [x] health check, naplózás és üzemeltetési hibakeresési útmutató.

Elfogadási feltétel: egy rosszindulatú forrásba ágyazott, `.env`, jelszó vagy
API-kulcs kiolvasását kérő utasítás nem válthat ki tool-hívást, a titok nem
jelenhet meg válaszban vagy naplóban, a workflow pedig biztonságosan
újrapróbálható és Kelvin auditadataiig visszakövethető.

## v0.9 UI & Email Notifications

Elkészült:

- [x] használható helyi Kelvin UI futások, jóváhagyások, audit, beállítások és n8n
  állapot megjelenítésére;
- [x] agentfutások listázása státusszal, idővonallal, részletekkel és biztonságosan
  maszkolt tool-kimenetekkel;
- [x] helyi jóváhagyási sor író vagy magas kockázatú műveletekhez;
- [x] auditnapló-keresés és auditbejegyzések összekapcsolása futásokkal,
  korrelációs azonosítókkal és jóváhagyási eseményekkel;
- [x] beállítási felület runtime-, biztonsági, email- és n8n-konfigurációhoz nyers
  titkok megjelenítése nélkül;
- [x] n8n állapotpanel, amely láthatóvá teszi az automation réteg egészségét, de
  n8n kiesése esetén nem blokkolja a helyi Kelvin használatát;
- [x] email értesítés függő jóváhagyásról;
- [x] email értesítés sikeresen befejezett vagy hibával lezárt futásokról;
- [x] napi email összefoglaló futásszámokkal, függő jóváhagyásokkal, fontos audit
  eseményekkel és n8n állapottal;
- [x] Slack, WhatsApp, Matrix és Mattermost chat-integrációk nem részei a v0.9
  mérföldkőnek.

Elfogadási feltétel: Kelvin a helyi UI-ban átláthatóan kezelhető, a felhasználó
látja a futásokat, jóváhagyásokat, auditot, beállításokat és n8n állapotot,
valamint biztonságos email értesítést kap függő jóváhagyásokról, futási
eredményekről és napi összefoglalóról.

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
- container-ready szerverkomponensek, dokumentált natív fallbackkel;
- offline kiadási és licencleltár-folyamat;
- biztonsági és jogosultsági alapértelmezések;
- self-hosted n8n-en keresztül ütemezhető, korlátozott automatizálás;
- dokumentált helyi és opcionális felhős n8n integrációk;
- dokumentált, jogosultságkezelt kétirányú messaging workflow-k;
- teljes regressziós és üzemeltetési ellenőrzés.
