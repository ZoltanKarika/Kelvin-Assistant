# PostgreSQL + pgvector telepítési terv

Ez a dokumentum a v0.4 Knowledge mérföldkő PostgreSQL + pgvector alapját
tervezi meg az Ubuntu Server VM-re.

Először átnézzük és csak utána telepítjük a VM-en.

## Mit telepítünk?

- PostgreSQL: relációs adatbázis dokumentumokhoz, chunkokhoz, metadatahoz és
  későbbi memóriához.
- pgvector: PostgreSQL bővítmény vektoros hasonlóságkereséshez.

Miért kell mindkettő?

- A PostgreSQL önmagában jól kezeli a táblákat, kapcsolatokat és mentést.
- A RAG-hoz viszont embedding vektorok között kell hasonlóságot keresni.
- Ezt a `vector` adattípust és a vektoros indexeket a pgvector adja.

## Miért natív Ubuntu telepítés és nem Docker?

Első körben natív Ubuntu csomagként telepítjük.

Indok:

- jobban látható, hogyan működik az adatbázis;
- illeszkedik a meglévő `systemd`-es Kelvin API telepítéshez;
- tanulási projektnél kevesebb absztrakció;
- egyszerűbb SSH-n, `systemctl`-lel és `journalctl`-lel ellenőrizni;
- később Dockerre még át lehet térni, ha indokolt.

Alternatíva:

- Docker Compose: hordozhatóbb, de most egy plusz réteg lenne az adatbázis
  megértése előtt.

## Tervezett nevek

| Elem | Név |
| --- | --- |
| Linux service | `postgresql` |
| PostgreSQL szerepkör/user | `kelvin` |
| Adatbázis | `kelvin_assistant` |
| Első schema | `public` |
| Kelvin env változó | `KELVIN_DATABASE_URL` |

Kezdeti connection string forma:

```text
KELVIN_DATABASE_URL=postgresql://kelvin:<password>@127.0.0.1:5432/kelvin_assistant
```

A jelszó nem kerülhet Gitbe. Productionben az érték az
`/etc/kelvin-assistant/kelvin.env` fájlba kerül.

## Hálózati döntés

Kezdésként PostgreSQL csak lokálisan figyeljen a VM-en:

```text
127.0.0.1:5432
```

Indok:

- a Kelvin API ugyanazon a VM-en fut;
- nincs szükség Windowsról közvetlen adatbázis-kapcsolatra;
- kisebb támadási felület;
- UFW-n nem kell 5432-es portot nyitni.

Ha később Windowsról pgAdminnal vagy más klienssel akarunk csatlakozni, azt
külön döntésként és tűzfalszabállyal kezeljük.

## Telepítés előtti ellenőrzések

VM-en:

```bash
lsb_release -ds
df -h /
free -h
sudo apt update
apt-cache search pgvector
apt-cache policy postgresql
```

Mit nézünk?

- Ubuntu verzió továbbra is 24.04 LTS-e;
- van-e elég lemezhely;
- elérhető-e pgvector csomag az aktuális apt forrásokból;
- melyik PostgreSQL verzió települne.

## Telepítési terv

### 1. PostgreSQL telepítése

```bash
sudo apt install postgresql postgresql-contrib
```

Ellenőrzés:

```bash
systemctl status postgresql --no-pager
sudo -u postgres psql -c "select version();"
```

### 2. pgvector csomag kiválasztása

Először keressük meg az elérhető csomagot:

```bash
apt-cache search pgvector
```

Ha van PostgreSQL verzióhoz illeszkedő pgvector csomag, azt telepítjük.
Példa név lehet:

```text
postgresql-16-pgvector
```

De a pontos csomagnevet a VM-en ellenőrizzük, nem találgatjuk.

Ha nincs pgvector csomag az alap Ubuntu forrásokban, akkor külön döntünk:

1. PostgreSQL hivatalos csomagtár hozzáadása;
2. vagy pgvector fordítása forrásból;
3. vagy Dockeres PostgreSQL + pgvector image használata.

Elsőként az apt csomagos megoldást preferáljuk.

### 3. Adatbázis-user és adatbázis létrehozása

Jelszót kézzel adunk meg, nem dokumentáljuk:

```bash
sudo -u postgres createuser --pwprompt kelvin
sudo -u postgres createdb --owner=kelvin kelvin_assistant
```

