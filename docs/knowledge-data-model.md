# v0.4 Knowledge adatmodell-terv

Ez a dokumentum a v0.4 Knowledge mérföldkő első adatmodelljét írja le.

A cél nem az, hogy azonnal tökéletes RAG-rendszert építsünk, hanem hogy
átlátható, bővíthető PostgreSQL + pgvector alapot hozzunk létre.

## Mit jelent itt a tudástár?

A tudástár azoknak a dokumentumoknak és dokumentumrészleteknek a gyűjteménye,
amelyekből Kelvin később válaszolni tud.

Példa:

```text
docs/server-notes.md
docs/project-decisions.md
manuals/router-setup.txt
```

Ezeket nem egyben adjuk oda a modellnek, hanem kisebb darabokra bontjuk. Ezek a
darabok lesznek a `chunkok`.

## Alapfogalmak

| Fogalom | Jelentés |
| --- | --- |
| Dokumentum | Egy eredeti fájl vagy tudásforrás |
| Chunk | A dokumentum kisebb, kereshető részlete |
| Embedding | Egy szövegrész numerikus, vektoros lenyomata |
| Metadata | Kiegészítő adat, például fájlnév, útvonal, oldalszám |
| Collection | Logikai csoport, például `project_docs` vagy `personal_notes` |

## Miért kell darabolni?

Egy teljes dokumentum túl hosszú lehet a modell context ablakához. A RAG lényege
nem az, hogy mindent betöltünk a modellbe, hanem hogy kevés, releváns részletet
keresünk ki.

Kezdő beállításnak:

```text
chunk size: 500–800 token
top_k: 3
max RAG context: kb. 2000 token
```

Ez óvatos érték a jelenlegi 8 GB VRAM-os környezethez.

## Tervezett táblák

### `knowledge_collections`

Logikai tudásgyűjtemények.

Példák:

- `project_docs`
- `home_lab`
- `personal_notes`

Tervezett mezők:

| Mező | Típus | Miért kell? |
| --- | --- | --- |
| `id` | UUID | Stabil belső azonosító |
| `name` | text | Emberi és API-s név |
| `description` | text/null | Rövid magyarázat |
| `created_at` | timestamp | Audit és rendezés |
| `updated_at` | timestamp | Változások követése |

### `knowledge_documents`

Az eredeti dokumentumokat tartja nyilván.

Tervezett mezők:

| Mező | Típus | Miért kell? |
| --- | --- | --- |
| `id` | UUID | Dokumentumazonosító |
| `collection_id` | UUID | Melyik tudásgyűjteményhez tartozik |
| `source_uri` | text | Fájlútvonal vagy későbbi forrásazonosító |
| `title` | text/null | Emberi cím |
| `content_hash` | text | Változásdetektálás és deduplikáció |
| `mime_type` | text | Például `text/markdown` |
| `metadata` | jsonb | Rugalmas extra adatok |
| `created_at` | timestamp | Mikor került be |
| `updated_at` | timestamp | Mikor változott |

Miért fontos a `content_hash`?

Ha ugyanazt a fájlt újra indexeljük, felismerhető, hogy valóban változott-e.
Így nem építjük újra feleslegesen az embeddingeket.

### `knowledge_chunks`

A dokumentum kereshető részleteit tartalmazza.

Tervezett mezők:

| Mező | Típus | Miért kell? |
| --- | --- | --- |
| `id` | UUID | Chunkazonosító |
| `document_id` | UUID | Eredeti dokumentum |
| `chunk_index` | integer | Sorrend a dokumentumon belül |
| `content` | text | Maga a kereshető szövegrész |
| `token_count` | integer/null | Context-tervezéshez |
| `metadata` | jsonb | Oldalszám, fejezet, címsor, sorok |
| `created_at` | timestamp | Audit |

Miért külön tábla?

Mert a keresés nem dokumentumokra, hanem dokumentumrészletekre történik. A modell
is ezeket a részleteket kapja meg.

### `knowledge_embeddings`

A chunkok vektorait tartalmazza.

Tervezett mezők:

