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