Ellenőrzés:

```bash
sudo -u postgres psql -c "\du"
sudo -u postgres psql -l
```

### 4. pgvector extension engedélyezése

```bash
sudo -u postgres psql -d kelvin_assistant -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Ellenőrzés:

```bash
sudo -u postgres psql -d kelvin_assistant -c "\dx vector"
```

### 5. Kelvin konfiguráció frissítése

```bash
sudoedit /etc/kelvin-assistant/kelvin.env
```

Hozzáadandó:

```text
KELVIN_DATABASE_URL=postgresql://kelvin:<password>@127.0.0.1:5432/kelvin_assistant
```

Utána:

```bash
sudo systemctl restart kelvin-api
sudo systemctl status kelvin-api --no-pager
```

Megjegyzés: a v0.4 elején Kelvin még nem fogja használni ezt a változót, amíg a
Python adatbázis-adaptert és konfigurációt be nem kötjük. A változó előkészítése
csak az infrastruktúra alapozása.

## Első adatbázis smoke test

VM-en:

```bash
PGPASSWORD='<password>' psql \
  --host=127.0.0.1 \
  --username=kelvin \
  --dbname=kelvin_assistant \
  --command="select current_database(), current_user;"
```

pgvector minimális próba:

```bash
sudo -u postgres psql -d kelvin_assistant -c "select '[1,2,3]'::vector;"
```

## Biztonsági alapelvek

- PostgreSQL ne legyen kinyitva a hálózatra.
- UFW-n ne nyissunk 5432-es portot.
- A jelszó csak `/etc/kelvin-assistant/kelvin.env` fájlban legyen.
- A konfigurációs fájl jogosultsága maradjon korlátozott:

```bash
sudo chown root:kelvin /etc/kelvin-assistant/kelvin.env
sudo chmod 0640 /etc/kelvin-assistant/kelvin.env
```

## Backup első terve

Kezdésként manuális mentés:

```bash
sudo -u postgres pg_dump kelvin_assistant > kelvin_assistant.sql
```

Később ezt pontosítani kell:

- mentési könyvtár;
- tömörítés;
- visszaállítási próba;
- automatizálás;
- retention szabály.

## Kapcsolat a v0.4 adatmodellhez

A PostgreSQL telepítés után a következő lépés nem a RAG azonnali bekötése,
hanem a migrációs stratégia kiválasztása:

- Alembic: professzionálisabb, Python projektekben standard;
- egyszerű SQL fájlok: tanulásra átláthatóbb, de hosszabb távon kényelmetlenebb.

Javaslat: Alembic, de külön lépésben, magyarázattal.

## Elfogadási feltétel ehhez a lépéshez

Ez az infrastruktúra-lépés akkor kész, ha:

- PostgreSQL fut a VM-en;
- a `kelvin_assistant` adatbázis létezik;
- a `kelvin` adatbázis-userrel lehet lokálisan csatlakozni;
- a `vector` extension aktív;
- az 5432-es port nincs kinyitva a hálózatra;
- a döntések és parancsok dokumentálva vannak.

## VM-validáció

A 2026-06-29-i ellenőrzés alapján az Ubuntu VM-en a PostgreSQL + pgvector alap
működik.

Ellenőrzött állapot:

| Ellenőrzés | Eredmény |
| --- | --- |
| Ubuntu verzió | Ubuntu 24.04.4 LTS |
| PostgreSQL verzió | PostgreSQL 16.14 |
| pgvector verzió | 0.6.0 |
| Adatbázis | `kelvin_assistant` |
| Adatbázis-user | `kelvin` |
| pgvector extension | `vector` aktív a `public` sémában |
| PostgreSQL listen address | `127.0.0.1:5432` |
| UFW 5432 | nincs nyitva |
| Kelvin env | `KELVIN_DATABASE_URL` beállítva |
| Kelvin API health | `{"status":"ok"}` |
| Kelvin API readiness | `{"status":"ready","provider":"ollama","model":"gemma4:e4b"}` |

Fontos következmény:

- az adatbázis kívülről nem érhető el;
- a Kelvin API továbbra is működik az új env változó mellett;
- a Python alkalmazás még nem használja az adatbázist, ez a következő v0.4
  fejlesztési lépések része.

Ellenőrzött pgvector próba:

```sql
select '[1,2,3]'::vector;
```

Eredmény:

```text
[1,2,3]
```

Ellenőrzött alkalmazás-user kapcsolat:

```sql
select current_database(), current_user;
```

Eredmény:

```text
kelvin_assistant | kelvin
```

## Knowledge séma validáció

A `infrastructure/sql/001_create_knowledge_schema.sql` fájl sikeresen lefutott a
VM-en a `kelvin` adatbázis-userrel.

Futtatott parancs:

```bash
PGPASSWORD='<password>' psql \
  --host=127.0.0.1 \
  --username=kelvin \
  --dbname=kelvin_assistant \
  --file=infrastructure/sql/001_create_knowledge_schema.sql
