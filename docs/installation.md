# Telepítés és fejlesztői futtatás

## Jelenlegi állapot

A FastAPI backend fejlesztői módban Windowson futtatható. A GitHub Actions
ugyanezt a projektet Ubuntu 24.04 és Python 3.12 alatt is ellenőrzi.

Ez még nem jelenti azt, hogy a backend telepítve van a projekt saját Ubuntu
Server VM-jére. A VM-hálózat, a `systemd` szolgáltatás, az offline
csomagimport és az Ollama külön következő lépések.

## Célkörnyezet

### Host

- Windows 11;
- Hyper-V;
- PowerShell;
- Git;
- Visual Studio Code.

### Guest

- Ubuntu Server 24.04 LTS;
- Python 3.12 vagy újabb;
- Ollama;
- később Open WebUI és ChromaDB.

## Fejlesztői előfeltételek

- Git;
- PowerShell;
- `uv` 0.11.25 vagy kompatibilis újabb verzió;
- internetkapcsolat az első függőségletöltéshez.

A projekt Python 3.12 vagy újabb verziót támogat. Az `uv` szükség esetén
képes a megfelelő Python-verzió telepítésére és kezelésére.

## Repository letöltése

```powershell
git clone https://github.com/ZoltanKarika/Kelvin-Assistant.git
Set-Location "Kelvin-Assistant"
```

Már létező munkapéldánynál:

```powershell
git switch main
git pull --ff-only origin main
```

## Konfiguráció

Hozd létre a saját, Git által figyelmen kívül hagyott `.env` fájlodat:

```powershell
Copy-Item .env.example .env
```

A v0.1 által használt változók:

| Változó | Alapérték | Jelentés |
| --- | --- | --- |
| `KELVIN_ENVIRONMENT` | `development` | Futási környezet neve |
| `KELVIN_LOG_LEVEL` | `INFO` | Minimális naplózási szint |
| `KELVIN_LOG_FORMAT` | `json` | `json` vagy `console` formátum |
| `KELVIN_API_HOST` | `127.0.0.1` | Figyelt hálózati cím |
| `KELVIN_API_PORT` | `8000` | Figyelt TCP-port |

A `.env` fájlban ne tárolj repositoryba kerülő jelszót, tokent vagy más
titkot. A fájlt soha ne commitold.

## Függőségek telepítése

```powershell
uv sync --locked --all-groups
```

A parancs:

1. létrehozza a `.venv` virtuális környezetet;
2. ellenőrzi, hogy az `uv.lock` naprakész;
3. telepíti a futási és fejlesztői függőségeket;
4. szerkeszthető csomagként telepíti a Kelvin Assistant backendet.

## Backend indítása

```powershell
uv run kelvin-api
```

Sikeres induláskor az API címe:

```text
http://127.0.0.1:8000
```

Ellenőrzés egy másik PowerShell-ablakból:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/version
```

Az interaktív Swagger UI a `http://127.0.0.1:8000/docs` címen érhető el.
A szerver `Ctrl+C` billentyűkombinációval állítható le.

## Fejlesztői ellenőrzések

```powershell
uv run ruff check backend tests
uv run ruff format --check backend tests
uv run mypy backend/src tests
uv run pytest --cov=kelvin_assistant --cov-report=term-missing
```

Ugyanezeket a fő ellenőrzéseket futtatja a GitHub Actions pull requestnél.

## Ubuntu VM telepítési terv

1. A VM CPU-, memória-, lemez- és hálózati erőforrásainak rögzítése.
2. Dedikált szolgáltatásfelhasználó és adatkönyvtárak létrehozása.
3. Git, `uv`, Python és a virtuális környezet ellenőrzése.
4. Verziórögzített offline Python wheelhouse előkészítése.
5. Ollama és a kiválasztott modell ellenőrzött átvitele.
6. A backend telepítése és lokális konfigurálása.
7. `systemd` egységek telepítése.
8. Health és readiness ellenőrzés.
9. Open WebUI csatlakoztatása.
10. A Windows PowerShell-kliens telepítése.

## Offline ellátási lánc

Az offline futás nem jelenti azt, hogy a telepítési fájlok automatikusan
rendelkezésre állnak. Egy internetkapcsolattal rendelkező előkészítő
környezetben kell összeállítani:

- az operációs rendszer szükséges csomagjait;
- a Python wheel fájlokat;
- az Ollama telepítőcsomagját;
- a modellfájlokat;
- a webes felület szükséges artefaktumait.

Az átvitt csomagokhoz verziólista és SHA-256 ellenőrző összeg tartozik majd.
Az offline VM csak az ellenőrzés után telepíti őket.

Az Ubuntu VM-en a `KELVIN_API_HOST=0.0.0.0` beállítás csak a Hyper-V
hálózat és az Ubuntu tűzfal külön ellenőrzése után használható. Internet felé
közvetlen API-kitettség nincs tervezve.

## Még szükséges hardveradatok

A modell és a kvantálási szint kiválasztása előtt rögzíteni kell:

- a host és a VM számára elérhető RAM mennyiségét;
- a processzor típusát és a VM virtuális processzorainak számát;
- a GPU típusát, VRAM-ját és Hyper-V elérhetőségét;
- a modellekhez fenntartott lemezterületet.
