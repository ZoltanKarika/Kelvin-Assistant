# v0.6 Agent architektúra

## Cél

A v0.6 célja, hogy Kelvin a válaszadás mellett ellenőrzött helyi műveleteket
is tudjon javasolni és végrehajtani. Az elsődleges felület egy későbbi
`kelvin` PowerShell-kliens lesz a Windows hoston.

Az agent nem kap korlátlan hozzáférést a géphez. A nyelvi modell tervet és
strukturált eszközhívást javasol, de a szabályok ellenőrzése, a jóváhagyás és
a végrehajtás determinisztikus programkódban történik.

## Mi az az AI agent?

Egy hagyományos chatfolyamat bemenetet kap, majd szöveget ad vissza. Egy agent
ezzel szemben több lépésben dolgozhat:

1. megérti a felhasználó célját;
2. eldönti, hogy elegendő-e az információ;
3. szükség esetén visszakérdez;
4. tervet készít;
5. eszközt választ;
6. jóváhagyást kér;
7. végrehajtja az engedélyezett műveletet;
8. megfigyeli az eredményt;
9. folytatja a tervet vagy összefoglalja az eredményt.

A fontos különbség: az LLM nem maga futtatja a parancsot. Csak egy
ellenőrizhető műveleti kérést állít elő.

## A v0.6 határai

A v0.6 része:

- agent domain modellek és állapotgép;
- strukturált eszközregiszter;
- célzott visszakérdezési szabály;
- terv és műveleti javaslat;
- kockázati besorolás;
- felhasználói jóváhagyás;
- Windows hoston futó PowerShell-kliens;
- első fájl-, keresési és Git-eszközök;
- munkakönyvtár-korlátozás;
- auditnapló és megszakítás;
- unit és integrációs tesztek.

Nem része:

- autonóm, felügyelet nélküli hosszú futás;
- rendszergazdai jogosultság automatikus megszerzése;
- tetszőleges internetes szolgáltatás használata;
- jelszavak vagy tokenek kiolvasása;
- időzített workflow-k;
- teljes n8n-szerű vizuális szerkesztő.

A workflow-szerkesztő a v0.7, a tartós automatizációs futtatómotor pedig a
v0.8 része. Mindkettő a v0.6 biztonságos eszközmodelljére épül majd.

## Telepítési kép

### Ubuntu VM

Az Ubuntu oldalon marad:

- FastAPI backend;
- agent alkalmazási logika;
- LLM-, RAG- és memóriakapcsolat;
- eszközleírások és központi policy;
- agent session és auditadatok perzisztenciája.

### Windows host

A Windows oldalon fut:

- Ollama és a helyi modellek;
- interaktív `kelvin` PowerShell-kliens;
- felhasználói jóváhagyási felület;
- fájl-, Git- és PowerShell-eszközök tényleges végrehajtása;
- második, hostoldali jogosultság- és útvonal-ellenőrzés.

A Windows kliens kezdeményezi a kapcsolatot az Ubuntu API felé. A v0.6
alapváltozatában nem nyitunk új bejövő végrehajtási portot a Windows hoston.

## Fő komponensek

### AgentService

Az alkalmazási réteg koordinátora. Feladata:

- az agent állapotának kezelése;
- a modell meghívása a rendelkezésre álló eszközleírásokkal;
- visszakérdezés vagy terv létrehozása;
- eszközkérések validálása;
- végrehajtási eredmények visszacsatolása;
- a ciklus és a lépésszám korlátozása.

Az `AgentService` nem importálhat FastAPI-, PowerShell- vagy Git-specifikus
kódot.

### ToolRegistry

Az engedélyezett eszközök katalógusa. Minden eszköznek van:

- stabil neve;
- emberi leírása;
- típusos bemeneti sémája;
- kockázati szintje;
- végrehajtási helye;
- timeoutja;
- deklarált állapotváltoztatási tulajdonsága.

Ismeretlen vagy hibás paraméterű eszközkérés alapértelmezetten tiltott.

### PolicyEngine

Determinista szabályok alapján eldönti, hogy egy kérés:

- automatikusan végrehajtható;
- felhasználói jóváhagyást igényel;
- teljesen tiltott.

Az LLM által megadott kockázati szint csak tájékoztató adat. A végső
besorolást programkód végzi.

### Windows Agent Client

A `kelvin` kliens:

- elküldi a felhasználói célt a backendnek;
- megjeleníti a tervet és a műveleti javaslatot;
- bekéri a jóváhagyást;
- ismét ellenőrzi az eszközt és a munkakönyvtárat;
- helyben végrehajtja az engedélyezett műveletet;
- strukturált eredményt küld vissza;
- lehetővé teszi a megszakítást.

### ToolExecutor adapterek

Az eszközleírás és a végrehajtó külön komponens. Példák:

- `file.read`;
- `file.search`;
- `git.status`;
- `git.diff`;
- később `file.patch`;
- később korlátozott `powershell.run`.

Ez lehetővé teszi, hogy az alkalmazási logikát valódi PowerShell nélkül,
memóriabeli tesztadapterrel ellenőrizzük.

### AuditRepository

Az auditnapló legalább az alábbiakat tárolja:

- agent session és lépés azonosítója;
- időpont;
- eszköz neve;
- normalizált munkakönyvtár;
- kockázati döntés;
- jóváhagyás eredménye;
- futási állapot és időtartam;
- kimenet rövidített összegzése;
- hibatípus.

Titkok, teljes környezeti változók és korlátlan fájltartalom nem kerülhetnek
az auditnaplóba.

## Agent állapotgép

Tervezett állapotok:

```text
received
  -> clarifying
  -> planning
  -> awaiting_approval
  -> executing
  -> observing
  -> completed

Bármely aktív állapotból:
  -> cancelled
  -> failed
```