```

Létrejött táblák:

| Tábla | Cél |
| --- | --- |
| `knowledge_collections` | Logikai tudásgyűjtemények |
| `knowledge_documents` | Eredeti dokumentumok nyilvántartása |
| `knowledge_chunks` | Kereshető dokumentumrészletek |
| `knowledge_embeddings` | Chunkok pgvector embeddingjei |

Ellenőrzött indexek:

- `ix_knowledge_chunks_document_id`
- `ix_knowledge_embeddings_vector_cosine`
- `ux_knowledge_chunks_document_index`
- `ux_knowledge_documents_collection_hash`
- `ux_knowledge_documents_collection_source`
- `ux_knowledge_embeddings_chunk_model`

Az `ix_knowledge_embeddings_vector_cosine` HNSW index a későbbi cosine distance
alapú vektoros keresést gyorsítja.

Validált pgvector smoke test:

```sql
select '[1,2,3]'::vector;
```

Eredmény:

```text
[1,2,3]
```

Ezzel a v0.4 első tényleges adatbázis-sémája készen áll a kézi adatpróbára.

## Embedding modell validáció

Az első RAG embedding modell:

```text
nomic-embed-text
```

Ollama API próba:

```powershell
$body = @{
  model = "nomic-embed-text"
  prompt = "Kelvin API production portja 8000."
} | ConvertTo-Json

$response = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:11434/api/embeddings" `
  -ContentType "application/json" `
  -Body $body

$response.embedding.Count
```

Mért eredmény:

```text
768
```

Következmény:

- a jelenlegi `knowledge_embeddings.embedding vector(768)` mező illeszkedik az
  első embedding modellhez;
- a `manual-dummy-768` kézi tesztmodell után a következő lépés már valódi
  `nomic-embed-text` embeddingek beszúrása lesz;
- ha később más embedding modellre váltunk, a dimenziót és a sémát külön
  validálni kell.

## Kézi vektoros keresési próba

A VM-en kézi tesztadatokkal ellenőriztük a RAG keresés legalapvetőbb adatbázis
oldali működését.

Létrehozott próbaadatok:

| Szint | Érték |
| --- | --- |
| Collection | `manual_test` |
| Dokumentum | `manual://kelvin-notes` |
| Embedding modell | `manual-dummy-768` |

Beszúrt chunkok:

| Chunk index | Szöveg | Dummy vektor logika |
| --- | --- | --- |
| `0` | `Kelvin API production portja 8000.` | 1. dimenzió = 1 |
| `1` | `PostgreSQL es pgvector a VM-en fut lokalisan.` | 2. dimenzió = 1 |

A keresővektor a 2. dimenzióban kapott `1` értéket, ezért a PostgreSQL/pgvector
chunknak kellett elsőként visszajönnie.

Futtatott keresés lényege:

```sql
SELECT
    chunks.chunk_index,
    chunks.content,
    embeddings.embedding <=> query.embedding AS cosine_distance
FROM knowledge_embeddings AS embeddings
JOIN knowledge_chunks AS chunks
    ON chunks.id = embeddings.chunk_id
ORDER BY cosine_distance
LIMIT 2;
```

Eredmény:

```text
 chunk_index |                    content                    | cosine_distance
-------------+-----------------------------------------------+-----------------
           1 | PostgreSQL es pgvector a VM-en fut lokalisan. |               0
           0 | Kelvin API production portja 8000.            |               1
```

Következtetés:

- a `vector(768)` embedding mező működik;
- a cosine distance operátor (`<=>`) működik;
- a legkisebb távolságú chunk kerül előre;
- a RAG keresés adatbázis oldali alapja validált;
- a következő lépés az embedding előállításának és a Python adapternek a
  megtervezése.
