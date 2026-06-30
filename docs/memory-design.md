# v0.5 Memory

## Cél

A v0.5 célja az volt, hogy Kelvin szabályozott, törölhető és auditálható
hosszú távú memóriát kapjon.

Ez nem ugyanaz, mint a v0.4 RAG:

- a RAG dokumentumokból és jegyzetekből keres vissza;
- a memória Kelvin működése közben keletkező, felhasználóhoz vagy projekthez
  kapcsolódó tényeket, preferenciákat és összefoglalókat tárol.

## Megvalósult állapot

Elkészült:

- típusos memória domain modell;
- PostgreSQL + pgvector alapú `memory_items` és `memory_embeddings` séma;
- PostgreSQL memory repository;
- alkalmazási `MemoryService`;
- `POST /api/v1/memory` memória létrehozásához;
- `GET /api/v1/memory` aktív memóriák listázásához;
- `DELETE /api/v1/memory/{memory_id}` soft delete művelethez;
- aktív `user` memóriák chat kontextusba illesztése;
- nyelvsemleges chat context promptok;
- unit és API contract tesztek;
- Ubuntu VM production validáció.

Tudatosan későbbre maradt:

- automatikus memória-kivonás beszélgetésekből;
- embedding alapú memory search;
- memória szerkesztése API-n keresztül;
- frontend memory panel;
- perzisztens chat session store;
- többfelhasználós jogosultsági modell.

## Alapelvek

1. **A memória explicit és törölhető.**
   Kelvin ne gyűjtsön kontroll nélkül személyes adatokat.

2. **A memória nem rejtett igazságforrás.**
   A memória API-n keresztül listázható, így visszanézhető, mit tárol Kelvin.

3. **A memória típusos.**
   Egy preferencia, egy projektbeállítás és egy feladatállapot nem ugyanaz.

4. **A memória adapter mögött él.**
   Az alkalmazási logika portokon keresztül használja, nem közvetlen SQL-en.

5. **A biztonság fontosabb, mint az automatikus okosság.**
   Az első verzió kézi és kontrollálható memóriaírást támogat.

## Memória típusok

### Session history

Már v0.3 óta létezik folyamatmemóriában.

Feladata:

- többfordulós beszélgetés kontextusa;
- aktuális chat folytonossága;
- rövid kontextusablak biztosítása az LLM számára.

Korlát:

- jelenleg process memory;
- újraindítás után elveszik;
- nem hosszú távú memória.

### Long-term memory

Tartós, felhasználó vagy projekt szintű memória.

Példák:

- `The user prefers step-by-step explanations.`
- `Kelvin runs on the Ubuntu VM.`
- `Ollama runs on the Windows host.`
- `The project uses Apache-2.0.`

Jellemzők:

- API-n keresztül létrehozható;
- listázható;
- soft delete-elhető;
- forrása és létrehozási ideje tárolt;
- később embeddinggel is kereshető.

### Knowledge / RAG

Nem memória, hanem dokumentumtár.

Példák:

- `docs/installation.md`;
- projekt döntési dokumentumok;
- kézzel importált Markdown jegyzetek.

Miért külön:

- dokumentumforrása van;
- chunkokra és embeddingekre bomlik;
- újraépíthető az eredeti dokumentumokból;
- nem személyes preferencia.

## Adatmodell

Az SQL séma:

```text
infrastructure/sql/002_create_memory_schema.sql
```

### `memory_items`

| Mező | Típus | Jelentés |
| --- | --- | --- |
| `id` | UUID | Memória azonosító |
| `scope` | text | `user`, `project`, `session`, `system` |
| `kind` | text | `preference`, `fact`, `summary`, `task_state` |
| `content` | text | A megjegyzett állítás |
| `source` | text | Honnan származik |
| `confidence` | numeric | Mennyire biztos az állítás |
| `metadata` | jsonb | Kiegészítő adatok |
| `created_at` | timestamptz | Létrehozás ideje |
| `updated_at` | timestamptz | Utolsó módosítás |
| `expires_at` | timestamptz nullable | Lejárat |
| `deleted_at` | timestamptz nullable | Soft delete |

