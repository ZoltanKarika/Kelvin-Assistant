# ADR-0001: Portok és adapterek

- Állapot: Accepted
- Dátum: 2026-06-28

## Kontextus

A rendszernek több nyelvi modellt, vektortárat, dokumentumformátumot és
később több felületet kell támogatnia. A közvetlen technológiai függőségek
megnehezítenék a cserét és a külső szolgáltatás nélküli tesztelést.

## Döntés

A domain- és alkalmazási logika portokon keresztül használja a külső
képességeket. Az Ollama, a vektortár és a dokumentumbetöltők adapterként
valósítják meg ezeket a portokat. A konkrét implementációk bekötése dependency
injection segítségével történik.

## Alternatívák

- Közvetlen FastAPI–Ollama–vektortár integráció: kevesebb kezdeti fájl, de
  szoros függőség és nehezebb tesztelés.
- Mikroszolgáltatások minden komponenshez: erős izoláció, de indokolatlan
  üzemeltetési összetettség az első verzióban.

## Következmények

- Több explicit interfész és modul szükséges.
- A külső szolgáltatások tesztduplákkal helyettesíthetők.
- Új modell- vagy tárolóimplementáció kisebb változtatással hozzáadható.
- A moduláris monolit később szükség esetén szolgáltatásokra bontható.
