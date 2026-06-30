# ADR-0009: Típusos, törölhető memória modell

Állapot: Proposed

## Kontextus

A v0.4 Knowledge mérföldkő után Kelvin már tud dokumentumokból keresni és RAG
kontextust adni a chat válaszokhoz. A következő lépés a v0.5 Memory, amely már
nem külső dokumentumokból, hanem Kelvin működése közben keletkező információkból
dolgozik.

Ez érzékenyebb terület, mert a memória tartalmazhat személyes preferenciákat,
projektállapotot, visszatérő szokásokat vagy beszélgetésekből kiemelt tényeket.
Ezért a memória nem lehet kontroll nélküli “mindent megjegyző” mechanizmus.

## Döntés

A memória típusos és törölhető lesz.

Első memória-kategóriák:

- `session history`: beszélgetés technikai előzménye;
- `short-term memory`: ideiglenes, feladathoz vagy beszélgetéshez kötött emlék;
- `long-term memory`: tartós, jóváhagyott felhasználói vagy projektmemória;
- `knowledge`: dokumentumokból származó RAG tudás, amely nem azonos a memóriával.

A v0.5 elsődleges tárolója PostgreSQL lesz, opcionális pgvector embeddinggel.

## Indoklás

Miért nem elég a meglévő RAG?

- A RAG dokumentumokból dolgozik.
- A memória működés közben keletkező preferenciákat és állapotot kezel.
- A RAG újraépíthető dokumentumokból, a memória viszont felhasználói kontrollt
  és törlési lehetőséget igényel.

Miért legyen típusos?

- Más szabály kell egy preferenciára, egy projekt tényre és egy ideiglenes
  feladatállapotra.
- A későbbi promptépítés tisztább lesz.
- Könnyebb listázni, törölni és auditálni.

Miért legyen törölhető?

- A felhasználónak kontrollálnia kell, mit jegyez meg Kelvin.
- Hibás vagy elavult memória különben rontaná a válaszokat.
- Személyes adatoknál ez alapvető biztonsági és bizalmi követelmény.

## Következmények

Pozitív:

- Kelvin fokozatosan személyesebb és hasznosabb asszisztenssé válhat;
- a memória nem keveredik össze a dokumentumtárral;
- később az agent és workflow funkciók is használhatják ugyanazt a memóriaréteget.

Negatív / kompromisszum:

- több adatmodell és több szabály szükséges;
- a memóriaírást óvatosan kell bevezetni;
- az első verzió lassabban lesz “okos”, de biztonságosabb lesz.

## Első implementációs irány

1. `memory_items` SQL séma.
2. `memory_embeddings` SQL séma.
3. Python domain modellek és portok.
4. PostgreSQL memory repository.
5. CLI:
   - add;
   - list;
   - delete;
   - search.
6. Chat integráció opcionális memória-kontekstussal.

## Elvetett alternatívák

### Minden beszélgetést automatikusan hosszú távú memóriába menteni

Elvetve. Túl zajos, túl kockázatos, és gyorsan hibás vagy fölösleges emlékeket
eredményezne.

### A memóriát a knowledge táblákba keverni

Elvetve. A dokumentumtár és a memória más eredetű, más törlési szabályú és más
felhasználói elvárású adat.

### Csak prompt-szintű memória, adatbázis nélkül

Elvetve. Nem auditálható, nem listázható és újraindítás után elveszik.
