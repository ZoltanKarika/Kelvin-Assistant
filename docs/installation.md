# Telepítés és fejlesztői futtatás

## Jelenlegi állapot

A FastAPI backend Windowson fejlesztői módban, a saját Ubuntu Server VM-en
pedig `systemd` szolgáltatásként fut. A VM újraindítása után automatikusan
elindul, és a helyi hálózatról elérhető health és readiness végponttal
ellenőrizhető.

A GitHub Actions ugyanezt a projektet Ubuntu 24.04 és Python 3.12 alatt
ellenőrzi. A Windows hoston futó Ollama adaptere és helyi integrációs
ellenőrzése működik. A VM és a host közötti, tűzfallal korlátozott Ollama
kapcsolat, a readiness végpont és a GPU-gyorsított generálás is ellenőrzött.
A verziózott chat API többfordulós memóriabeli sessionöket kezel, a streaming
végpont pedig Server-Sent Events formátumban küldi a modell válaszát. A
minimális webes chatfelület a `/ui` útvonalon érhető el. Az offline
csomagimport még külön üzemeltetési lépés.

## Célkörnyezet

### Host

- Windows 11;
- Hyper-V;
- PowerShell;
- Git;
- Visual Studio Code;
- Ollama és a helyileg telepített Gemma modell.

### Guest

- Ubuntu Server 24.04 LTS;
- Python 3.12 vagy újabb;
- később Open WebUI, PostgreSQL és pgvector.

### Ellenőrzött VM-konfiguráció

| Beállítás | Érték |
| --- | --- |
| Hyper-V generáció | Generation 2 |
| Operációs rendszer | Ubuntu Server 24.04.4 LTS |
| Virtuális processzor | 6 |
| Induló memória | 6144 MB |
| Dinamikus memória | 4096–8192 MB |
| Virtuális lemez | 40 GB, dinamikusan növekvő VHDX |
| Hálózat | External Switch |
| Secure Boot sablon | Microsoft UEFI Certificate Authority |

A VM IP-címét DHCP osztja ki. A dokumentációban szereplő `<VM_IP>` helyére
mindig a `hostname -I` paranccsal ellenőrzött aktuális cím kerül. Tartós
üzemeltetéshez DHCP-foglalás ajánlott a routeren.

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

A jelenlegi backend által használt változók:

| Változó | Alapérték | Jelentés |
| --- | --- | --- |
| `KELVIN_ENVIRONMENT` | `development` | Futási környezet neve |
| `KELVIN_LOG_LEVEL` | `INFO` | Minimális naplózási szint |
| `KELVIN_LOG_FORMAT` | `json` | `json` vagy `console` formátum |
| `KELVIN_API_HOST` | `127.0.0.1` | Figyelt hálózati cím |
| `KELVIN_API_PORT` | `8000` | Figyelt TCP-port |
| `KELVIN_API_AUTH_MODE` | `disabled` | `disabled` fejlesztéshez, `required` production vagy LAN-elérés esetén |
| `KELVIN_API_TOKEN_FILE` | nincs | Hashelt API-tokeneket tartalmazó JSON fájl útvonala |
| `KELVIN_LLM_PROVIDER` | `ollama` | Aktív LLM-adapter |
| `KELVIN_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API alapcíme |
| `KELVIN_OLLAMA_MODEL` | `gemma4:e4b` | Telepített modell neve |
| `KELVIN_OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Dokumentum- és keresési embedding modell |
| `KELVIN_EMBEDDING_DIMENSION` | `768` | Az embedding vektor elvárt dimenziója |
| `KELVIN_OLLAMA_TIMEOUT` | `120` | Kérés időkorlátja másodpercben |
| `KELVIN_DATABASE_URL` | nincs | PostgreSQL kapcsolat a tudástárhoz |
| `KELVIN_DATABASE_CONNECT_TIMEOUT` | `5` | Adatbázis-kapcsolat időkorlátja másodpercben |
| `KELVIN_RAG_ENABLED` | `false` | Tudásbázis-kontekstus bekapcsolása a chatben |
| `KELVIN_RAG_COLLECTION` | `manual` | Chathez használt tudásgyűjtemény |
| `KELVIN_RAG_RESULT_LIMIT` | `3` | Chathez lekért tudásbázis-részletek száma |

A `.env` fájlban ne tárolj repositoryba kerülő jelszót, tokent vagy más
titkot. A fájlt soha ne commitold.

