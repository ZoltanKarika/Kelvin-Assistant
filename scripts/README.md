# Segédszkriptek

Ismételhető fejlesztési, ellenőrzési, telepítési és mentési feladatok helye.

Minden szkriptnek:

- biztonságos alapértékeket kell használnia;
- hibánál nem nulla kilépési kódot kell adnia;
- dokumentálnia kell a bemenetét és a mellékhatásait;
- lehetőség szerint többször is biztonságosan futtathatónak kell lennie.

## Ollama kapcsolat ellenőrzése

A `check_ollama.py` opcionális élő integrációs ellenőrzés. A `.env` fájlban
konfigurált Ollama runtime-ot és modellt hívja meg, ezért a unit tesztekkel
ellentétben futó Ollamát igényel:

```powershell
uv run python scripts/check_ollama.py
```

Siker esetén naplózza a rövid modellválaszt és nulla kilépési kódot ad.
Kapcsolati, HTTP- vagy válaszformátum-hibánál nem nulla kóddal áll le. A
szkript nem módosít adatot és nem tölt le modellt.

## Dokumentum importálása a tudásbázisba

A `kelvin-import-document` parancs egy helyi `.txt`, `.md` vagy `.markdown`
fájlt tölt be, feldarabolja, PostgreSQL-be menti a dokumentumot és a chunkokat,
majd Ollama embeddinget készít és eltárolja a `knowledge_embeddings` táblában.

Példa:

```powershell
uv run kelvin-import-document `
  --collection manual `
  docs/installation.md
```

Régi, közvetlen scriptes futtatásra továbbra is van kompatibilitási wrapper:

```powershell
uv run python scripts/import_document.py `
  --collection manual `
  docs/installation.md
```

Fontos:

- szükséges hozzá a `KELVIN_DATABASE_URL` beállítás;
- szükséges hozzá futó Ollama és telepített embedding modell;
- alapértelmezett embedding modell: `nomic-embed-text`;
- a PostgreSQL sémának már léteznie kell;
- ugyanazt a dokumentumot újrafuttatva a chunkok és embeddingek frissülnek, nem
  duplikálódnak.

## Tudásbázis keresése

A `kelvin-search-knowledge` parancs a kérdést embeddinggé alakítja, majd
pgvector cosine distance alapján visszaadja a legközelebbi chunkokat.

Példa:

```powershell
uv run kelvin-search-knowledge `
  --collection manual `
  --limit 3 `
  "Hol fut az Ollama?"
```

Ez még diagnosztikai/admin parancs. A következő lépésben ugyanez a keresés kerül
majd be a chat/RAG folyamatba.

## Kelvin VM update

`update-kelvin-vm.sh` updates the systemd deployment on the Kelvin VM. It pulls
the selected branch, syncs production dependencies, applies the idempotent agent
and security audit database schemas when `KELVIN_DATABASE_URL` is available from
the shell, the `kelvin-api` systemd environment file, or the repo `.env`, and then
restarts `kelvin-api`.

The schema step is required by default and verifies that `security_audit_logs`
can be queried. Use `--skip-db-schema` only when the database schema is managed
separately.

Run it on the VM:

```bash
cd /opt/kelvin-assistant
sudo ./scripts/update-kelvin-vm.sh
```

For a static-only hotfix you can skip dependency sync:

```bash
sudo ./scripts/update-kelvin-vm.sh --skip-uv-sync
```

Only skip database schema application when you have already applied the matching
SQL manually:

```bash
sudo ./scripts/update-kelvin-vm.sh --skip-db-schema
```
