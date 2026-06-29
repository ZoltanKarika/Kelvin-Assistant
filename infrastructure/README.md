# Infrastruktúra

Helyi telepítési és üzemeltetési konfigurációk:

- `systemd`: natív Ubuntu szolgáltatásegységek;
- `sql`: kézzel olvasható adatbázis-sémák és kezdeti migrációk;
- `docker`: későbbi opcionális Docker Compose telepítés;
- `config`: nem titkos konfigurációs sablonok.

Jelszó, token, privát kulcs és futásidejű adat nem kerülhet ebbe a
könyvtárba.

## systemd

A `systemd/kelvin-api.service` a backend javasolt Ubuntu szolgáltatásegysége.
A hordozható telepítési elrendezés:

- alkalmazás: `/opt/kelvin-assistant`;
- konfiguráció: `/etc/kelvin-assistant/kelvin.env`;
- írható alkalmazásadat: `/var/lib/kelvin-assistant`;
- szolgáltatásfelhasználó: `kelvin`.

Az egység nem rootként fut, automatikusan újraindul hiba után, és a naplókat
az Ubuntu naplókezelőjébe írja. A telepítési lépéseket a
`docs/installation.md` dokumentálja.
