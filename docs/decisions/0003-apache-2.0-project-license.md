# ADR-0003: Apache-2.0 projektlicenc

- Állapot: Accepted
- Dátum: 2026-06-28

## Kontextus

A Kelvin Assistant tanulási projektként indul, de később bővíthető, több
közreműködőt és akár kereskedelmi felhasználást is támogató offline
AI-platformmá válhat. Egyértelmű licenc nélkül az alapértelmezett szerzői jog
nem biztosít mások számára felhasználási, módosítási vagy terjesztési jogot.

## Döntés

A saját Kelvin Assistant forráskód és dokumentáció Apache License 2.0 alatt
kerül kiadásra. A választott SPDX-azonosító `Apache-2.0`.

A külső függőségek, modellek, adatok és önálló alkalmazások nem kerülnek a
projektlicenc alá; ezek saját feltételeit külön kell nyilvántartani.

## Alternatívák

- MIT: rövidebb és egyszerűbb megengedő licenc, de nem tartalmaz az
  Apache-2.0-hoz hasonló explicit szabadalmi engedélyt.
- Zárt projekt: nem igényel nyílt forráskódú licencet, de akadályozná a
  későbbi együttműködést és újrafelhasználást.
- Erős copyleft licenc: biztosíthatná a származékos művek forrásának
  megnyitását, de nem ez a projekt kívánt terjesztési modellje.

## Következmények

- A kiadásoknak tartalmazniuk kell a licencet és a releváns értesítéseket.
- A módosított és terjesztett változatoknak meg kell felelniük az
  Apache-2.0 feltételeinek.
- Az explicit szabadalmi engedély tisztább jogi keretet ad a
  közreműködésekhez.
- Minden külső komponens és modell kompatibilitását külön kell ellenőrizni.
