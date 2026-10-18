# Operación de CuadraMe (runbook)

Esta guía no depende de la memoria de nadie: todo lo que hay que hacer para verificar y desplegar está
en comandos, y todo lo que ya nos mordió está en la lista de trampas. Los scripts viven en `scripts/` y
funcionan igual desde la raíz de cualquier copia del repositorio (también desde un worktree).

## 1. Verificar antes de commit o de desplegar

| Qué | Comando (PowerShell, raíz del repo) | Tarda |
|-----|--------------------------------------|-------|
| Rápido: corpus de casos reales + guardianes | `powershell -File scripts\verificar_todo.ps1 -Rapido` | ~10 s |
| Completo: todo el backend + toda la PWA | `powershell -File scripts\verificar_todo.ps1` | 3-5 min |
| Producción sana (solo lectura) | `powershell -File scripts\verificar_produccion.ps1` | ~15 s |

En bash/Git Bash: `scripts/verificar_todo.sh [--rapido]` y `scripts/verificar_produccion.sh [commit_esperado]`.

- `verificar_todo` resume una línea por parte (BACKEND / PWA) y **sale con código distinto de 0 si algo falla**.
  Usa el venv de `backend\venv` (si trabajas en un worktree sin venv, usa el del repo principal; o define
  `CUADRAME_PYTHON` con la ruta de `python.exe`).
- `-Rapido` corre `backend/tests/casos_reales` (ver su `README.md`) y los guardianes: contabilidad
  (nadie suma gastos con el tipo guardado), migraciones congeladas y «500 con CORS».
