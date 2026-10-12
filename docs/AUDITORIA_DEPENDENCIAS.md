# Auditoría de dependencias

Corrida local el 2026-10-12 (y semanal/por commit en CI, job `auditoria`, informativo por ahora).

## Backend (`pip-audit -r backend/requirements.txt`)
Sin vulnerabilidades conocidas. Nada pendiente.

## PWA (`npm audit`)
Producción (`npm audit --omit=dev`): **0 vulnerabilidades**. Todo lo que sigue es herramienta de desarrollo
y no llega al bundle que usan los usuarios.

| Paquete | Severidad | Corrección | Afecta a la app | Estado |
|---|---|---|---|---|
| sharp < 0.35.5 (librsvg, GHSA-wq5f-xc86-pv6w) | alta | 0.35.5 | No: solo genera íconos (`npm run icons`) | **Corregido** (parche, lockfile) |
| source-map-js 1.0.0 - 1.2.1 (DoS, GHSA-68fv-2mgg-jv7q) | alta | 1.2.2 | No: dependencia de build/pruebas | **Corregido** (parche, lockfile) |
| uuid < 11.1.1 (GHSA-w5hq-g745-h8pq), vía xcode y @capacitor/cli 8.5.0 a 9.0.0-alpha | moderada x3 | `npm audit fix --force` instala @capacitor/cli 8.4.3 (cambio mayor/retroceso) | No: solo el CLI de Capacitor al empaquetar iOS; el bug requiere pasar un `buf` a uuid v3/v5/v6 | **Pendiente**: esperar versión de @capacitor/cli que actualice xcode/uuid; no forzar |

Tras los parches: `npx vitest run` y `npm run build` en verde.
