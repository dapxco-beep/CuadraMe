# Cómo verificar antes de desplegar

El CI (`.github/workflows/ci.yml`) corre solo en cada PR y en `main`, pero **no despliega**: el deploy
sigue siendo manual por CLI (Railway / Vercel). Antes de desplegar, confirma:

1. **CI en verde** en el commit que vas a desplegar (backend y PWA).
2. **Local, backend**: `cd backend && venv/Scripts/python.exe -m pytest tests -q` (unos 810 casos, ~50 s).
3. **Local, PWA**: `cd pwa && npm test && npm run build` (unos 450 casos, ~15-20 s; el build debe terminar sin errores).
   Para el build local hacen falta `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY` (en CI van ficticias).
4. **Cambios de base de datos**: nada de SQL a producción sin aprobación; revisa que las migraciones sean aditivas.
5. **Variables nuevas**: si el código lee una variable de entorno nueva, ya debe estar en Railway/Vercel antes del deploy.
6. Después del deploy: abre la app, entra, registra un movimiento y revisa que Sentry no reporte errores nuevos.

## Notas sobre las pruebas de la PWA
- Usan `pool: 'vmThreads'` (un jsdom por worker, aislamiento por archivo intacto): bajó de ~40 s a ~15 s y no falla bajo carga.
- Importa `userEvent` desde `src/test/userEvent.js` (sin pausas entre acciones), no desde la librería directa.
- Evita `setTimeout` fijos en las pruebas: usa `findBy*`/`waitFor` o temporizadores falsos.