Production vagy helyi hálózatról elérhető telepítés esetén az API-hitelesítés
kötelező:

```text
KELVIN_API_AUTH_MODE=required
KELVIN_API_TOKEN_FILE=/etc/kelvin-assistant/api-tokens.json
```

Az `api-tokens.json` csak `token_sha256` mezőket tartalmazhat, nyers tokeneket
nem. A formátumot az `api-tokens.example.json` és a
`docs/token-management.md` dokumentálja.

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
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/ready/database
Invoke-RestMethod http://127.0.0.1:8000/version
```

Az `/health` csak a FastAPI folyamat állapotát jelzi. A `/ready` az Ollama
elérhetőségét és a konfigurált modell telepítettségét is ellenőrzi. Ha ezek
nem állnak rendelkezésre, a végpont HTTP 503 választ ad.

Az `/ready/database` a PostgreSQL kapcsolatot ellenőrzi egy egyszerű `select 1`
lekérdezéssel. Ha a `KELVIN_DATABASE_URL` nincs beállítva, vagy az adatbázis nem
érhető el, HTTP 503 választ ad. Ez külön végpont, hogy az LLM és az adatbázis
állapota ne keveredjen.

Az interaktív Swagger UI a `http://127.0.0.1:8000/docs` címen érhető el.
A szerver `Ctrl+C` billentyűkombinációval állítható le.

## Nem streamelt chat API

Az első kérés sessionazonosító nélkül új beszélgetést hoz létre:

```powershell
$firstBody = @{
    message = "Jegyezd meg ezt a szót: boróka."
} | ConvertTo-Json

$first = Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:8000/api/v1/chat `
    -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes($firstBody))

$first
```

A következő kérés visszaküldi a kapott `session_id` értéket:

```powershell
$secondBody = @{
    message = "Melyik szót kértem, hogy jegyezd meg?"
    session_id = $first.session_id
} | ConvertTo-Json

$second = Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:8000/api/v1/chat `
    -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes($secondBody))

$second
```

A kézi UTF-8 byte-konverzió a Windows PowerShell 5.1 hibás ékezetmegjelenítési
és request-kódolási eseteit kerüli el. PowerShell 7 alatt általában a JSON
szöveg közvetlen átadása is megfelelő.

Az endpoint fontosabb válaszai:

| HTTP | Jelentés |
| --- | --- |
| `200` | A teljes forduló elkészült és mentésre került |
| `404` | A megadott session nem létezik |
| `409` | A sessiont egy másik kérés időközben módosította |
| `422` | A kérés vagy az üzenet formátuma érvénytelen |
| `502` | Az LLM használhatatlan választ adott |
| `503` | Az Ollama runtime nem érhető el |

A sessiontár jelenleg folyamatmemóriában él. Backend- vagy VM-újraindításkor
a beszélgetések elvesznek; a későbbi perzisztens adapter ezt a `SessionStore`
port mögött, az API módosítása nélkül válthatja fel.

## Streaming chat API

A streaming végpont ugyanazt a request body-t használja, mint a nem streamelt
chat, de `text/event-stream` választ ad:

```text
POST /api/v1/chat/stream
```

PowerShellből:

```powershell
$body = @{
    message = "Please count from 1 to 5, one number per line."
} | ConvertTo-Json

curl.exe -N -i -X POST "http://127.0.0.1:8000/api/v1/chat/stream" `
    -H "Content-Type: application/json" `
    --data-binary $body
```

A sikeres válasz eseményei:

```text
event: session
data: {"session_id": "...", "model": "..."}

event: token
data: {"text": "..."}

event: done
data: {}
```

Az asszisztens válasza csak a teljes stream sikeres befejezése után kerül a
sessionbe. Így megszakadt kapcsolat vagy modellhiba esetén nem marad félkész
asszisztens-forduló a beszélgetésben.

## Webes chatfelület

A beépített, minimális chatfelület:

```text
http://127.0.0.1:8000/ui
```

Ubuntu VM-en a helyi hálózatról:

```text
http://<VM_IP>:8000/ui
```

A felület ugyanazt a FastAPI alkalmazást használja, mint az API, ezért nincs
külön Node.js build, CORS-beállítás vagy internetfüggőség. A válaszokat
streamelve jeleníti meg, és a sessionazonosítót csak a böngésző memóriájában
tartja.

## Fejlesztői ellenőrzések