- `verificar_produccion` pide `/version` y `/health` del backend, `version.json` de la PWA, comprueba que
  **ambos corran el mismo commit** y, con el CLI de Railway, cuenta 500 / `UndefinedColumn` / `Traceback`
  de la última hora. Explica en español qué falló. No usa secretos ni cambia nada.
  Si el CLI de Railway no está enlazado en tu máquina, omite los logs y lo dice (`railway link` en `backend\`).

## 2. Desplegar

```
powershell -File scripts\desplegar.ps1 -SoloVerificar        # ensayo: verifica todo y producción, NO despliega
powershell -File scripts\desplegar.ps1                         # despliegue real
```

El despliegue real (desde la rama `main`, con todo commiteado):

1. Pide escribir **`DESPLEGAR`** (si no, no hace nada).
2. Corre `verificar_todo` completo; si falla, se detiene.
3. Crea un **commit vacío con el autor del equipo** (`DAPX <dapxco@gmail.com>`): sin eso Vercel deja el
   despliegue en *Blocked*.
4. Backend: `railway variables --set GIT_COMMIT_SHA=<sha> --service backend` y `railway up --service backend --detach`.
5. PWA: `vercel deploy --prod --yes --build-env COMMIT_SHA=<sha>` (reintenta una vez ante «Not authorized»).
6. Espera hasta 6 min y termina con `verificar_produccion -Esperado <sha>`: ambos deben correr ese commit.

**No hace `git push`.** El despliegue es por CLI, no por git. Hacer push (o no) lo decide una persona aparte.
Variantes: `-PermitirRama` (desplegar desde otra rama a propósito), `-Confirmacion DESPLEGAR` (automatizar).
Antes de un despliegue que cambie la base de datos o variables nuevas, revisa `docs/verificar-antes-de-desplegar.md`.

## 3. Si algo sale mal

1. **Mira primero qué dice el verificador**: `scripts\verificar_produccion.ps1`.
2. **Logs del backend**: `cd backend` y `railway logs --service backend --since 1h --lines 500`
   (solo errores: `--filter "@level:error"`). Busca `500`, `UndefinedColumn`, `Traceback`.
3. **Rollback del backend**: en Railway, *Deployments* del servicio `backend` → el despliegue anterior bueno →
   «Redeploy»/«Rollback». Por CLI: `railway deployment list --service backend` para ver los despliegues y
   `railway redeploy --service backend` (re-lanza el último; para volver a uno anterior usa el panel). Después,
   fija otra vez `GIT_COMMIT_SHA` al commit al que volviste (para que `/version` diga la verdad).
4. **Rollback de la PWA**: `cd pwa` y `vercel rollback <url-o-id-del-despliegue-anterior>` (o *Promote* en el panel de Vercel).
5. **No hace falta tocar la base**: las migraciones son aditivas (solo agregan columnas/índices).
6. Backend y PWA en commits distintos = un despliegue quedó a medias: repite el paso que falló
   (`railway up` o `vercel deploy`) con el mismo commit.
7. Después de resolver: agrega el caso al corpus (`backend/tests/casos_reales/README.md`, «Cómo agregar un caso nuevo»).

## 4. Trampas conocidas (ya nos mordieron)

- **Vercel «Blocked»**: Vercel bloquea el despliegue si el autor del último commit no es del equipo. Por eso
  `desplegar` crea el commit vacío con `DAPX <dapxco@gmail.com>`. A mano:
  `git -c user.name=DAPX -c user.email=dapxco@gmail.com commit --allow-empty -m "Despliegue"` y desplegar con ese SHA.
  Un «Not authorized» puntual de Vercel se arregla reintentando.
- **Migraciones inmutables** (`backend/app/migraciones.py`): una migración que ya corrió en producción **no se edita
  ni se le agregan sentencias** (no se vuelve a ejecutar y la app da 500 por columnas faltantes: pasó con
  `datos_cuerpo`). Lo nuevo es siempre una migración `000N_...` **al final**. Las desplegadas están congeladas por
  `tests/casos_reales/test_caso_10_11_12_operacion.py` (y `test_columnas_de_arranque.py`): al desplegar una nueva,
  súmala al diccionario `DESPLEGADAS` de ese archivo.
- **500 sin CORS = «Sin conexión»**: en la PWA un error del servidor sin cabeceras CORS se ve como falta de
  internet. `errores_500.py` lo evita, pero ante un aviso de «sin conexión» **primero mira los logs** por
  500/`UndefinedColumn`, no la red del usuario.
- **Crons en cron-job.org** (los crea el dueño; están fuera del código y de Railway). Ver §5.
- **Worktrees**: un worktree no trae `venv` ni está enlazado a Railway/Vercel. Para pruebas, el script usa el venv del
  repo principal. Para desplegar, hazlo desde el worktree de `main` (el CLI de Railway/Vercel se enlaza por carpeta:
  `railway link` en `backend\`, `vercel link` en `pwa\`). Crea los worktrees a mano si la herramienta rechaza la
  ruta: `git worktree add ..\wt-x -b rama main` y una *junction* de `pwa\node_modules` hacia el repo principal.
  Antes de desplegar mira `git log`: otras sesiones también commitean en `main`.
- **Pruebas de rendimiento** pueden fallar por carga si corren dos suites a la vez: repite solas.

## 5. Crons de cron-job.org (los crea el dueño)

El backend no programa nada solo. Sin estos crons, los correos solo entran al abrir la app y no salen avisos.
Todos son `POST` a `https://backend-production-aeab.up.railway.app<ruta>` con la cabecera `X-Cron-Secret`
(el mismo valor que `CRON_SECRET` en Railway; **nunca va en el repo**), zona horaria `America/Bogota`.

Se crean con los scripts (muestran qué harían y solo crean con `--aplicar`; las llaves se pasan por variable de
entorno `CRONJOB_API_KEY` y `CRON_SECRET`, no se guardan):

```
cd backend
venv\Scripts\python.exe cronjobs\crear_crons.py            # simulacro
venv\Scripts\python.exe cronjobs\crear_crons.py --aplicar  # crea los jobs
venv\Scripts\python.exe cronjobs\crear_cron_correos.py --aplicar   # solo el de correos, sin duplicar
```

| Cron | Ruta | Horario (hora Colombia) |
|------|------|-------------------------|
| Leer correos de los bancos | `/correos/cron/sincronizar` | cada hora, 6:00 a 23:00 |
| Aportes automáticos | `/push/cron/aportes-automaticos` | diario 8:00 |
| Recordar recurrentes | `/push/cron/recordar-recurrentes` | diario 9:00 |
| Revisar presupuestos | `/push/cron/revisar-presupuestos` | diario 18:00 |
| Premiar presupuestos (fin de mes) | `/push/cron/premiar-presupuestos-mes` | diario 21:00 |
| Resumen semanal (push) | `/push/cron/resumen-semanal` | domingo 17:00 |
| Backup diario | `/backup/cron/enviar` | diario 2:00 |
| Uso semanal | `/metricas/cron/revisar-uso-semanal` | lunes 8:00 |
| Purgar retención de datos | `/correos/cron/purgar-retencion` | diario 3:30 |
| Resumen diario de avisos | `/avisos/cron/resumen-diario` | diario 20:00 |
| Avisar renta | `/impuestos/cron/avisar-renta` | diario 9:30 |
| Precios de inversiones (opcional) | `/inversiones/cron/actualizar-precios` | L-V, 8-16 h, :00 y :30 |
| Resumen semanal de inversiones (opcional) | `/inversiones/cron/resumen-semanal` | domingo 18:00 |

La fuente de verdad de esta tabla es la lista `JOBS` de `backend/cronjobs/crear_crons.py`: si cambias una,
cambia la otra. Para comprobar que un cron vive, mira que `verificar_produccion` no tenga 500 y que en
cron-job.org el último resultado sea 200.

## 6. Checklist antes de aceptar clientes nuevos

- [ ] `scripts\verificar_todo.ps1` completo en verde sobre el commit exacto que está en producción.
- [ ] `scripts\verificar_produccion.ps1` en verde: `/health` ok, backend y PWA en el mismo commit, 0 errores 500.
- [ ] Los crons de §5 existen en cron-job.org, con `X-Cron-Secret` correcto y último resultado 200 (sobre todo
      «leer correos», «backup diario» y «purgar retención»).
- [ ] Backup: llegó el correo del backup diario de las últimas 24 h y se probó restaurar una vez (`docs/RESTAURAR_RESPALDO.md`).
- [ ] Variables de Railway/Vercel completas (revisa `docs/SALIDA_A_PRODUCCION.md`); ninguna nueva sin definir.
- [ ] Sentry recibe eventos y no hay errores nuevos sin atender.
- [ ] Recorrido manual con una cuenta de prueba: registrar, traer correos, subir un extracto, ver informes.
- [ ] Textos legales y consentimientos de datos vigentes (`docs/legal/`); términos y privacidad enlazados en la app.
- [ ] Para cada falla nueva que haya aparecido: ya está en `backend/tests/casos_reales/` con su fila en el README.
- [ ] Hay una persona con acceso a Railway, Vercel, Supabase y cron-job.org que sepa hacer rollback (§3).
