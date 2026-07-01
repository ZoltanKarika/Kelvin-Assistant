# ADR-0012: Strukturált, szolgáltatófüggetlen agent planner

- Állapot: Accepted
- Dátum: 2026-07-01

## Kontextus

A v0.6 agent jelenleg explicit CLI-parancsokkal képes regisztrált
eszközöket használni. A felhasználónak azonban ismernie kell az eszköz nevét és
argumentumait, például `git status` vagy `file search`. A következő cél, hogy
Kelvin természetes nyelvű kérésből tudjon biztonságos eszközjavaslatot vagy
célzott visszakérdezést készíteni.

A nyelvi modell kimenete nem megbízható végrehajtási utasítás. Lehet hibás,
hiányos, nem létező eszközt tartalmazó vagy a promptban szereplő káros
utasítás által befolyásolt. Emiatt a planner és a végrehajtás között kötelező
marad a típusos validáció, az eszközregistry és a determinisztikus policy.

## Döntés

Az alkalmazási rétegben szolgáltatófüggetlen `AgentPlanner` portot vezetünk
be. A planner egyetlen, diszkriminált strukturált döntést adhat vissza:

```json
{
  "action": "clarify",
  "question": "Melyik szöveget szeretnéd lecserélni?",
  "reason": "A célfájl ismert, de a módosítandó részlet nem."
}
```

```json
{
  "action": "tool",
  "tool_name": "git.status",
  "arguments": {
    "include_untracked": true
  },
  "reason": "A repository állapotát kell megvizsgálni.",
  "expected_effect": "A workspace nem változik."
}
```

```json
{
  "action": "complete",
  "summary": "A feladat nem igényel további eszközhívást."
}
```

A modell nem adhat meg kockázati szintet, végrehajtási célt, jóváhagyási
döntést vagy nyers shellparancsot. Ezek megbízható forrása a szerveroldali
`ToolRegistry` és policy.

## Planner bemenet

A planner csak a szükséges, korlátozott kontextust kapja:

- az eredeti felhasználói cél;
- az engedélyezett eszközök neve, leírása és JSON-sémája;
- az aktuális agentállapot és hátralévő lépésszám;
- opcionális korábbi pontosító kérdés és felhasználói válasz;
- az előző eszközmegfigyelés korlátozott kimenete.

Jelszó, teljes környezeti változó, korlátlan fájltartalom és nem regisztrált
eszközleírás nem kerülhet a planner promptjába.

## Validáció és hibakezelés

1. A provider adapter strukturált választ kér a modelltől.
2. A válasz JSON- és domain-validáción megy át.
3. `tool` döntésnél a szerver megkeresi az eszközt a registryben.
4. Az argumentumoknak meg kell felelniük az eszköz deklarált sémájának.
5. A kockázatot a registry adja, nem a modell.
6. A meglévő determinisztikus policy dönt az engedélyezésről.
7. Érvénytelen modellválasz esetén legfeljebb egy javító újrapróbálkozás
   engedélyezett.
8. A második hibás válasz sikertelen agentfutást eredményez; eszköz nem fut.

Az újrapróbálkozás nem növelheti az agent végrehajtási lépésszámát, mert nem
történt eszközvégrehajtás, de külön naplóeseményként megfigyelhető.

## API és kliensciklus

A verziózott agent API egy `next` műveletet kap:

```text
POST /api/v1/agent/runs/{run_id}/next
```

A kérés opcionálisan korlátozott pontosítási kontextust tartalmazhat. A válasz
a planner három döntésének egyikét adja vissza:

- `clarify`: kérdés és indoklás, a run `clarifying` állapotba kerül;
- `tool`: a meglévő policy által értékelt `ToolProposal`;
- `complete`: összegzés, a run `completed` állapotba kerül.

A Windows kliens természetes nyelvű belépési pontja:

```powershell
kelvin agent "Mutasd meg a Git állapotát"
```

Pontosítás esetén a kliens bekéri a választ és újra meghívja a `next`
műveletet. Tool döntésnél ugyanazt a már működő proposal, approval, helyi
végrehajtás és result API-folyamatot használja. A planner nem kap külön
végrehajtási útvonalat.

## Provider adapter

Az első adapter Ollamát és a helyi Gemma modellt használja. Ha a provider
megbízható natív JSON-sémát kínál, az adapter használhatja. Más provider vagy
modell esetén promptolt JSON és ugyanaz a szerveroldali validáció alkalmazható.
Az alkalmazási réteg nem importál Ollama-specifikus típust.

## Alternatívák

### Natív Ollama tool calling közvetlenül az AgentService-ben

Elvetve. Egyszerűbb első implementáció lenne, de az alkalmazási logikát az
Ollama válaszformátumához kötné, és nehezítené a Gemma, Qwen, Llama vagy más
provider közötti cserét.

### Nyers szöveges terv reguláris kifejezésekkel

Elvetve. Lokalizált, több soros és modellfüggő válaszoknál törékeny, valamint
nehezen különíthető el az indoklás a végrehajtható argumentumoktól.

### A modell közvetlenül futtatja a toolt

Elvetve. Megkerülné a registryt, a policyt, a workspace-ellenőrzést és a
felhasználói jóváhagyást.

### Minden kérésnél kötelező visszakérdezés

Elvetve. Az egyértelmű read-only feladatokat indokolatlanul lassítaná. A
plannernek csak akkor kell `clarify` döntést adnia, ha a hiányzó információ
érdemben megváltoztatja a műveletet vagy annak kockázatát.

## Következmények

Előnyök:

- természetes nyelvű agenthasználat regisztrált eszközökkel;
- modell- és providerfüggetlen alkalmazási szerződés;
- a jelenlegi policy, approval és audit réteg változatlanul megmarad;
- a planner külön hamis adapterrel unit tesztelhető;
- a későbbi n8n-integráció ugyanazt a döntési modellt használhatja.

Hátrányok:

- egy agentlépés újabb LLM-hívást és késleltetést jelent;
- strukturált output mellett is szükséges javító retry és hibatűrés;
- a pontosítási kontextust méretkorláttal kell kezelni;
- gyengébb magyar modell esetén az eszközválasztás minősége külön
  finomhangolást igényelhet.

## Elfogadási feltétel

Egy egyértelmű természetes nyelvű read-only kérésből Kelvin helyes,
regisztrált tool proposal-t készít. Hiányos író kérésnél célzottan
visszakérdez. Ismeretlen eszköz, hibás argumentum vagy két egymást követő
érvénytelen modellválasz esetén semmilyen helyi eszköz nem fut le.