Az állapotváltások explicit alkalmazási műveletek. Egy API-kérés nem
ugorhatja át a jóváhagyási állapotot.

## Visszakérdezési szabály

Kelvin nem kérdez vissza automatikusan minden promptnál. Ez lassú és
fárasztó lenne. Akkor kér pontosítást, ha:

- több lényegesen eltérő értelmezés lehetséges;
- hiányzik egy kötelező cél, fájl, környezet vagy eredményforma;
- a feltételezés állapotváltoztatást vagy adatvesztési kockázatot okozhat;
- a választás jelentősen befolyásolja az eredményt.

Nem szükséges visszakérdezni, ha:

- a kérés egyértelmű és csak olvasási műveletet igényel;
- biztonságos, könnyen visszafordítható alapértelmezés használható;
- a hiányzó részlet helyi, nem módosító ellenőrzéssel felderíthető.

A visszakérdezés és a végrehajtási jóváhagyás két külön dolog. Az első a cél
pontosításáról, a második egy már ismert művelet engedélyezéséről szól.

## Kockázati és jóváhagyási modell

### `read`

Példák:

- fájllista a munkakönyvtáron belül;
- szövegkeresés;
- `git status`;
- `git diff`.

Alapértelmezés: automatikusan engedélyezhető, ha a célútvonal a jóváhagyott
munkakönyvtáron belül marad.

### `write`

Példák:

- fájl létrehozása vagy módosítása;
- formázó futtatása;
- Git stage vagy commit.

Alapértelmezés: előnézet és felhasználói jóváhagyás szükséges.

### `destructive`

Példák:

- fájl törlése;
- branch kényszerített átírása;
- folyamat leállítása;
- adatbázis rekordjainak tömeges törlése.

Alapértelmezés: v0.6-ban tiltott, vagy külön, műveletenkénti megerősítés és
szigorú adapter szükséges.

### `privileged`

Példák:

- rendszergazdai PowerShell;
- tűzfalszabály módosítása;
- rendszerkönyvtár írása;
- szolgáltatás telepítése.

Alapértelmezés: a v0.6 agent számára tiltott. Ezek továbbra is kézi,
dokumentált üzemeltetési lépések.

## Strukturált eszközkérés

Egy műveleti javaslat logikai formája:

```json
{
  "tool_call_id": "uuid",
  "tool_name": "git.status",
  "arguments": {
    "workspace": "C:\\Users\\Zoltan\\Documents\\Kelvin Assistant"
  },
  "reason": "A módosított fájlok ellenőrzése szükséges a tervhez.",
  "expected_effect": "Nincs állapotváltozás."
}
```

A modell nem küldhet végrehajtható PowerShell-kódrészletet strukturált
argumentum helyett. A kliens csak regisztrált eszköznevet fogad el.

## Munkakönyvtár-biztonság

Minden fájl- és Git-művelet előtt:

1. a kliens abszolút, kanonikus útvonalat képez;
2. ellenőrzi, hogy az útvonal a jóváhagyott workspace alatt marad;
3. elutasítja a workspace-ből kivezető relatív útvonalat és symlinket;
4. nem ad át összefűzött parancsszöveget másik shellnek;
5. módosítás előtt diffet vagy egyenértékű előnézetet készít.

## Hibák és korlátok

- maximális agentlépésszám megakadályozza a végtelen ciklust;
- minden eszköznek timeoutja van;
- a megszakítás új eszköz indítását tiltja;
- részleges végrehajtás esetén Kelvin nem állíthatja, hogy a teljes feladat
  elkészült;
- az eszközkimenet mérete korlátozott és szükség esetén rövidített;
- modellhiba nem kerülhető meg nyers parancsvégrehajtással;
- a backend vagy kliens kapcsolatvesztésekor a függőben lévő jóváhagyás
  érvényét veszti.

## Első implementációs szeletek

1. Agent domain modellek és állapotátmenetek unit tesztekkel.
2. Tool port, típusos eszközséma és memóriabeli registry.
3. Policy engine a négy kockázati szinttel.
4. AgentService visszakérdezési, tervezési és jóváhagyási folyamata.
5. Verziózott agent API-szerződés.
6. Minimális PowerShell `kelvin` kliens bejövő hostport nélkül.
7. Első read-only eszközök: fájlkeresés, `git status`, `git diff`.
8. Egy jóváhagyásköteles, diffalapú fájlmódosítási útvonal.
9. Audit repository és production validáció.

Minden szelet külön kis Conventional Commit és lehetőség szerint külön
pull request.

## Elfogadási feltételek

A v0.6 akkor kész, ha:

- [ ] egyértelmű olvasási feladatot Kelvin felesleges visszakérdezés nélkül
      meg tud tervezni;
- [ ] kétértelmű vagy kockázatos kérésnél célzottan visszakérdez;
- [ ] ismeretlen eszközt vagy workspace-en kívüli útvonalat elutasít;
- [ ] állapotváltoztató művelet jóváhagyás nélkül nem fut le;
- [ ] a Windows kliens legalább fájlkeresést és Git állapotellenőrzést tud
      végrehajtani;
- [ ] legalább egy fájlmódosítás diff-előnézettel és jóváhagyással működik;
- [ ] minden végrehajtási kísérlet auditálható;
- [ ] a folyamat megszakítható;
- [ ] az agent internet nélkül is működik.

## Kapcsolódó döntések

- [ADR-0001: Portok és adapterek](decisions/0001-ports-and-adapters.md)
- [ADR-0002: Hostoldali PowerShell-végrehajtás](decisions/0002-host-side-powershell-execution.md)
- [ADR-0010: Kliens által közvetített strukturált agentciklus](decisions/0010-client-mediated-agent-loop.md)

