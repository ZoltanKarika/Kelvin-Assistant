# Backend

A FastAPI alkalmazás és a technológiától független alkalmazási logika helye.

A Python-kód `src` elrendezést használ, hogy a tesztek ne tudják véletlenül
a repository gyökeréből importálni a még nem telepített csomagot.

Fő modulhatárok:

- `domain`: belső modellek és szabályok;
- `application`: használati esetek;
- `ports`: cserélhető függőségek interfészei;
- `adapters`: külső technológiák integrációi;
- `api`: HTTP-szerződések;
- `agent`: agentciklus;
- `tools`: eszközsémák;
- `sessions`: munkamenetek;
- `permissions`: engedélyezési szabályok;
- `config`: konfiguráció;
- `observability`: logging és későbbi metrikák.
