# Auditoría visual (tamaños, desbordes, cosas montadas)

Sirve para revisar TODAS las pantallas en celular, tableta y computador con datos realistas, sin tocar producción ni cuentas
reales. Úsala después de cualquier cambio de diseño. Lo que el revisor automático NO ve (texto recortado, cosas que se montan)
se revisa mirando las capturas.

## 1. Levantar la API local con los datos de la demo
```
cd backend
PYTHONPATH=. venv/Scripts/python.exe tools/auditoria_visual/servidor_auditoria.py     # escucha en http://127.0.0.1:8000
```
Base SQLite temporal, usuario fijo, consentimiento aceptado. (Otro zip: `DEMO_ZIP=ruta.zip`.)

## 2. Levantar la PWA apuntando a esa API
```
cd pwa
npm i --no-save playwright-core        # una sola vez (no queda en package.json)
VITE_SUPABASE_URL=https://x.supabase.co VITE_SUPABASE_ANON_KEY=falsa npm run dev -- --port 5199
```

## 3. Recorrer las pantallas
```
cd pwa
SUPABASE_REF=x PW_REAL=1 PW_ESPERA=3000 \
PW_CHROMIUM="C:/Program Files/Google/Chrome/Application/chrome.exe" \
PW_ANCHOS="360x740,390x844,768x1024,1536x864" \
PW_PANTALLAS="Inicio:/,Cuentas:/cuentas,Movimientos:/movimientos,Tabla:/movimientos?vista=tabla,..." \
node scripts/verificar-ancho.mjs http://localhost:5199 carpeta-de-capturas
```
Variables de `scripts/verificar-ancho.mjs`:
- `PW_REAL=1` usa la API local de verdad (sin ella usa datos simulados mínimos, y muchas pantallas muestran «Algo salió mal»).
- `PW_ANCHOS` lista de `ancho x alto`; `PW_PANTALLAS` lista `Nombre:/ruta`; `PW_UA` cambia el user-agent (p. ej. Android).
- `PW_SCROLL=1500` baja la pantalla antes de la captura; `PW_ESPERA` milisegundos de espera; `PW_DIAG=1` lista lo que pasa del borde.
- Una línea `MAL` = hay scroll horizontal o algo fuera de pantalla (incluye el ancho real del `body`).

## 4. Mirar las capturas
Un desborde que un contenedor recorta no se detecta solo (así se escondió la columna «Monto» de la tabla). Arma hojas de contacto
con las capturas (4 por fila) y revísalas. En computador mira también con zoom del navegador de 110–125 % (equivale a 1536 px).

## Lo que ya se corrigió con esto (2026-10-26)
Tabla de Movimientos (columna Monto cortada: ahora es de ancho fijo y oculta Cuenta/Categoría si no caben), botones de periodo de
Informe, nombres en Categorías, Dividir gasto, tabla oculta de los gráficos que ensanchaba el `body` a 661 px, Inicio en dos
columnas en computador y tarjetas de Cuentas con el mismo ancho.
