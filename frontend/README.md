# Frontend

A saját webes felület dokumentációja és egy későbbi, önálló frontend projekt
számára fenntartott könyvtár.

A v0.3 minimális, buildlépés nélküli HTML/CSS/JavaScript felületét a Python
csomag tartalmazza a `backend/src/kelvin_assistant/web/` könyvtárban. Így az
API-val együtt települ, és FastAPI szolgálja ki a `/ui`, illetve `/static/*`
útvonalakon.

Ha később külön React vagy Vue alkalmazásra váltunk, annak forrása ide
kerülhet, miközben a verziózott backend API változatlan marad.
