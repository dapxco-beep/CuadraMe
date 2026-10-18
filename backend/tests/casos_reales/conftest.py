"""Base de datos desechable para el corpus: se fija ANTES de que cualquier prueba importe la app.

Sin esto, el primer import de `app` (p. ej. `app.gmail_extract`) crearía el motor sobre el archivo por
defecto (`./cuadrame.db`), que persiste entre corridas y vuelve falsas las pruebas con usuarios fijos.
Si otra prueba ya fijó DATABASE_URL, se respeta (setdefault)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'casos_reales.db')}")
