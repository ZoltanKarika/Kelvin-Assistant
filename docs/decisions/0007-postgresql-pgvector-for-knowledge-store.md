# ADR-0007: PostgreSQL + pgvector a tudástárhoz

- Állapot: Accepted
- Dátum: 2026-06-29

## Kontextus

A v0.4 Knowledge mérföldkőben a rendszer dokumentumokat fog feldolgozni,
darabolni, embedding vektorokká alakítani, majd releváns részleteket keresni a
felhasználói kérdésekhez. Az eredeti terv ChromaDB-t említett vektortárként.

A projekt tanulási célú, hosszú távon karbantartható offline platformként
épül. Fontos, hogy az adatok szerkezete átlátható legyen, a mentés és
visszaállítás ismert eszközökkel történjen, és később a dokumentumok,
memóriaadatok, sessionök és auditnaplók ne több különálló tárolóban éljenek.

## Döntés

A v0.4 Knowledge mérföldkő elsődleges perzisztens tárolója PostgreSQL lesz, a
vektoros hasonlóságkereséshez pedig a pgvector bővítményt használjuk.

A backend továbbra sem függhet közvetlenül PostgreSQL-specifikus részletektől az
alkalmazási logikában. A RAG réteg portokon keresztül éri majd el:

- a dokumentumtárat;
- a chunk- és metaadattárat;
- az embeddingtárat;
- a vektoros keresést.

A PostgreSQL + pgvector ezek adaptere lesz.

## Miért

- Egy adatbázisban tarthatók a dokumentumok, chunkok, embeddingek, források,
  későbbi memóriák és auditadatok.
- A relációs táblák jobban tanulhatók és átláthatók, mint egy külön
  AI-specifikus vektortár belső struktúrája.
- A PostgreSQL mentése, visszaállítása, jogosultságkezelése és üzemeltetése
  standard DevOps tudás.
- A pgvector elegendő a kezdeti offline RAG igényekhez.
- Később is cserélhető marad a vektortár-adapter, ha a projekt kinövi ezt a
  megoldást.

## Alternatívák

- ChromaDB: gyorsabb RAG prototípus, kevesebb kezdeti adatbázis-tervezés, de
  külön tárolót és külön üzemeltetési modellt vezetne be.
- SQLite + vektoros kiegészítő: egyszerű lokális futtatás, de hosszabb távon
  gyengébb párhuzamossági és üzemeltetési alap.
- Külön dedikált vektordb: nagyobb skálázási lehetőség, de a jelenlegi offline
  tanulási célhoz túl nagy üzemeltetési összetettség.

## Következmények

- A v0.4-ben előbb adatmodellre és migrációs stratégiára lesz szükség.
- Telepíteni és dokumentálni kell a PostgreSQL-t és a pgvector bővítményt az
  Ubuntu VM-en.
- A RAG indulása lassabb lehet, mint ChromaDB-vel, de a rendszer hosszú távon
  átláthatóbb lesz.
- Az architektúra port/adapters szerkezete megmarad, ezért később más vektortár
  is bevezethető.