```powershell
uv run ruff check backend tests scripts
uv run ruff format --check backend tests scripts
uv run mypy backend/src tests scripts
uv run pytest --cov=kelvin_assistant --cov-report=term-missing
```

Ugyanezeket a fő ellenőrzéseket futtatja a GitHub Actions pull requestnél.

## Ollama a Windows hoston

Az Ollama Windows alatt alapértelmezetten csak a
`http://127.0.0.1:11434` címen figyel. Helyi fejlesztésnél ez megfelelő:

```powershell
ollama list
uv run python scripts/check_ollama.py
```

A tényleges CPU/GPU megoszlás ellenőrzése egy futó modell mellett:

```powershell
ollama ps
```

### Ellenőrzött end-to-end mérés

A 2026-06-28-i ellenőrzés során az Ubuntu VM-ből indított kérés a Windows
host Ollamáján keresztül sikeres választ adott:

| Tulajdonság | Mért érték |
| --- | --- |
| Modell | `gemma4:e4b` |
| Modellcsalád | Gemma 4 |
| Paraméterméret | 8.0B |
| Kvantálás | Q4_K_M |
| Betöltött méret | 3.3 GB |
| Feldolgozó | 100% GPU |
| Context length | 4096 |

Ez az ellenőrzés a teljes útvonalat lefedte: Ubuntu systemd szolgáltatás →
Windows host → Ollama → AMD Radeon RX 6650 XT → Gemma modell.

Ahhoz, hogy az Ubuntu VM elérje a Windows host Ollamáját, Windows felhasználói
környezeti változóként be kell állítani:

```text
OLLAMA_HOST=0.0.0.0:11434
```

Ezután az Ollama tálcaalkalmazást teljesen ki kell léptetni és újra kell
indítani. A Windows tűzfalon a TCP 11434 portot kizárólag a VM IP-címéről
vagy a megbízható helyi alhálózatról szabad engedélyezni. Routeres
porttovábbítás nem használható, mert a helyi Ollama API nem igényel
hitelesítést.

Az Ubuntu szerver `/etc/kelvin-assistant/kelvin.env` fájljában:

```text
KELVIN_LLM_PROVIDER=ollama
KELVIN_OLLAMA_BASE_URL=http://<WINDOWS_HOST_IP>:11434
KELVIN_OLLAMA_MODEL=gemma4:e4b
KELVIN_OLLAMA_TIMEOUT=120
KELVIN_DATABASE_URL=postgresql://kelvin:<password>@127.0.0.1:5432/kelvin_assistant
KELVIN_DATABASE_CONNECT_TIMEOUT=5
```

Kapcsolat ellenőrzése a VM-ről:

```bash
curl http://<WINDOWS_HOST_IP>:11434/api/tags
```

