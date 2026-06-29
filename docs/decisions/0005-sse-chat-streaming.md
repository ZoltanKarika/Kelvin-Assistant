# ADR-0005: SSE-alapú chat streaming

- Állapot: Accepted
- Dátum: 2026-06-29

## Kontextus

A nem streamelt chat végpont csak a teljes modellválasz elkészülte után ad
eredményt. Hosszabb válasznál ez lassúnak érződik, és a kliens nem tudja
megszakítani a már érdektelenné vált generálást. A PowerShell-kliensnek és a
későbbi webes felületnek ugyanazt a helyi, verziózott streaming szerződést
kell használnia.

A sessionbe kizárólag teljes user–assistant forduló kerülhet. Egy
megszakított hálózati kapcsolat, modellhiba vagy párhuzamos módosítás nem
hagyhat félkész előzményt.

## Döntés

A külön streaming végpont:

```text
POST /api/v1/chat/stream
```

A kérés ugyanazt a JSON-sémát használja, mint a nem streamelt chat:

```json
{
  "message": "Írj röviden a borókáról.",
  "session_id": null
}
```

A válasz `text/event-stream; charset=utf-8` formátumú Server-Sent Events
folyam. Az események:

### `delta`

Egy új szövegrészlet:

```text
event: delta
data: {"content":"A boróka"}
```

A kliens az érkezési sorrendben fűzi össze a `content` értékeket.

### `done`

Csak akkor küldhető el, ha a modell befejezte a választ és a teljes forduló
sikeresen mentésre került:

```text
event: done
data: {"session_id":"<UUID>","model":"gemma4:e4b"}
```

Új beszélgetésnél a kliens csak ebből az eseményből kap session ID-t. Így
megszakított stream után nem marad nem létező vagy félkész sessionazonosító.

### `error`

A HTTP fejlécek elküldése után fellépő hiba SSE-eseményként érkezik:

```text
event: error
data: {"code":"llm_unavailable","message":"Ollama runtime is unavailable"}
```

Az elsőként támogatott stabil hibakódok:

- `llm_unavailable`;
- `llm_response_error`;
- `session_conflict`;
- `stream_interrupted`.

Kérésellenőrzési és session-előkészítési hiba még a stream megnyitása előtt
szokásos HTTP-választ ad:

- hibás kérés: HTTP 422;
- ismeretlen session: HTTP 404;
- ugyanazon session már futó kérése: HTTP 409.

Az alkalmazási réteg sessionönként legfeljebb egy aktív fordulót enged. A
modell streamjét a klienskapcsolat megszakadásakor le kell zárni. A részleges
válasz memóriában összegyűjthető, de csak a modell sikeres befejezése után
menthető a sessiontárba. A `done` esemény a sikeres mentés után következik.

## Alternatívák

- NDJSON: POST kéréssel és PowerShellből egyszerűen feldolgozható, de nem ad
  szabványos eseménytípusokat, és a webes klienshez több saját protokollkódot
  igényel.
- WebSocket: kétirányú kommunikációt biztosítana, de a jelenlegi egyirányú
  tokenfolyamhoz felesleges kapcsolat- és állapotkezelést hozna.
- Streaming kapcsoló a `/api/v1/chat` végponton: kevesebb útvonalat adna,
  viszont ugyanahhoz az endpointhez JSON és eseményfolyam válaszformátumot
  keverne.
- Session ID küldése a stream elején: korábban elérhetővé tenné az
  azonosítót, de megszakításkor olyan ID maradna a kliensnél, amelyhez nincs
  mentett forduló.

## Következmények

- A kliensnek SSE-eseményeket és stabil hibakódokat kell feldolgoznia.
- Stream megnyitása után a HTTP státuszkód már nem módosítható; a későbbi
  hibák `error` eseményként érkeznek.
- A backendnek kezelnie kell a kliens lecsatlakozásából eredő aszinkron
  megszakítást.
- A session írása csak a teljes stream befejezése után történik.
- A nem streamelt végpont és a streaming ugyanazt a domain- és
  sessionlogikát használja.
