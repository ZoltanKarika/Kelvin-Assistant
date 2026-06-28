# ADR-0002: Hostoldali PowerShell-végrehajtás

- Állapot: Accepted
- Dátum: 2026-06-28

## Kontextus

A felhasználó hosszú távon Codexhez hasonló, PowerShellben használható
asszisztenst szeretne. Az LLM és a fő backend Linux VM-ben fut, a kezelendő
fájlok és a PowerShell azonban a Windows hoston találhatók.

## Döntés

A Windows-oldali kliens interaktív felületként és korlátozott
eszközvégrehajtóként működik. A backend strukturált eszközkérést küld, de a
kliens ellenőrzi a munkakönyvtárat, a jogosultságot és a felhasználói
jóváhagyást a végrehajtás előtt.

## Alternatívák

- Csak chat a PowerShellben: biztonságosabb és egyszerűbb, de nem biztosít
  fejlesztői agentfunkciókat.
- WinRM vagy SSH alapú távoli PowerShell: központi végrehajtást ad, de
  szélesebb támadási felületet és összetettebb hitelesítést igényel.
- Korlátlan hosthozzáférés a VM-ből: kényelmes, de elfogadhatatlan
  biztonsági kockázat.

## Következmények

- Külön Windows-kliens és kommunikációs protokoll szükséges.
- A jogosultságokat a backendnek és a kliensnek is ellenőriznie kell.
- A végrehajtás a felhasználói környezetben marad.
- A műveletek naplózhatók, megszakíthatók és munkakönyvtárhoz köthetők.
