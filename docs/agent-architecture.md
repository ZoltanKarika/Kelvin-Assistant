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

A workflow-szerkesztést és az automatizációs futtatómotort a self-hosted n8n
biztosítja. A v0.7 és v0.8 feladata ezért az n8n integrációja és megerősítése,
nem egy külön Kelvin workflow-motor megépítése. Az n8n a v0.6 biztonságos
agent API-ját használja, és nem kerülheti meg a helyi jóváhagyásokat.

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

### AgentPlanner

Az `AgentPlanner` port természetes nyelvű célból pontosan egy strukturált
döntést készít:

- `clarify`: célzott kérdés, ha lényeges adat hiányzik;
- `tool`: regisztrált eszköz neve és típusos argumentumai;
- `complete`: a feladat lezárható további eszköz nélkül.

A planner megkapja a registry eszközleírásait, de nem állíthat be kockázati
szintet és nem hagyhat jóvá műveletet. A planner kimenete nem végrehajtási
engedély: minden `tool` döntés ugyanúgy átmegy a domain-validáción, a
registryn, a policy engine-en és szükség esetén a felhasználói jóváhagyáson.

Az első provider adapter Ollamát használ. Az alkalmazási réteg csak az
`AgentPlanner` portot ismeri, ezért később más helyi modell vagy provider az
agentciklus átírása nélkül hozzáadható.

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

A természetes nyelvű planner teljes szerződését és hibatűrését az
[ADR-0012](decisions/0012-structured-agent-planner.md) rögzíti.

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
- a Windows kliens `Ctrl+C` esetén best-effort meghívja a
  `POST /api/v1/agent/runs/{run_id}/cancel` végpontot;
- a cancel művelet atomikusan `cancelled` állapotba teszi a futást és lezárja
  az aktív tool proposalt;
- a már terminális futás eredménye megszakítással nem írható felül;
- folyamatban lévő helyi gyermekfolyamat megszakításkor leáll;
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

## Első Windows kliens

A `kelvin` kliens természetes nyelvű agentlépést, három olvasási eszközt és
egy jóváhagyásköteles fájlmódosítást támogat:

```powershell
uv run kelvin --api-url http://192.168.10.13:8000 `
  --workspace-id kelvin-assistant agent "Show the current Git status."

uv run kelvin --api-url http://192.168.10.13:8000 `
  --workspace-id kelvin-assistant git status

uv run kelvin --api-url http://192.168.10.13:8000 `
  --workspace-id kelvin-assistant git diff

uv run kelvin --api-url http://192.168.10.13:8000 `
  --workspace-id kelvin-assistant file search "AgentService"

uv run kelvin --api-url http://192.168.10.13:8000 `
  --workspace-id kelvin-assistant file patch README.md `
  --old-text "old value" --new-text "new value"
```

A kliens az aktuális könyvtárat használja workspace-ként, hacsak a
`--workspace` opció mást nem ad meg. A gyakran használt értékek a
`KELVIN_API_URL`, `KELVIN_WORKSPACE_ID` és `KELVIN_WORKSPACE_PATH`
környezeti változókkal is beállíthatók.

A Windows kliens API-kérésenként alapértelmezetten 120 másodpercet vár, mert a
planner hibás strukturált modellválasz esetén egy javítási kört is indíthat.
Az érték a `--timeout-seconds` kapcsolóval vagy a
`KELVIN_API_TIMEOUT_SECONDS` környezeti változóval módosítható.

Az `agent` alparancs természetes nyelvű célt küld a planner API-nak. A kliens
egy korlátozott, többfordulós ciklusban három strukturált döntést kezel:

- `clarify`: kiírja a planner célzott kérdését és bekéri a választ;
- `tool`: a policy által ellenőrzött eszközt helyben végrehajtja;
- `complete`: kiírja a planner összefoglalóját.

Sikeres eszközfutás után a korlátozott kimenet observationként visszakerül a
plannerhez. A ciklus legfeljebb az agentfutás `max_steps` értékéig tarthat.
Minden állapotváltoztató eszköz továbbra is külön helyi jóváhagyást kér.

Minden parancs létrehoz egy backend által kezelt agentfutást. A backend
ellenőrzi az eszközt és a workspace azonosítóját, a tényleges Git- vagy
fájlolvasás viszont a Windows kliensen fut. A VM ezért nem kap hozzáférést
a Windows fájlrendszeréhez, és a modell nem küldhet tetszőleges shellparancsot.

A `file patch` az egyetlen kezdeti író eszköz. Pontosan egy szövegrészletet
cserélhet le egy UTF-8 fájlban. A kliens előbb teljes unified diffet mutat,
majd `[y/N]` választ kér. Csak az explicit `y` vagy `yes` engedélyezi az
írást. Ha a fájl a preview és a végrehajtás között megváltozik, a művelet
megszakad és új preview szükséges.

## Elfogadási feltételek

A v0.6 akkor kész, ha:

- [x] egyértelmű olvasási feladatot Kelvin felesleges visszakérdezés nélkül
      meg tud tervezni;
- [x] kétértelmű vagy kockázatos kérésnél célzottan visszakérdez;
- [x] ismeretlen eszközt vagy workspace-en kívüli útvonalat elutasít;
- [x] állapotváltoztató művelet jóváhagyás nélkül nem fut le;
- [x] a Windows kliens legalább fájlkeresést és Git állapotellenőrzést tud
      végrehajtani;
- [x] legalább egy fájlmódosítás diff-előnézettel és jóváhagyással működik;
- [x] minden végrehajtási kísérlet auditálható;
- [x] a folyamat megszakítható;
- [x] az agent internet nélkül is működik.

## Production validáció

Az elfogadási feltételek 2026. július 1-jén a tényleges Windows 11 host és
Ubuntu Server 24.04 VM között lettek ellenőrizve:

- természetes nyelvű cél → `git.status` planner döntés;
- hostoldali végrehajtás → observation → `complete` planner döntés;
- sikeres futás PostgreSQL `completed` állapottal;
- `Ctrl+C` → cancel API → PostgreSQL `cancelled` állapot;
- teljes quality check és `308 passed`.

A validáció során az Ollama és a Gemma modell a Windows hoston, Kelvin és a
PostgreSQL pedig az Ubuntu VM-en futott. Külső AI API nem vett részt a
folyamatban.

## Kapcsolódó döntések

- [ADR-0001: Portok és adapterek](decisions/0001-ports-and-adapters.md)
- [ADR-0002: Hostoldali PowerShell-végrehajtás](decisions/0002-host-side-powershell-execution.md)
- [ADR-0010: Kliens által közvetített strukturált agentciklus](decisions/0010-client-mediated-agent-loop.md)
