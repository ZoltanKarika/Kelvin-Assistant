# ADR-0013: Self-hosted n8n az automatizációs réteghez

Állapot: Accepted

Felváltja: ADR-0008 saját Workflow UI-ra és Automation Runtime-ra vonatkozó
részét. A Voice post-1.0 prioritása változatlan.

## Kontextus

A korábbi roadmap egy Kelvin-specifikus, n8n-szerű workflow felületet és külön
automatizációs futtatómotort tervezett. Ezek megépítése jelentős fejlesztési és
üzemeltetési költséget okozna: vizuális szerkesztő, időzítés, retry, credential
kezelés, integrációk, futástörténet és hibakezelés is szükséges lenne.

Az n8n self-hosted Community Edition ezeket a képességeket kész, vizuális
automatizációs rétegként biztosítja. Kelvin fő értéke nem egy általános
workflow-motor újraimplementálása, hanem a helyi AI, RAG, memória, agent,
biztonsági policy és jóváhagyási folyamat.

## Döntés

Kelvin nem épít saját workflow UI-t vagy általános automatizációs futtatómotort
az 1.0 verzióig. A vizuális automatizációt self-hosted n8n Community Edition
biztosítja az Ubuntu VM-en.

A felelősségek:

- n8n: vizuális workflow-k, triggerek, időzítés, külső integrációk, retry és
  workflow-szintű futástörténet;
- Kelvin: LLM, RAG, memória, agenttervezés, eszközpolicy, jóváhagyás és
  agentaudit;
- Windows `kelvin` kliens: a hostoldali eszközök tényleges végrehajtása és a
  helyi felhasználói jóváhagyás.

Az elsődleges integráció verziózott HTTP API és n8n webhook. Kelvin csak
konfigurációban engedélyezett workflow-kat indíthat. Az n8n nem kaphat
korlátlan shell- vagy Windows-hozzáférést, és nem kerülheti meg Kelvin policy
engine-jét.

## Offline működés

Az n8n, Kelvin, PostgreSQL és Ollama helyi telepítéssel internet nélkül is
használható. Az olyan workflow-k, amelyek Slackhez, WhatsApphoz vagy más
felhős szolgáltatáshoz kapcsolódnak, csak internetkapcsolattal működnek.
Ezek kiesése nem akadályozhatja Kelvin helyi chat-, RAG- vagy agentfunkcióit.

## Titkok és adatok

- n8n credentialök nem kerülnek a repositoryba vagy LLM promptba;
- titkok az n8n credential store-ban vagy helyi környezeti konfigurációban
  maradnak;
- exportált workflow nem tartalmazhat titkot;
- az auditnapló csak korrelációs azonosítót és szükséges metaadatot tárol;
- állapotváltoztató Windows-művelethez továbbra is helyi jóváhagyás kell.

## Licencelési következmény

Az n8n különálló komponens, saját Sustainable Use License feltételekkel. Nem
kerül a Kelvin Apache-2.0 licence alá. A projekt a self-hosted Community
Editiont személyes és belső használatra tervezi.

Ha Kelvin később értékesített szolgáltatássá válik, ügyfeleknek n8n-hozzáférést
ad, vagy ügyfelek saját credentialjeit kezeli, az n8n aktuális licencfeltételeit
újra kell értékelni.

## Következmények

Pozitív:

- lényegesen kisebb saját fejlesztési feladat;
- kész vizuális szerkesztő és integrációs ökoszisztéma;
- Kelvin fejlesztése az AI- és agentbiztonságra fókuszálhat;
- az üzenetküldés nagy része n8n workflow-val megoldható.

Negatív:

- egy új szolgáltatást kell telepíteni, frissíteni és menteni;
- az n8n licence eltér a Kelvin Apache-2.0 licencétől;
- az offline működéshez a szükséges n8n csomagokat és node-okat előre kell
  beszerezni;
- felhős integrációk internet nélkül nem működnek.

## Elvetett alternatívák

### Saját Kelvin Workflow UI és runtime

Elvetve, mert sok, már n8n-ben megoldott infrastruktúrát kellene újraépíteni,
miközben kevés közvetlen AI-értéket adna.

### Csak egyedi Python automatizációs szkriptek

Elvetve mint elsődleges irány, mert nem ad vizuális szerkesztést, egységes
futástörténetet vagy könnyen bővíthető integrációkat.

### Felhős n8n

Nem elsődleges irány, mert nem felel meg a projekt helyi és offline működési
céljának.

## Hivatkozások

- [n8n Community Edition képességek](https://docs.n8n.io/hosting/community-edition-features/)
- [n8n Sustainable Use License](https://docs.n8n.io/sustainable-use-license/)
