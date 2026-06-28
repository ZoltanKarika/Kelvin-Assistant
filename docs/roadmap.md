# Fejlesztési roadmap

Minden szakasz külön jóváhagyási pont. Egy szakasz csak akkor tekinthető
késznek, ha a dokumentációja és az automatizált ellenőrzései is elkészültek.

## 0. Projektalapok

- könyvtárstruktúra és induló dokumentáció;
- Git repository és alapértelmezett `main` ág;
- biztonságos `.gitignore` és `.env.example`;
- Conventional Commits és branchszabályok;
- Python minőségi eszközök alapkonfigurációja.

Elfogadási feltétel: tiszta repository, ellenőrzött első commit és
dokumentált fejlesztési folyamat.

## 1. Ubuntu és offline előkészítés

- VM-erőforrások rögzítése;
- adattárolási és hálózati terv;
- natív szolgáltatásfelhasználók;
- offline csomag- és modellimport;
- ellenőrző összegek;
- mentési helyek.

Elfogadási feltétel: az alap VM dokumentáltan újra létrehozható, és futás
közben nem igényel internetet.

## 2. Backend-alap

- FastAPI alkalmazásgyár;
- típusos konfiguráció;
- logging és központi kivételkezelés;
- `health` és `ready` végpont;
- unit tesztek és minőségi ellenőrzések.

Elfogadási feltétel: a backend lokálisan elindul, és minden automatikus
ellenőrzés sikeres.

## 3. LLM-integráció

- általános LLM-port;
- Ollama adapter;
- hardverhez választott Gemma modell;
- timeout, megszakítás és streaming;
- mockolt unit és opcionális helyi integrációs teszt.

Elfogadási feltétel: a modell konfigurációból cserélhető, és hiba esetén
érthető API-válasz keletkezik.

## 4. Chat API és munkamenetek

- verziózott chat végpont;
- munkamenet-azonosítás;
- kontextusablak-kezelés;
- streaming klienskapcsolat;
- API-szerződés tesztelése.

## 5. Dokumentumfeldolgozás és RAG

- szöveg- és Markdown-betöltő;
- darabolási stratégia;
- embedding-port és adapter;
- ChromaDB adapter;
- forrásmegjelölés;
- később PDF és DOCX.

Elfogadási feltétel: egy indexelt dokumentumból visszakeresett válasz
ellenőrizhető forráshivatkozást tartalmaz.

## 6. Hosszú távú memória

- elkülönített memóriatár;
- mentési és visszakeresési szabályok;
- deduplikáció;
- felhasználói listázás és törlés;
- később összefoglalás és elévülés.

## 7. Open WebUI

- helyi integráció;
- API-kapcsolat;
- hálózati korlátozás;
- üzemeltetési dokumentáció.

## 8. PowerShell agentkliens

- `kelvin` terminálparancs;
- interaktív munkamenet és folytatás;
- aktuális munkakönyvtár kezelése;
- fájl-, keresési és Git-eszközök;
- PowerShell-végrehajtó;
- jóváhagyási módok és auditnapló;
- diffalapú változásellenőrzés.

Elfogadási feltétel: az agent csak a megadott munkakönyvtárban és a
jóváhagyott jogosultságokkal tud állapotot változtatni.

## 9. Hang

- Whisper beszédfelismerő adapter;
- Piper TTS adapter;
- hangfolyam és megszakítás;
- eszközválasztás és késleltetési mérés.

## 10. Automatizálás

- ütemezhető feladatok;
- korlátozott automatizálási eszközök;
- explicit jogosultságok;
- biztonságos leállítás és auditálás.
