# v0.7 Safe n8n Foundation

## Cél

A v0.7 célja egy külön Ubuntu Server VM-en futó, self-hosted n8n Community
Edition létrehozása, majd egy korlátozott és hitelesített kapcsolat kialakítása
n8n és Kelvin között.

Az n8n az online automatizációért felel:

- vizuális workflow-szerkesztés;
- manuális és időzített triggerek;
- engedélyezett webes, RSS- és API-források lekérése;
- online AI-szolgáltatások meghívása;
- online credentialök titkosított tárolása;
- workflow-szintű hibakezelés és futástörténet.

Kelvin a helyi intelligencia és végrehajtási szabályok tulajdonosa marad:

- helyi LLM, RAG és memória;
- agenttervezés;
- determinisztikus tool policy;
- író műveletek helyi jóváhagyása;
- agent- és eszközfutások auditja.

Az online n8n kiesése nem akadályozhatja Kelvin helyi chat-, RAG-, memória- vagy
agentfunkcióit.

## Célarchitektúra

```text
Windows 11 host
├── Hyper-V
├── Ollama + AMD GPU
├── Kelvin PowerShell kliens
│
├── VM 1: kelvin-ai
│   ├── Kelvin FastAPI
│   ├── PostgreSQL + pgvector
│   └── később: Kelvin Docker Compose stack
│
└── VM 2: kelvin-automation
    └── Docker Compose
        ├── n8n
        └── n8n PostgreSQL
```

Az Ollama natívan a Windows hoston marad. Ennek oka a már működő AMD
GPU-gyorsítás megőrzése. A `kelvin` kliens szintén natív marad, mert a valódi
Windows workspace-hez és a helyi felhasználói jóváhagyáshoz fér hozzá.

## Miért külön automation VM?

Az n8n internetes forrásokat és külső API-kat használhat, ezért más
megbízhatósági tartományba tartozik, mint Kelvin offline core-ja.

Előnyök:

- n8n-frissítés vagy workflow-hiba nem állítja le Kelvint;
- az online szolgáltatások kulcsai nem kerülnek a Kelvin VM-re;
- a két rendszer külön menthető, visszaállítható és újratelepíthető;
- a tűzfal pontosan korlátozhatja az n8n által elérhető Kelvin-végpontokat;
- az automation VM később másik hostra költöztethető;
- az internetet használó komponens kisebb támadási felületre korlátozható.

Kompromisszumok:

- két Ubuntu rendszert kell frissíteni és felügyelni;
- több memória és tárhely szükséges;
- több hálózati és mentési szabályt kell dokumentálni.

A jelenlegi, 16 GB memóriás hoston két VM még ésszerű kompromisszum. További
VM-eket csak mérés és valós izolációs igény alapján hozunk létre.

## Automation VM kezdeti erőforrásai

Javasolt kiinduló konfiguráció:

- Ubuntu Server 24.04 LTS, Generation 2 VM;
- 2 virtuális processzor;
- 3 GB memória;
- 40 GB dinamikusan növekvő VHDX;
- külső Hyper-V switch;
- rögzített DHCP-cím vagy DHCP reservation;
- OpenSSH kizárólag a helyi adminisztrációhoz.

Az erőforrásokat az első valós workflow-k futtatása után mérés alapján
módosítjuk.

## n8n futtatási modell

Az automation VM-en Docker Engine és Docker Compose fut. Az első stack két
konténert tartalmaz:

```text
n8n
n8n-postgres
```

Az n8n PostgreSQL-e nem azonos Kelvin PostgreSQL adatbázisával. A két
adatbázis külön credentialt, volume-ot és mentési folyamatot kap.

Repositoryban tárolható:

```text
infrastructure/n8n/
├── compose.yaml
├── n8n.env.example
└── README.md
```

Nem kerülhet repositoryba:

- valódi n8n környezeti fájl;
- `N8N_ENCRYPTION_KEY`;
- adatbázisjelszó;
- Kelvin API-token;
- online szolgáltatások API-kulcsai;
- credentialt tartalmazó workflow-export.

Production konfigurációban nem használunk `latest` image taget. A kiválasztott
stabil verziókat pontos taggel, szükség esetén digesttel rögzítjük.

## Hálózati határok

Az automation VM:

- az n8n editort csak a Windows host felől teszi elérhetővé;
- az n8n PostgreSQL portját nem publikálja a VM hálózatára;
- Kelvin API-jából csak a szükséges `8000/tcp` portot éri el;
- nem kap SMB-megosztást vagy host workspace mountot;
- nem kap hozzáférést a Windows Docker sockethez;
- nem kezdeményezhet közvetlen PowerShell-végrehajtást a hoston.