Miért soft delete?

Az első verzióban hasznos audit és hibakeresés miatt. Később kellhet végleges
törlés is, főleg személyes adatoknál.

### `memory_embeddings`

| Mező | Típus | Jelentés |
| --- | --- | --- |
| `id` | UUID | Embedding rekord |
| `memory_id` | UUID | Kapcsolódó memória |
| `embedding_model` | text | Melyik embedding modell készítette |
| `embedding_dimension` | integer | Vektor mérete |
| `embedding` | vector(768) | pgvector embedding |
| `created_at` | timestamptz | Létrehozás ideje |

Az embedding tábla elkészült, de a v0.5-ben a chat még egyszerű, legfrissebb
aktív memóriákon alapuló kontextust használ. Az embedding alapú memory search
későbbi bővítés.

## API

### Memória létrehozása

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/memory \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "user",
    "kind": "preference",
    "content": "The user prefers step-by-step explanations.",
    "source": "manual-test",
    "confidence": 1.0,
    "metadata": {
      "topic": "communication"
    }
  }'
```

### Aktív memóriák listázása

```bash
curl -s "http://127.0.0.1:8000/api/v1/memory?scope=user&kind=preference&limit=5"
```

### Memória törlése

```bash
curl -i -X DELETE "http://127.0.0.1:8000/api/v1/memory/<memory-id>"
```

Sikeres törlés esetén az API `204 No Content` választ ad. A rekord soft delete
állapotba kerül, ezért a későbbi aktív listázásban már nem jelenik meg.

## Chat integráció

Az első chat integráció egyszerű és kontrollált:

```text
felhasználói üzenet
→ aktív user memóriák lekérése
→ RAG context lekérése, ha engedélyezett
→ system context összeállítása
→ LLM válasz
```

A memória system üzenetként jut el a modellhez, de nem kerül bele a chat
session historyba.

Első körben Kelvin:

- csak aktív `user` memóriákat használ;
- alapértelmezetten maximum 5 memóriát ad a promptba;
- nem végez embedding alapú memory searchöt;
- nem ment automatikusan új memóriát beszélgetésekből.

## Production validáció

Ubuntu VM-en ellenőrizve:

- a `memory_items` és `memory_embeddings` táblák létrejöttek;
- kézi memória beszúrható volt SQL-ből;
- `POST /api/v1/memory` sikeresen létrehozott memóriát;
- `GET /api/v1/memory` visszaadta az aktív memóriákat;
- `DELETE /api/v1/memory/{id}` `204 No Content` választ adott;
- törlés után az adott memória már nem jelent meg az aktív listában;
- a chat válaszban érződött a `step-by-step` felhasználói preferencia;
- nyelvsemleges prompt javítás után az angol kérdés angol, a magyar kérdés
  magyar választ kapott.

## Elfogadási feltételek

- [x] dokumentált memória-adatmodell;
- [x] PostgreSQL `memory_*` táblák;
- [x] memóriaelem kézzel létrehozható;
- [x] memóriaelem listázható;
- [x] memóriaelem soft delete-elhető;
- [x] chat válasz előtt Kelvin képes aktív memóriát kontextusként használni;
- [x] a felhasználó számára dokumentált, mit tárolhat Kelvin és hogyan
  törölhető;
- [ ] memóriaelem embeddinggel kereshető.

Az embedding alapú memory search a v0.5 utáni bővítések közé került, mert az
első használható memory loophoz elegendő volt a kézi memória és a legfrissebb
aktív user memóriák promptba illesztése.

## Következő bővítések

- konfigurálható `KELVIN_MEMORY_CONTEXT_LIMIT`;
- `POST /api/v1/memory/search`;
- memory embedding mentése;
- frontend memory panel;
- memória szerkesztése;
- automatikus memória-jelölt készítés LLM-mel;
- felhasználói jóváhagyás memória mentése előtt;
- clarification policy az agent mérföldkő részeként.