| Mező | Típus | Miért kell? |
| --- | --- | --- |
| `id` | UUID | Embedding rekord azonosító |
| `chunk_id` | UUID | Melyik chunkhoz tartozik |
| `embedding_model` | text | Melyik embedding modell készítette |
| `embedding_dimension` | integer | Vektor mérete |
| `embedding` | vector | pgvector mező |
| `created_at` | timestamp | Mikor készült |

Miért kell eltárolni az embedding modellt?

Ha később modellt váltunk, tudnunk kell, melyik embedding melyik modellből
származik. Különböző embedding modellek vektorai nem feltétlenül keverhetők
biztonságosan.

Első embedding modell:

```text
nomic-embed-text
```

A modellt Ollamán keresztül futtatjuk. A 2026-06-29-i helyi mérés alapján egy
tesztszövegre `768` dimenziós embeddinget adott, ezért kompatibilis az első
`embedding vector(768)` PostgreSQL sémával.

Későbbi összehasonlításra jelölt modellek:

- `mxbai-embed-large`;
- `all-minilm`.

## Első keresési folyamat

```text
felhasználói kérdés
→ kérdés embedding készítése
→ pgvector hasonlóságkeresés a knowledge_embeddings táblában
→ top 3 chunk lekérése
→ chunkok forrással együtt bekerülnek a modell promptjába
→ Kelvin válaszol és forrást jelöl
```

## Forráshivatkozás

A v0.4 egyik fontos célja, hogy Kelvin ne csak válaszoljon, hanem meg is mondja,
mire támaszkodott.

Példa válasz:

```text
Kelvin productionben a 8000-es porton fut.

Forrás:
- docs/installation.md
```

Később pontosítható:

```text
Forrás:
- docs/installation.md, "Backend indítása" szakasz
- manuals/router.md, 42. sor
```

## Amit most szándékosan nem építünk bele

Az első v0.4 adatmodell nem tartalmaz:

- PDF/DOCX feldolgozást;
- jogosultságkezelést dokumentumszinten;
- automatikus webes crawlingot;
- hosszú távú személyes memóriát;
- többfelhasználós adatleválasztást;
- bonyolult ranking pipeline-t.

Ezek későbbi lépések. Most a cél: `.txt` és `.md` dokumentumokból működő,
érthető RAG-alap.

## Első implementációs sorrend

1. PostgreSQL + pgvector telepítés dokumentálása az Ubuntu VM-en.
2. Adatbázis-kapcsolat konfigurációja `KELVIN_DATABASE_URL` alapján.
3. Migrációs stratégia kiválasztása.
4. Táblák létrehozása.
5. `.txt` és `.md` dokumentumbetöltő.
6. Determinisztikus chunkoló.
7. Embedding port és első adapter.
8. Keresési port és PostgreSQL + pgvector adapter.
9. Chat prompt bővítése top 3 releváns chunkkal.
10. Források visszaadása az API-válaszban.

## Nyitott kérdések

- Melyik offline embedding modellt használjuk elsőként?
- Legyen-e külön API dokumentumfeltöltésre, vagy induljunk helyi mappaindexeléssel?
- Milyen migrációs eszközt használjunk: Alembic vagy egyszerű SQL fájlok?
- A v0.4-ben csak nem streamelt RAG-választ adjunk, vagy a streaming válaszba is
  építsük be a forrásokat?

## Első SQL séma

Az első kézzel olvasható SQL séma itt található:

```text
infrastructure/sql/001_create_knowledge_schema.sql
```

Szándékosan egyszerű SQL fájlként indulunk. Így látható, hogy pontosan milyen
táblák, constraint-ek és indexek jönnek létre, mielőtt Alembicet vagy más
migrációs eszközt vezetnénk be.

A séma VM-en validálva lett PostgreSQL 16.14 és pgvector 0.6.0 alatt.

Kézi dummy embeddingekkel a cosine distance alapú keresés is validálva lett:
a keresés a vektorosan legközelebbi chunkot hozta vissza első találatként.

Az első valódi embedding modellként a `nomic-embed-text` lett kiválasztva, mert
Ollamával lokálisan futtatható és mért dimenziója `768`.

Valódi `nomic-embed-text` embeddinggel a PostgreSQL/pgvector chunk jelentősen
kisebb cosine distance értéket kapott, mint a nem releváns API chunk, ezért az
első end-to-end embeddinges keresési próba sikeres.