A Kelvin VM:

- a `8000/tcp` portot csak a Windows host és az automation VM rögzített
  IP-címéről engedélyezi;
- PostgreSQL portját továbbra sem nyitja ki az automation VM felé;
- minden n8n-kérést token és scope alapján ellenőriz.

Nyilvános n8n webhookot a v0.7-ben nem teszünk közzé. Ehhez később külön HTTPS,
hitelesítés, rate limit és webhook allowlist szükséges.

## Credential-kezelés

Az online AI- és integrációs kulcsokat az n8n credential store kezeli. Kelvin
csak a workflow eredményét kapja meg, a szolgáltatói kulcsot nem.

Kötelező szabályok:

- minden szolgáltató külön, minimális jogosultságú credentialt kap;
- az `N8N_ENCRYPTION_KEY` telepítéskor generált, hosszú véletlen érték;
- az encryption key az n8n adatmentésétől elkülönítve is mentésre kerül;
- credential nem kerül promptba, Code node-ba, naplóba vagy workflow JSON-ba;
- community node csak külön kód- és jogosultságvizsgálat után telepíthető;
- az n8n owner fiók erős jelszót és 2FA-t kap;
- a workflow-futások érzékeny bemenetei és kimenetei maszkolásra kerülnek.

Az encryption key elvesztése után az adatbázisban tárolt credentialök nem
állíthatók helyre, ezért a kulcs mentése a telepítés elfogadási feltétele.

## Kelvin API-jogosultságok

A hozzáférés nem HTTP-metódus, hanem képesség alapján válik szét. Egy chat vagy
keresés POST kérés lehet úgy is, hogy nem módosít állapotot.

Tervezett scope-ok:

| Scope | Engedély |
| --- | --- |
| `kelvin:read` | chat, RAG-keresés, állapot- és verziólekérdezés |
| `memory:write` | memória létrehozása és törlése |
| `agent:execute` | agentfutás kezdeményezése |
| `agent:write` | író tool javaslata |
| `agent:approve` | állapotváltoztató művelet jóváhagyása |

Az első kutató workflow kizárólag `kelvin:read` tokent kap. Az approve scope nem
kerül általános automation credentialbe.

A meglévő agent tool policy továbbra is érvényes:

- read tool engedélyezhető az autorizált workspace-ben;
- write tool teljes diffet és helyi jóváhagyást igényel;
- destructive és privileged tool alapértelmezetten tiltott.

## Első integráció

Az első Kelvin-integráció az n8n beépített HTTP Request node-ját használja. Saját
Kelvin node-ot csak legalább két stabil workflow után készítünk, amikor már
pontosan ismertek a szükséges műveletek és válaszformátumok.

Első kapcsolatpróba:

```text
Manual Trigger
  -> HTTP Request: Kelvin /health
  -> If: status == ok
  -> Set: human-readable result
```

Első funkcionális kutató workflow:

```text
Manual vagy Schedule Trigger
  -> engedélyezett RSS/API/web források lekérése
  -> normalizálás és duplikációszűrés
  -> minimum AI Firewall
  -> online szöveges AI összefoglaló
  -> Kelvin read-only értékelés helyi RAG és roadmap alapján
  -> hivatkozott fejlesztési javaslat
  -> emberi elfogadás vagy elutasítás
```

A v0.7-ben egyetlen online szöveges AI-szolgáltatót használunk. Kódoló és
képgeneráló szolgáltató csak a működő alapfolyamat és a biztonsági ellenőrzések
után kerül be.

## Minimum AI Firewall

A v0.7 még nem teljes AI Security Gateway, de az online kutatás előtt kötelező
minimumot biztosít:

- csak név szerint engedélyezett források olvashatók;
- a külső tartalom adat, nem Kelvinnek szóló rendszerutasítás;
- a forrás URL-je és lekérési ideje megmarad;
- credentialre, `.env` fájlra vagy privát kulcsra irányuló kérés blokkolható;
- külső szöveg nem válthat ki közvetlen tool-hívást;
- ismert titokminták válasz és napló előtt maszkolásra kerülnek;
- minden futás oldal-, idő- és költségkorlátot kap.

A teljes input, context, output és tool guard a v0.8 része.

## Fokozatos konténerizálás

A cél container-ready, de nem container-only Kelvin platform.

Natív marad:

- Windows Ollama a GPU-hozzáférés miatt;
- Windows `kelvin` kliens a workspace és helyi jóváhagyás miatt.

Konténerbe kerül:

- n8n és saját PostgreSQL-e már a v0.7-ben;
- Kelvin FastAPI először külön tesztkörnyezetben;
- Kelvin PostgreSQL csak sikeres dump/restore és párhuzamos validáció után.

A jelenlegi systemd-alapú Kelvin telepítést addig megtartjuk, amíg a Compose
változat nem teljesíti ugyanazokat a teszteket és üzemeltetési ellenőrzéseket.
Nem végzünk egyszeri, teljes „big bang” migrációt.

## Mentés és visszaállítás

A VM checkpoint, a konténerkonfiguráció és az adatmentés külön célokat szolgál:

- Hyper-V checkpoint: rövid életű visszagörgetési pont;
- VM-export: teljes appliance helyreállítása;
- Compose és rögzített image-ek: reprodukálható újraépítés;
- PostgreSQL dump: konzisztens alkalmazásadat-visszaállítás;
- volume-mentés: n8n futásidejű fájlok helyreállítása;
- külön encryption key mentés: credentialök visszafejthetősége.

Mentendő:

- n8n PostgreSQL dump;
- n8n és PostgreSQL volume-ok;
- `N8N_ENCRYPTION_KEY`, elkülönített biztonságos helyen;
- pontos image tagek és digestek;
- titokmentes workflow-exportok;
- Compose fájl és dokumentált visszaállítási sorrend.

Checkpointot futó adatbázis egyetlen hosszú távú mentéseként nem használunk.

## Implementációs sorrend

1. A második Ubuntu Server VM létrehozása.
2. Erőforrás-, hálózat-, SSH- és UFW-ellenőrzés.
3. Docker Engine és Compose telepítése.
4. Verziórögzített n8n + PostgreSQL Compose stack elkészítése.
5. Encryption key és többi secret létrehozása közvetlenül az automation VM-en.
6. n8n owner fiók, 2FA és helyi hozzáférés beállítása.
7. Reboot utáni automatikus indulás ellenőrzése.
8. Kelvin API tokenes és scope-alapú hitelesítésének implementálása.
9. Read-only `/health` és Kelvin API kapcsolatpróba.
10. Első, egy szolgáltatós kutató workflow.
11. Minimum AI Firewall és rosszindulatú forrással végzett teszt.
12. PostgreSQL dump, volume-mentés és visszaállítási próba.
13. Ideiglenes Hyper-V checkpointok törlése a sikeres validáció után.

## v0.7 elfogadási feltételek

- [ ] külön automation VM fut Ubuntu Server 24.04 LTS rendszerrel;
- [ ] n8n és saját PostgreSQL-e Docker Compose alatt fut;
- [ ] egyik image sem használ `latest` taget;
- [ ] n8n felülete csak a megbízható helyi hálózatról érhető el;
- [ ] PostgreSQL port nem kerül publikálásra;
- [ ] encryption key és adatbázismentés külön visszaállítható;
- [ ] Kelvin API token- és scope-alapú hitelesítést használ;
- [ ] a kutató workflow csak read-only Kelvin credentialt kap;
- [ ] online AI-kulcs nem kerül Kelvinhez, Gitbe vagy workflow-exportba;
- [ ] egy hivatkozott fejlesztési javaslatot készítő workflow sikeresen lefut;
- [ ] webes prompt injection nem indíthat Kelvin toolt;
- [ ] n8n nem kerülheti meg a Windows agent jóváhagyását;
- [ ] n8n kiesése mellett Kelvin helyi funkciói működnek;
- [ ] reboot, backup és restore ellenőrzése sikeres;
- [ ] a telepítéshez használt ideiglenes checkpointok törlésre kerülnek.

## Hivatalos hivatkozások

- [n8n Docker telepítés](https://docs.n8n.io/hosting/installation/docker/)
- [n8n Docker Compose telepítés](https://docs.n8n.io/hosting/installation/server-setups/docker-compose/)
- [Egyedi encryption key](https://docs.n8n.io/hosting/configuration/configuration-examples/encryption-key/)
- [n8n biztonsági útmutató](https://docs.n8n.io/hosting/securing/overview/)
- [Security audit](https://docs.n8n.io/hosting/securing/security-audit/)
- [Community Edition képességek](https://docs.n8n.io/hosting/community-edition-features/)
- [Sustainable Use License](https://docs.n8n.io/sustainable-use-license/)
