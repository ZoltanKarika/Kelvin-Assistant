# ADR-0011: PostgreSQL-alapú agent audit és futásállapot

- Állapot: Accepted
- Dátum: 2026-07-01

## Kontextus

A v0.6 első agent store-ja folyamatmemóriában tárolja a futásokat, az aktív
eszközjavaslatot és a legutóbbi eredményt. Ez unit tesztekhez megfelelő, de az
API újraindításakor minden adat eltűnik. Kelvin már képes jóváhagyás után
Windows-fájlt módosítani, ezért egy ilyen műveletnek utólag is
visszakövethetőnek kell lennie.

## Döntés

Az agent aktuális állapotát és végrehajtási auditadatait PostgreSQL 16-ban
tároljuk, három kapcsolódó táblában:

- `agent_runs`: a verziózott futás aktuális állapota;
- `agent_tool_proposals`: a pontos eszközargumentumok, policy-döntés és
  jóváhagyás;
- `agent_tool_results`: a végrehajtás kimenete, hibája és időtartama.

Az agent run frissítése optimista verzióellenőrzést használ. Egy runhoz
egyszerre legfeljebb egy le nem zárt proposal tartozhat. A proposal és result
sorokat a végrehajtás lezárása után is megtartjuk.

## Miért nem JSON naplófájl?

Egy helyi JSON vagy JSONL fájl egyszerűbb lenne, de:

- párhuzamos kéréseknél külön zárolást igényelne;
- nehezebb lenne konzisztensen összekapcsolni a futást, jóváhagyást és
  eredményt;
- kereséshez és későbbi n8n-integrációhoz új indexelő réteg kellene;
- a projekt már használ helyi PostgreSQL-t.

## Következmények

Előnyök:

- API-újraindítás után is megmaradó agentállapot;
- egy jóváhagyott írás pontos argumentumai visszakereshetők;
- adatbázis-szintű constraint-ek védenek a hibás státuszoktól;
- a későbbi n8n-integráció korrelálható futástörténetet kaphat.

Hátrányok:

- az agent API működéséhez production környezetben szükséges lesz PostgreSQL;
- a tranzakciókat és verzióütközéseket az adapterben gondosan kell kezelni;
- a séma módosításaihoz később formális migrációkezelő, például Alembic válhat
  indokolttá.

## Biztonsági határ

Az adatbázis auditadatot tárol, de nem jogosít eszközvégrehajtásra. A
determinista policy és az explicit kliensoldali jóváhagyás továbbra is
kötelező. Titkok, környezeti változók és teljes Windows elérési utak nem
kerülhetnek az auditmezőkbe.
