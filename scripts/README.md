# Segédszkriptek

Ismételhető fejlesztési, ellenőrzési, telepítési és mentési feladatok helye.

Minden szkriptnek:

- biztonságos alapértékeket kell használnia;
- hibánál nem nulla kilépési kódot kell adnia;
- dokumentálnia kell a bemenetét és a mellékhatásait;
- lehetőség szerint többször is biztonságosan futtathatónak kell lennie.

## Ollama kapcsolat ellenőrzése

A `check_ollama.py` opcionális élő integrációs ellenőrzés. A `.env` fájlban
konfigurált Ollama runtime-ot és modellt hívja meg, ezért a unit tesztekkel
ellentétben futó Ollamát igényel:

```powershell
uv run python scripts/check_ollama.py
```

Siker esetén naplózza a rövid modellválaszt és nulla kilépési kódot ad.
Kapcsolati, HTTP- vagy válaszformátum-hibánál nem nulla kóddal áll le. A
szkript nem módosít adatot és nem tölt le modellt.
