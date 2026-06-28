# Telepítési terv

## Jelenlegi állapot

A repository egyelőre csak a projektvázat tartalmazza. Még nincs telepíthető
backend vagy futtatható kliens. Ez a dokumentum a célfolyamatot rögzíti; a
konkrét, ellenőrzött parancsokat az érintett komponensekkel együtt adjuk
hozzá.

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

## Tervezett telepítési sorrend

1. A VM CPU-, memória-, lemez- és hálózati erőforrásainak rögzítése.
2. Dedikált szolgáltatásfelhasználó és adatkönyvtárak létrehozása.
3. Python és a virtuális környezet ellenőrzése.
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

## Konfiguráció

Lokális fejlesztéshez:

1. másold a `.env.example` fájlt `.env` néven;
2. add meg a helyi modell pontos nevét és az elérési útvonalakat;
3. soha ne commitold a `.env` fájlt.

A publikus hálózati bind alapértelmezetten tiltott. Távoli elérés csak külön
hitelesítési és hálózati döntés után engedélyezhető.

## Még szükséges hardveradatok

A modell és a kvantálási szint kiválasztása előtt rögzíteni kell:

- a host és a VM számára elérhető RAM mennyiségét;
- a processzor típusát és a VM virtuális processzorainak számát;
- a GPU típusát, VRAM-ját és Hyper-V elérhetőségét;
- a modellekhez fenntartott lemezterületet.
