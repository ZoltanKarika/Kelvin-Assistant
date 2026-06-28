# ADR-0004: Verziózott chat API és szerveroldali sessionök

- Állapot: Accepted
- Dátum: 2026-06-28

## Kontextus

A v0.3 Conversation mérföldkőben a PowerShell-kliensnek és a későbbi webes
felületnek stabil chat API-ra van szüksége. A backendnek többfordulós
beszélgetést kell kezelnie úgy, hogy az API ne függjön az Ollama saját
HTTP-formátumától. A későbbi streamingnek és tartós memóriának is ugyanarra
az alkalmazási rétegre kell épülnie.

## Döntés

Az első nem streamelt chat végpont:

```text
POST /api/v1/chat
```

Kérés:

```json
{
  "message": "Szia!",
  "session_id": null
}
```

Válasz:

```json
{
  "session_id": "0197f25c-f017-7ee4-9f40-f9f771ccac35",
  "message": "Szia! Miben segíthetek?",
  "model": "gemma4:e4b"
}
```

Szabályok:

- a `message` nem lehet üres vagy csak whitespace, és méretkorlátot kap;
- hiányzó `session_id` esetén a backend új, átlátszatlan UUID-t hoz létre;
- ismeretlen `session_id` HTTP 404 választ ad;
- ugyanazon session párhuzamos módosítása HTTP 409 választ ad;
- sikertelen modellhívás nem ment félkész beszélgetési fordulót;
- a válasz mindig visszaadja a session ID-t és a tényleges modell nevét;
- a sessiontárolás külön `SessionStore` port mögött helyezkedik el;
- az első adapter folyamatmemóriát használ, ezért újraindításkor ürül;
- az alkalmazási `ChatService` koordinálja a sessiont, kontextust és
  LLM-portot; a FastAPI route nem hív közvetlenül adaptert.

A tokenenkénti streaming külön, későbbi végpontot kap ugyanazon
alkalmazási service fölött. A pontos streaming protokollról külön döntés
készül, így a nem streamelt JSON-szerződés stabil marad.

## Alternatívák

- OpenAI-kompatibilis API elsődleges szerződésként: megkönnyítené néhány
  külső kliens bekötését, de külső formátumhoz kötné a Kelvin belső
  session- és hibamodelljét. Később külön kompatibilitási adapterként
  hozzáadható.
- Teljes beszélgetési előzmény minden kérésben: állapotmentesebb szervert
  adna, de a kliensekre terhelné a kontextuskezelést, és nem teljesítené a
  szerveroldali session célját.
- Adatbázisos sessiontár az első verzióban: újraindításálló lenne, de a
  v0.3 első lépéséhez indokolatlan tárolási és migrációs összetettséget
  hozna.
- Streaming kapcsoló ugyanazon végponton: kevesebb útvonalat jelentene, de
  két külön válaszformátumot adna egyetlen szerződéshez.

## Következmények

- A sessionök az első változatban elvesznek backend-újraindításkor.
- A port miatt később fájl-, SQLite- vagy hosszú távú memóriatárra
  cserélhető az adapter.
- A route, alkalmazási logika és tároló külön unit tesztelhető.
- A session ID nem hitelesítés; többfelhasználós használat előtt külön
  hozzáférés-kezelés szükséges.
- Az OpenAI-kompatibilitás és a streaming külön adapterrel vagy végponttal
  bővíthető a belső chatlogika módosítása nélkül.
