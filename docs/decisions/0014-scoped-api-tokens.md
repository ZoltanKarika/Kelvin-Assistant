# ADR-0014: Scope-alapú Kelvin API-tokenek

Állapot: Accepted

## Kontextus

Kelvin v0.6 agent policy-je már megkülönbözteti a read, write, destructive és
privileged eszközöket. Ez azonban csak egy jóváhagyott agent tool hívására
vonatkozik; a FastAPI végpontok jelenleg nem azonosítják a hívót, és nem
korlátozzák annak képességeit.

A v0.7-ben egy külön automation VM-en futó n8n kapcsolódik Kelvinhez. Az n8n
online forrásokat és külső AI-szolgáltatásokat is használhat, ezért nem kaphat
korlátlan hozzáférést Kelvin memória-, agent- és jóváhagyási végpontjaihoz.

Az API-védelem nem alapulhat kizárólag HTTP-metóduson. A chat és a
tudáskeresés POST kérés lehet anélkül, hogy tartós helyi állapotot módosítana,
míg egy DELETE vagy agent approval lényegesen magasabb jogosultságot igényel.

## Döntés

Kelvin nagy entrópiájú, átlátszatlan Bearer tokeneket és explicit scope-alapú
engedélyezést használ.

Egy védett kérés formája:

```http
Authorization: Bearer <opaque-token>
```

A raw token:

- legalább 32 véletlen bájtból készül;
- csak a kliens biztonságos credential tárában létezik;
- nem kerül Kelvin konfigurációjába, adatbázisába, naplójába vagy Gitbe;
- nem kerül URL query paraméterbe vagy request body-ba.

Kelvin csak a teljes token SHA-256 hashét és a hozzá tartozó principal
metaadatait tárolja. Nagy entrópiájú tokennél a hash só nélküli tárolása
elfogadható, mert nem ember által választott, szótárazható jelszóról van szó.
A számított és tárolt digest összehasonlítása timing-safe művelettel történik.

## Tokenkonfiguráció

A tokenhash-ek egy verziózott sémájú, repositoryn kívüli JSON-fájlban élnek,
például:

```json
{
  "version": 1,
  "tokens": [
    {
      "id": "n8n-research",
      "token_sha256": "<64 lowercase hex characters>",
      "scopes": [
        "system:read",
        "chat:use",
        "knowledge:read"
      ]
    }
  ]
}
```

Production elérési út:

```text
/etc/kelvin-assistant/api-tokens.json
```

A fájl:

- tulajdonosa `root`;
- csoportja a Kelvin szolgáltatáscsoport;
- jogosultsága `0640`;
- csak hash-eket, azonosítókat és scope-okat tartalmaz;
- hibás vagy hiányzó production konfiguráció esetén meghiúsítja az alkalmazás
  indulását.

A tokenfájl elérési útja Pydantic Settings konfigurációból érkezik. Rotációkor
az új és a régi hash rövid ideig együtt lehet aktív, majd a régi bejegyzés
eltávolítható. A változás kontrollált szolgáltatás-újraindítással lép életbe.

## Scope-ok

Az első scope-k:

| Scope | Képesség |
| --- | --- |
| `system:read` | readiness, verzió és nem érzékeny rendszerállapot |
| `chat:use` | chat és streaming chat használata |
| `knowledge:read` | RAG- és tudáskeresés |
| `memory:read` | aktív hosszú távú memória listázása |
| `memory:write` | memória létrehozása és törlése |
| `agent:execute` | agentfutás létrehozása, folytatása és megszakítása |
| `agent:write` | állapotváltoztató tool-javaslat beküldése |
| `agent:approve` | állapotváltoztató tool-javaslat jóváhagyása |

A scope-ok nem öröklődnek egymásból. Az `agent:approve` önmagában nem ad
`agent:write` vagy `agent:execute` jogosultságot.

Az első n8n kutató credential csak ezt kapja:

```text
system:read chat:use knowledge:read
```

Nem kap memóriaírási, agentírási vagy jóváhagyási jogot.

## Végpontvédelem

Nyilvánosan, token nélkül elérhető marad:

- `/`;
- `/health`;
- `/version`;
- a statikus frontend fájljai.

