# ADR-0006: Minimális, framework nélküli chat frontend

- Állapot: Accepted
- Dátum: 2026-06-29

## Kontextus

A nem streamelt chat API már többfordulós beszélgetést kezel, de jelenleg
csak Swaggerből vagy kézi PowerShell-kérésekkel használható. A tanulási
projekthez szükség van egy korán kipróbálható felületre, amely láthatóvá
teszi a sessionkezelést, a hibákat és később a streaming működését.

A rendszernek offline kell futnia, és a v0.3-ban még nem cél egy külön
frontend build- és csomagkezelési lánc üzemeltetése.

## Döntés

Az első chatfelület framework nélküli HTML, CSS és JavaScript modulokból
áll. A FastAPI ugyanazon origin alatt szolgálja ki:

```text
GET /ui
GET /static/*
```

A kezdeti felület:

- megjeleníti a user és assistant üzeneteket;
- a `POST /api/v1/chat` végpontot használja;
- memóriában tartja az aktuális session ID-t;
- új beszélgetés gombot biztosít;
- kérés közben letiltja a küldést és várakozási állapotot jelez;
- érthetően megjeleníti a 404, 409, 422, 502 és 503 hibákat;
- az API health és readiness állapotát jelzi;
- mobilon és asztali böngészőben is használható;
- minden modellválaszt szövegként jelenít meg, nem értelmez nyers HTML-t.

A frontend kezdetben nem renderel Markdownt. Ez csökkenti az XSS-kockázatot
és elkerüli egy külön sanitizer függőség bevezetését. A streaming
megvalósítása után ugyanaz a felület az SSE végpontra áll át.

## Alternatívák

- React vagy Vue Vite builddel: jobb komponens-ökoszisztémát adna, de Node.js
  toolchaint, külön buildet és további függőségfrissítést igényelne.
- Open WebUI: gyorsan adna gazdag felületet, de a saját Kelvin chat- és
  session API tanulását, hibáit és későbbi agentengedélyeit elfedné.
- Külön frontend webszerver: tisztább deployment-határt adna, de CORS-t,
  új szolgáltatást és több üzemeltetést hozna egy egyfelhasználós helyi
  rendszerbe.
- Csak Swagger vagy PowerShell: nem igényelne frontendkódot, de nem adna
  valós chatélményt és a streaming kliensoldala sem lenne kipróbálható.

## Következmények

- A frontend ugyanazzal a FastAPI szolgáltatással települ és indul.
- Nincs külön Node.js függőség vagy buildlépés.
- A statikus fájlokhoz backend route- és böngészős ellenőrzés szükséges.
- A session továbbra is memóriabeli; backend-újraindítás után a kliensnek új
  beszélgetést kell kezdenie.
- Többfelhasználós vagy internet felé nyitott használat előtt hitelesítés,
  CSRF- és szigorúbb böngészőbiztonsági szabályok szükségesek.
- A felület később lecserélhető anélkül, hogy a chat alkalmazási service
  módosulna.
