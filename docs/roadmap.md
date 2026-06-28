# Fejlesztési roadmap

Minden mérföldkő külön jóváhagyási pont. Egy mérföldkő akkor kész, ha a
funkció, a teszt, a dokumentáció és az üzemeltetési ellenőrzés is elkészült.

## Áttekintés

| Verzió | Cél | Állapot |
| --- | --- | --- |
| v0.1 Foundation | Repository, CI, dokumentáció, Hyper-V, Ubuntu | Folyamatban |
| v0.2 Runtime | FastAPI, Ollama és Gemma | Folyamatban |
| v0.3 Conversation | Chat API, streaming és sessionkezelés | Tervezett |
| v0.4 Knowledge | RAG és ChromaDB | Tervezett |
| v0.5 Memory | Rövid és hosszú távú memória | Tervezett |
| v0.6 Agent | Eszközhívások, PowerShell és Git | Tervezett |
| v0.7 Voice | Whisper és Piper | Tervezett |
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

Még szükséges:

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

Még szükséges:

- v0.2 verzióemelés és mérföldkőlezárás.

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

- verziózott chat végpont;
- munkamenet-azonosítás;
- kontextusablak-kezelés;
- tokenenkénti válaszstreamelés;
- megszakítás és API-szerződés tesztelése.

## v0.4 Knowledge

- szöveg- és Markdown-betöltő;
- darabolási stratégia;
- embedding-port és adapter;
- ChromaDB adapter;
- forrásmegjelölés;
- később PDF és DOCX.

Elfogadási feltétel: egy indexelt dokumentumból visszakeresett válasz
ellenőrizhető forráshivatkozást tartalmaz.

## v0.5 Memory

- elkülönített rövid és hosszú távú memóriatár;
- mentési és visszakeresési szabályok;
- deduplikáció;
- felhasználói listázás és törlés;
- összefoglalás és elévülés.

## v0.6 Agent

- agentciklus és eszközregiszter;
- `kelvin` PowerShell-parancs;
- fájl-, keresési és Git-eszközök;
- szabályozott PowerShell-végrehajtó;
- jóváhagyási módok és auditnapló;
- diffalapú változásellenőrzés.

Elfogadási feltétel: az agent csak a megadott munkakönyvtárban és a
jóváhagyott jogosultságokkal tud állapotot változtatni.

## v0.7 Voice

- Whisper beszédfelismerő adapter;
- Piper TTS adapter;
- hangfolyam és megszakítás;
- eszközválasztás és késleltetési mérés.

## v1.0 Stable

- stabil és verziózott API;
- dokumentált telepítés, frissítés, mentés és visszaállítás;
- offline kiadási és licencleltár-folyamat;
- biztonsági és jogosultsági alapértelmezések;
- ütemezhető, korlátozott automatizálás;
- teljes regressziós és üzemeltetési ellenőrzés.
