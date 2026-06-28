# Telepítés és fejlesztői futtatás

## Jelenlegi állapot

A FastAPI backend Windowson fejlesztői módban, a saját Ubuntu Server VM-en
pedig `systemd` szolgáltatásként fut. A VM újraindítása után automatikusan
elindul, és a helyi hálózatról elérhető health végponttal ellenőrizhető.

A GitHub Actions ugyanezt a projektet Ubuntu 24.04 és Python 3.12 alatt
ellenőrzi. Az offline csomagimport és az Ollama még külön következő lépések.

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

Ezért a v0.2 elsődleges terve:

- a FastAPI és az alkalmazásréteg az Ubuntu VM-en fut;
- az Ollama a Windows hoston próbálja használni a Radeon GPU-t;
- a VM korlátozott helyi hálózati API-n keresztül éri el az Ollamát;
- a tényleges GPU-használatot mérés és `ollama ps` igazolja.
