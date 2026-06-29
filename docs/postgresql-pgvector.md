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
