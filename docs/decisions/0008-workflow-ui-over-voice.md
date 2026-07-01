# ADR-0008: Workflow UI előnyben a Voice mérföldkővel szemben

Állapot: Superseded by ADR-0013

## Kontextus

Az eredeti roadmapben a v0.7 mérföldkő a hangvezérlés volt Whisper és Piper
komponensekkel. A projekt gyakorlati iránya közben erősebben az offline AI,
RAG, agentek, PowerShell/Git eszközhasználat és automatizálás felé mozdult.

A fejlesztői gépen jelenleg nincs mikrofon, és a hangvezérlés nem elsődleges
felhasználási igény. Ezzel szemben egy n8n-szerű vizuális workflow felület
közvetlenül támogatná Kelvin hosszabb távú célját: helyi, moduláris,
automatizálható AI platformként működni.

## Döntés

A Voice mérföldkő kikerül az 1.0 előtti fő roadmapből.

Helyette két mérföldkő kerül be:

- `v0.7 Workflow UI`: n8n-szerű vizuális folyamatépítő első, Kelvin-specifikus
  verziója;
- `v0.8 Automation Runtime`: workflow futtatás, naplózás, hibakezelés és
  jóváhagyási pontok.

A Voice opcionális, post-1.0 irányként marad dokumentálva.

## Indoklás

Workflow UI előnyei:

- jobban illeszkedik az agent és tool-calling irányhoz;
- kézzelfoghatóbb értéket ad mikrofon nélkül is;
- támogatja a későbbi PowerShellben élő Kelvin elképzelést;
- vizuálisan érthetővé teszi az automatizációkat;
- építhet a már elkészült RAG, API és későbbi memória komponensekre.

Voice hátrányai jelenleg:

- nincs mikrofon a fejlesztői környezetben;
- a projekt fő céljaihoz képest kisebb gyakorlati értéket ad;
- plusz audio pipeline-t, eszközkezelést és késleltetési finomhangolást igényel;
- elvinné a fókuszt az agent/workflow irányról.

## Következmények

Pozitív:

- az 1.0 célja fókuszáltabb lesz;
- Kelvin nemcsak chat-asszisztens, hanem vizuálisan vezérelhető offline
  automation platform felé fejlődik;
- a v0.6 Agent után természetes következő lépés lesz a v0.7 Workflow UI.

Negatív / kompromisszum:

- hangvezérlés 1.0 előtt nem lesz cél;
- Whisper és Piper integráció későbbi, opcionális fejlesztés marad.

## Elvetett alternatívák

### Voice megtartása v0.7-ként

Elvetve, mert jelenleg nincs hozzá hardveres igény, és kisebb értéket adna, mint
a workflow irány.

### Teljes n8n-klón építése 1.0-ig

Elvetve. A cél nem általános n8n-klón, hanem Kelvin-specifikus, offline,
korlátozott, biztonságos workflow réteg. A sok integráció, marketplace,
credential vault és ütemezett production workflow-k 1.0 utánra tartoznak.
