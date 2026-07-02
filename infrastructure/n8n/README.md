# n8n automation stack

Ez a Compose stack a külön `kelvin-automation` Ubuntu VM-en futtatja az n8n-t
és annak dedikált PostgreSQL adatbázisát.

## Biztonsági határok

- Az n8n editor csak a VM `127.0.0.1:5678` címére van publikálva.
- A PostgreSQL port nincs publikálva.
- Az editor Windowsról PuTTY SSH tunnelen keresztül érhető el.
- A VM nem kap Windows workspace-, SMB- vagy Docker socket mountot.
- Az Execute Command, Read/Write Files, Local File Trigger és SSH node tiltott.
- Community node-ok alapértelmezetten nem telepíthetők.
- A valódi `.env` fájl és minden credential Gitből kizárt.

A loopback portkötés szándékos. A Docker által publikált portok megkerülhetik az
UFW szabályait, ezért a `5678/tcp` portot nem publikáljuk a VM LAN-címén.

## Első telepítés

Másold a könyvtárat az automation VM-re, majd:

```bash
cd /opt/kelvin-automation
sudo cp .env.example .env
sudo chmod 600 .env
```

Generálj két külön secretet közvetlenül a VM-en:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Az egyik érték legyen `N8N_DB_PASSWORD`, a másik
`N8N_ENCRYPTION_KEY`. Szerkesztés:

```bash
sudo nano .env
```

Ellenőrzés és indítás:

```bash
sudo docker compose config --quiet
sudo docker compose pull
sudo docker compose up -d
sudo docker compose ps
```

A `docker compose config` feloldja a secret értékeket, ezért annak teljes
kimenetét nem szabad naplóba vagy beszélgetésbe másolni. A `--quiet` csak a
konfiguráció érvényességét jelzi.

## PuTTY tunnel

A mentett `Kelvin Automation` sessionben:

1. `Connection -> SSH -> Tunnels`
2. Source port: `5678`
3. Destination: `127.0.0.1:5678`
4. `Local`, majd `Add`
5. vissza a `Session` képernyőre és `Save`

Aktív PuTTY kapcsolat mellett az editor címe:

```text
http://127.0.0.1:5678
```

## Ellenőrzés

Konténerállapot:

```bash
sudo docker compose ps
```

Lokális health check az automation VM-en:

```bash
curl --fail http://127.0.0.1:5678/healthz
```

Portkötés:

```bash
sudo ss -ltnp | grep 5678
```

Csak `127.0.0.1:5678` jelenhet meg. `0.0.0.0:5678` vagy
`192.168.10.14:5678` biztonsági hibának számít.

## Leállítás és frissítés

Leállítás az adatok megtartásával:

```bash
sudo docker compose down
```

A `down -v` kapcsoló törli a volume-okat és az adatokat, ezért production
környezetben nem használható mentés és külön jóváhagyás nélkül.

Frissítés előtt kötelező:

1. PostgreSQL dump;
2. n8n volume és encryption key mentése;
3. új image-verzió külön feature branchben;
4. Compose-validáció és release note ellenőrzés;
5. ellenőrzött visszaállítási pont.

## Rögzített verziók

- n8n: `2.27.5`
- PostgreSQL: `17.10-bookworm`

Az image-verziók módosítása külön karbantartási commit.