Az `OLLAMA_HOST` Windows-konfigurációját az
[Ollama hivatalos FAQ-ja](https://docs.ollama.com/faq) dokumentálja.

## Ubuntu VM alapbeállítása

Az első rendszerfrissítés:

```bash
sudo apt update
sudo apt upgrade
sudo reboot
```

Az OpenSSH szerver telepítve van. A nyilvános kulcs sikeres ellenőrzése után
a `/etc/ssh/sshd_config.d/99-kelvin-hardening.conf` fájl tartalma:

```text
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
```

Módosítás után mindig ellenőrizni kell a szintaxist az SSH újratöltése előtt:

```bash
sudo sshd -t
sudo systemctl reload ssh
```

Az UFW alapértelmezetten tiltja a bejövő kapcsolatokat. Az SSH és az API csak
a példában használt helyi hálózatról érhető el:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.10.0/24 to any port 22 proto tcp comment 'SSH from LAN'
sudo ufw allow from 192.168.10.0/24 to any port 8000 proto tcp comment 'Kelvin API from LAN'
sudo ufw --force enable
```

Más alhálózat használatakor a `192.168.10.0/24` értéket módosítani kell.
Internet felé porttovábbítás nem szükséges és nem ajánlott.

## Ubuntu fejlesztői telepítés

Az `uv` rögzített verziójának telepítése:

```bash
curl -LsSf https://astral.sh/uv/0.11.25/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
uv --version
```

A repository és a környezet létrehozása:

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/ZoltanKarika/Kelvin-Assistant.git
cd Kelvin-Assistant
uv sync --locked
cp .env.example .env
```

A helyi hálózati eléréshez a Git által figyelmen kívül hagyott `.env`
fájlban:

```text
KELVIN_API_HOST=0.0.0.0
KELVIN_API_PORT=8000
```

A `0.0.0.0` figyelési cím csak aktív tűzfal és megbízható helyi hálózat
mellett használható.

## Ajánlott systemd telepítés

A repositoryban található
`infrastructure/systemd/kelvin-api.service` a végleges, hordozható
könyvtárszerkezetet használja:

- kód és virtuális környezet: `/opt/kelvin-assistant`;
- helyi konfiguráció: `/etc/kelvin-assistant/kelvin.env`;
- futásidejű adat: `/var/lib/kelvin-assistant`;
- jogosultság nélküli szolgáltatásfelhasználó: `kelvin`.

A szolgáltatásfelhasználó és a rendszer szintű `uv` parancs létrehozása:

```bash
sudo useradd --system --create-home \
  --home-dir /var/lib/kelvin-assistant \
  --shell /usr/sbin/nologin kelvin
sudo install -m 0755 "$HOME/.local/bin/uv" /usr/local/bin/uv
```

A kód telepítése és a futási függőségek létrehozása:

```bash
sudo install -d -o kelvin -g kelvin -m 0750 /opt/kelvin-assistant
sudo -u kelvin -H git clone \
  https://github.com/ZoltanKarika/Kelvin-Assistant.git \
  /opt/kelvin-assistant
sudo -u kelvin -H bash -c \
  'cd /opt/kelvin-assistant && uv sync --locked --no-dev'
```

A helyi konfiguráció létrehozása:

```bash
sudo install -d -o root -g kelvin -m 0750 /etc/kelvin-assistant
sudo install -o root -g kelvin -m 0640 \
  /opt/kelvin-assistant/.env.example \
  /etc/kelvin-assistant/kelvin.env
sudoedit /etc/kelvin-assistant/kelvin.env
```

A szerveren legalább ezeket az értékeket kell beállítani:

```text
KELVIN_ENVIRONMENT=production
KELVIN_LOG_FORMAT=json
KELVIN_API_HOST=0.0.0.0
KELVIN_API_PORT=8000
KELVIN_API_AUTH_MODE=required
KELVIN_API_TOKEN_FILE=/etc/kelvin-assistant/api-tokens.json
KELVIN_LLM_PROVIDER=ollama
KELVIN_OLLAMA_BASE_URL=http://<WINDOWS_HOST_IP>:11434
KELVIN_OLLAMA_MODEL=gemma4:e4b
KELVIN_OLLAMA_TIMEOUT=120
```

A szolgáltatásegység telepítése és indítása:

```bash
sudo install -o root -g root -m 0644 \
  /opt/kelvin-assistant/infrastructure/systemd/kelvin-api.service \
  /etc/systemd/system/kelvin-api.service
sudo systemd-analyze verify /etc/systemd/system/kelvin-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now kelvin-api
systemctl status kelvin-api --no-pager
```

Naplók megtekintése:

```bash
journalctl -u kelvin-api --no-pager
```

Külső health ellenőrzés Windows PowerShellből:

```powershell
Invoke-RestMethod http://<VM_IP>:8000/health
Invoke-RestMethod http://<VM_IP>:8000/ready
Invoke-RestMethod http://<VM_IP>:8000/ready/database
Invoke-RestMethod http://<VM_IP>:8000/version
```

A tanulási VM-et először a `zoltan` felhasználó
`~/projects/Kelvin-Assistant` könyvtárából ellenőriztük. Ezután sikeresen
átállt a dedikált `kelvin` felhasználóra és az `/opt` elrendezésre. A
szolgáltatás külső health ellenőrzése és automatikus újraindulása is
ellenőrzött.

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

## Hardver és GPU

A host 16 GB RAM-mal, 12 logikai processzorral és AMD Radeon RX 6650 XT
8 GB GPU-val rendelkezik. A Windows 11 Hyper-V nem biztosít ehhez a
consumer Radeon kártyához támogatott közvetlen VM-hozzárendelést.

Az ellenőrzött v0.2 runtime felépítése:

- a FastAPI és az alkalmazásréteg az Ubuntu VM-en fut;
- az Ollama a Windows hoston használja a Radeon GPU-t;
- a VM korlátozott helyi hálózati API-n keresztül éri el az Ollamát;
- a Windows tűzfal csak a VM IP-címéről engedi a TCP 11434 portot;
- az `ollama ps` mérése 100% GPU-feldolgozást igazolt.
