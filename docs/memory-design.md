# v0.5 Memory terv

## Cél

A v0.5 célja, hogy Kelvin ne csak az aktuális beszélgetésben tudjon kontextust
kezelni, hanem szabályozott, törölhető és auditálható memóriát is kapjon.

Ez nem ugyanaz, mint a v0.4 RAG:

- a RAG dokumentumokból és jegyzetekből keres vissza;
- a memória Kelvin működése közben keletkező, felhasználóhoz és projekthez
  kapcsolódó tényeket, preferenciákat és összefoglalókat tárol.

## Alapelvek

1. **A memória legyen explicit és törölhető.**
   Kelvin ne gyűjtsön kontroll nélkül személyes adatokat.

2. **A memória ne legyen rejtett igazságforrás.**
   Ha egy válasz memóriára támaszkodik, később legyen visszakövethető, miből.

3. **A memória legyen típusos.**
   Egy preferencia, egy projektbeállítás és egy ideiglenes beszélgetési tény nem
   ugyanaz.

4. **A memória legyen cserélhető adapter mögött.**
   Az alkalmazási logika portokon keresztül használja, ne közvetlen SQL-en.

5. **A biztonság fontosabb, mint az automatikus okosság.**
   Az első verzió inkább legyen óvatos, mint túlzottan “mindent megjegyző”.

## Memóriafajták

### Session history

Már létezik v0.3 óta memóriabeli session formában.

Feladata:

- többfordulós beszélgetés kontextusa;
- aktuális chat folytonossága;
- rövid kontextusablak biztosítása az LLM számára.

Korlát:

- jelenleg process memory;
- újraindítás után elveszik;
- nem hosszú távú memória.

v0.5-ben eldöntendő, hogy a sessionök PostgreSQL-be kerüljenek-e, vagy külön
maradjanak a hosszú távú memóriától.

### Short-term memory

Rövid életű, beszélgetéshez vagy feladathoz kötött emlék.

Példák:

- “Ebben a beszélgetésben a v0.5 Memory terven dolgozunk.”
- “A felhasználó most angol tesztkérdéseket szeretne Kelvinhez.”
- “A jelenlegi branch: `codex/docs/v0.5-memory-plan`.”

Jellemzők:

- automatikusan létrejöhet;
- lejárati ideje van;
- felülírható vagy törölhető;
- nem feltétlenül kerül embeddingbe.

### Long-term memory

Tartós, felhasználó vagy projekt szintű memória.

Példák:

- “A felhasználó neve Zoltán.”
- “A felhasználó lépésről lépésre szeret tanulni.”
- “Kelvin Ubuntu VM-en fut, az Ollama Windows hoston.”
- “A projekt Apache-2.0 licencet használ.”

Jellemzők:

- csak jóváhagyott szabályok szerint jöhet létre;
- listázható;
- törölhető;
- forrása és létrehozási ideje tárolt;
- később embeddinggel is kereshető.

### Knowledge / RAG

Nem memória, hanem dokumentumtár.

Példák:

- `docs/installation.md`
- projekt döntési dokumentumok;
- kézzel importált Markdown jegyzetek.

Miért külön:

- dokumentumforrása van;
- chunkokra és embeddingekre bomlik;
- nem személyes preferencia;
- újraépíthető az eredeti dokumentumokból.

## Első adatmodell-javaslat

Az első SQL séma:

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

Az első verzióban hasznos lehet audit és hibakeresés miatt. Később kellhet
végleges törlés is, főleg személyes adatoknál.

### `memory_embeddings`

| Mező | Típus | Jelentés |
| --- | --- | --- |
| `id` | UUID | Embedding rekord |
| `memory_id` | UUID | Kapcsolódó memória |
| `embedding_model` | text | Melyik embedding modell készítette |
| `embedding_dimension` | integer | Vektor mérete |
| `embedding` | vector(768) | pgvector embedding |
| `created_at` | timestamptz | Létrehozás ideje |

Ez hasonló a `knowledge_embeddings` táblához, de szándékosan külön van.

## Első API / CLI ötletek

v0.5 első körben lehet admin CLI fókuszú:

```bash
kelvin-memory-add --kind preference "The user prefers step-by-step explanations."
kelvin-memory-list
kelvin-memory-delete <memory-id>
kelvin-memory-search "How should I explain things?"
```

Később API:

- `GET /api/v1/memory`
- `POST /api/v1/memory`
- `DELETE /api/v1/memory/{id}`
- `POST /api/v1/memory/search`

## Chat integráció

Első chat integráció:

```text
felhasználói üzenet
→ releváns long-term memory keresés
→ releváns RAG knowledge keresés
→ system kontextus összeállítása
→ LLM válasz
```

Fontos: a memória és a RAG kontextus külön blokk legyen a promptban.

Példa:

```text
Relevant user memory:
- The user prefers step-by-step explanations.

Relevant project knowledge:
- Ollama runs on the Windows host.
```

## Mit nem csinálunk v0.5 első körben?

- nincs automatikus személyes adatgyűjtés kontroll nélkül;
- nincs többfelhasználós jogosultsági rendszer;
- nincs bonyolult memory consolidation pipeline;
- nincs automatikus “mindent jegyezz meg” mód;
- nincs végleges agent-autonóm memóriaírás jóváhagyás nélkül.

## Elfogadási feltételek

v0.5 akkor tekinthető késznek, ha:

- van dokumentált memória-adatmodell;
- PostgreSQL-ben létrejönnek az első `memory_*` táblák;
- memóriaelem kézzel létrehozható;
- memóriaelem listázható;
- memóriaelem törölhető vagy soft-delete-elhető;
- memóriaelem embeddinggel kereshető;
- chat válasz előtt Kelvin képes releváns memóriát kontextusként használni;
- a felhasználó számára dokumentált, mit tárolhat Kelvin és hogyan törölhető.

## Nyitott kérdések

- Legyen-e már v0.5-ben perzisztens session store?
- A long-term memory létrehozása első körben legyen csak kézi?
- Kell-e külön `project` memória és `user` memória?
- Mikor törlődjön automatikusan a short-term memory?
- Mely memóriafajták kapjanak embeddinget?
