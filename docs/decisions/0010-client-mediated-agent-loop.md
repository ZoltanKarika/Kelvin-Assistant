# ADR-0010: Kliens által közvetített strukturált agentciklus

- Állapot: Accepted
- Dátum: 2026-06-30

## Kontextus

Kelvin a v0.5 végére helyi LLM-et, beszélgetést, RAG tudástárat és hosszú
távú memóriát használ. A v0.6 célja, hogy a rendszer eszközöket is tudjon
használni, különösen a Windows host PowerShell-, fájl- és Git-környezetében.

A FastAPI backend az Ubuntu VM-en fut, miközben a kezelendő projektek és a
PowerShell a Windows hoston találhatók. A modell által generált nyers
parancsok közvetlen végrehajtása túl nagy biztonsági kockázatot jelentene.

## Döntés

Kliens által közvetített, strukturált agentciklust használunk.

- A backend értelmezi a célt, kezeli az agent állapotát és strukturált
  eszközkérést készít.
- A modell csak regisztrált eszköz nevét és típusos argumentumait
  javasolhatja.
- A determinisztikus policy engine kockázati döntést hoz.
- A Windows `kelvin` kliens megjeleníti a tervet és szükség esetén
  jóváhagyást kér.
- A kliens második ellenőrzés után helyben hajtja végre a műveletet.
- A végrehajtás eredménye strukturált megfigyelésként kerül vissza a
  backendhez.
- A Windows hoston nem nyitunk új bejövő távoli shell portot.

Az agent csak indokolt esetben kérdez vissza. A cél pontosítása külön
állapot, és nem helyettesíti az állapotváltoztató művelet jóváhagyását.

## Indoklás

### Miért strukturált eszközök?

- séma alapján ellenőrizhetők;
- külön tesztelhetők;
- kockázati szint rendelhető hozzájuk;
- nem igényelnek tetszőleges shellszöveg végrehajtását;
- később a workflow UI is ugyanazokat az eszközöket használhatja.

### Miért a Windows kliens hajt végre?

- a fájlok és a PowerShell eleve a Windows hoston vannak;
- a felhasználó helyben láthatja és engedélyezheti a műveletet;
- nincs szükség széles VM → host adminisztrációs hozzáférésre;
- a workspace-határ a végrehajtás helyén is ellenőrizhető.

### Miért két ellenőrzési pont?

A backend policy segít helyes tervet készíteni, de nem tekinthető kizárólagos
biztonsági határnak. A tényleges művelet előtt a Windows kliensnek is
ellenőriznie kell az eszközt, az argumentumokat, a workspace-t és a
jóváhagyást.

## Alternatívák

### Nyers PowerShell-parancs közvetlen végrehajtása

Elvetve az első implementációban. Nehezen validálható, könnyen tartalmazhat
parancsbefecskendezést, és túl széles jogosultságot adna a modellnek.

### Bejövő PowerShell-szolgáltatás a Windows hoston

Elvetve. Új hálózati támadási felületet, hitelesítést és tűzfalszabályokat
igényelne.

### Minden lépés automatikus végrehajtása

Elvetve. Állapotváltoztató és destruktív műveleteknél a felhasználói kontroll
fontosabb a sebességnél.

### Minden prompt kötelező pontosítása

Elvetve. Feleslegesen lassítaná az egyértelmű és csak olvasási feladatokat.
Célzott visszakérdezés szükséges, amikor a hiányzó információ érdemben
befolyásolja az eredményt vagy a kockázatot.

### A teljes agent futtatása kizárólag Windows alatt

Egy későbbi változatban lehetséges, de most megkettőzné a már működő
backend-, memória- és RAG-infrastruktúrát. A kliens–backend szétválasztás
jobban illeszkedik a jelenlegi portok és adapterek architektúrához.

## Következmények

Pozitív:

- a modell és a végrehajtás között ellenőrizhető biztonsági határ marad;
- az eszközök unit tesztelhetők valódi shell nélkül;
- nincs új bejövő végrehajtási port a Windows hoston;
- a későbbi workflow UI újrahasználhatja az eszközregisztert;
- a felhasználó megtartja az irányítást az állapotváltoztatások felett.

Negatív és kompromisszum:

- külön Windows kliens és kommunikációs szerződés szükséges;
- egy feladat több oda-vissza API-lépést igényelhet;
- a jóváhagyások lassítják az állapotváltoztató folyamatokat;
- a backend és a kliens policy szabályait konzisztensen kell tartani.

## Első implementáció

1. Agent domain modellek.
2. Tool registry és policy portok.
3. Memóriabeli tesztadapterek.
4. AgentService és állapotátmenetek.
5. API-szerződés.
6. PowerShell kliens read-only eszközökkel.
7. Jóváhagyásköteles módosító eszköz és auditnapló.

## Elfogadási feltétel

Egy agent feladat képes legyen a Windows kliensen keresztül workspace-en
belüli olvasási műveletet végrehajtani, egy módosító művelet előtt
jóváhagyást kérni, valamint minden próbálkozást auditálni. Ismeretlen eszköz,
workspace-en kívüli útvonal vagy jóváhagyás nélküli módosítás ne futhasson le.