Minden más readiness és `/api/v1` végpont explicit scope-ot igényel.

A frontend chat nem kap beégetett tokent. A későbbi frontend-integráció a
felhasználótól munkamenetenként kér read tokent, azt csak memóriában tartja,
és nem menti local storage-ba. A Windows `kelvin` kliens és az n8n külön
principalhoz tartozó tokent használ.

## Hibaválaszok

- hiányzó vagy hibás token: `401 Unauthorized`;
- érvényes token, de hiányzó scope: `403 Forbidden`;
- a `401` válasz `WWW-Authenticate: Bearer` headert tartalmaz;
- a válasz nem árulja el, hogy mely tokenazonosító vagy scope-konfiguráció
  létezik.

## Transportbiztonság

A Bearer token birtoklása önmagában hozzáférést ad, ezért plaintext hálózaton
nem továbbítható.

Elfogadott transport:

- loopback kapcsolat;
- hitelesített SSH tunnel;
- ellenőrzött TLS-kapcsolat.

Az automation VM és Kelvin közötti valódi, scope-olt tokenkapcsolat csak TLS
vagy hitelesített tunnel kialakítása után kapcsolható be. A jelenlegi
hitelesítés nélküli HTTP `/health` kapcsolat kizárólag elérhetőségi próba.

## Naplózás és audit

Naplózható:

- principal azonosító;
- szükséges scope;
- végpont és metódus;
- engedélyezett vagy elutasított döntés;
- korrelációs azonosító;
- forrás IP-cím.

Nem naplózható:

- raw Bearer token;
- Authorization header;
- teljes tokenhash;
- credentialt tartalmazó request vagy response body.

## Fejlesztési és tesztkörnyezet

Az auth kikapcsolása csak explicit development vagy test konfigurációban
engedélyezett. Production környezet nem indulhat el auth nélkül.

Kötelező tesztek:

- hiányzó token elutasítása;
- hibás token elutasítása;
- megfelelő token és scope elfogadása;
- hiányzó scope elutasítása;
- tokenhash timing-safe ellenőrzése;
- hibás tokenfájl fail-closed kezelése;
- raw token hiánya naplóból és hibaválaszból;
- route-szintű scope-hozzárendelések ellenőrzése.

## Következmények

Pozitív:

- az n8n legkisebb szükséges jogosultságot kapja;
- egy read-only token elvesztése nem ad írási vagy approval jogot;
- a token visszavonható és rotálható;
- a meglévő tool policy mellett külön API-biztonsági réteg jön létre;
- az audit principalhoz tudja kötni a hívásokat.

Negatív:

- a frontend és a Windows kliens auth-támogatást igényel;
- production telepítéshez token- és transportkonfiguráció szükséges;
- a tokenrotáció és tokenfájl mentése új üzemeltetési feladat;
- a statikus token nem helyettesít központi identitásszolgáltatót több
  felhasználós környezetben.

## Elvetett vagy halasztott alternatívák

### Egyetlen közös API-token

Elvetve, mert elvesztése minden API-képességet egyszerre nyitna meg, és nem
adna legkisebb jogosultságot.

### Csak UFW és LAN-védelem

Elvetve, mert a hálózati elérés nem azonosítja a hívót, és egy kompromittált
LAN-eszköz korlátlan API-hozzáférést kapna.

### Nyers token tárolása Kelvin `.env` fájljában

Elvetve. Kelvinnek csak ellenőriznie kell a tokent, visszaolvasnia nem, ezért
elegendő a hash tárolása.

### JWT vagy teljes OAuth 2.0 authorization server

V0.7-re elvetve a kulcskezelési, aláírási, lejárati és issuer-komplexitás miatt.
Többfelhasználós vagy külső deployment esetén újraértékelhető.

### Kölcsönös TLS mint egyetlen hitelesítési réteg

V0.7-re halasztva. Erős gépazonosítást adna, de önmagában nem helyettesíti a
route-szintű scope-okat, és jelentősen növeli a tanúsítványüzemeltetést.

## Hivatkozások

- [RFC 6750: Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)
- [Python `hmac.compare_digest`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)
