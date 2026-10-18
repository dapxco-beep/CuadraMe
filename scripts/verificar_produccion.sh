#!/usr/bin/env bash
# Revisa que produccion este sana. SOLO LECTURA, sin secretos.
#   scripts/verificar_produccion.sh [commit_esperado] [ventana_logs=1h]
# Sale 0 si todo bien, 1 si algo fallo (explica en espanol que).
set -u
ESPERADO="${1:-}"
VENTANA="${2:-1h}"
BACKEND="https://backend-production-aeab.up.railway.app"
PWA="https://cuadrame.dapx.shop"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBLEMAS=()

# Extrae un campo de un JSON plano sin depender de jq.
campo() { printf '%s' "$1" | sed -n "s/.*\"$2\" *: *\"\{0,1\}\([^\",}]*\)\"\{0,1\}.*/\1/p" | head -1; }

VER="$(curl -s -m 25 -H 'Cache-Control: no-cache' "$BACKEND/version" || true)"
if [ -n "$VER" ]; then
  B="$(campo "$VER" commit)"
  echo "Backend /version : commit $B  version $(campo "$VER" version)  arranque $(campo "$VER" arranque_en)"
else
  echo "Backend /version : NO RESPONDE"; PROBLEMAS+=("El backend no responde en $BACKEND/version (caido, reiniciando o sin red).")
fi
SALUD="$(curl -s -m 25 "$BACKEND/health" || true)"
if printf '%s' "$SALUD" | grep -q '"ok" *: *true'; then echo "Backend /health  : ok"
else echo "Backend /health  : FALLA"; PROBLEMAS+=("El backend no contesta {\"ok\": true} en /health."); fi

VW="$(curl -s -m 25 -H 'Cache-Control: no-cache' "$PWA/version.json" || true)"
if [ -n "$VW" ]; then
  P="$(campo "$VW" commit)"
  echo "PWA version.json : commit $P  version $(campo "$VW" version)  build $(campo "$VW" build)"
else
  echo "PWA version.json : NO RESPONDE"; PROBLEMAS+=("La PWA no entrega $PWA/version.json (despliegue de Vercel bloqueado o caido).")
fi

if [ -n "$VER" ] && [ -n "$VW" ]; then
  if [ -z "$B" ] || [ "$B" = dev ]; then PROBLEMAS+=("El backend no informa su commit (falta GIT_COMMIT_SHA en Railway).")
  elif [ -z "$P" ] || [ "$P" = dev ]; then PROBLEMAS+=("La PWA no informa su commit (falta --build-env COMMIT_SHA en Vercel).")
  elif [ "${B#"$P"}" = "$B" ] && [ "${P#"$B"}" = "$P" ]; then PROBLEMAS+=("Backend ($B) y PWA ($P) estan en commits distintos: un despliegue quedo a medias.")
  else echo "Coinciden        : backend y PWA en $B"; fi
  if [ -n "$ESPERADO" ]; then
    E="${ESPERADO:0:7}"
    case "$B" in "$E"*) ;; *) PROBLEMAS+=("El backend corre $B y se esperaba $E (el despliegue del backend no termino o fallo).");; esac
    case "$P" in "$E"*) ;; *) PROBLEMAS+=("La PWA corre $P y se esperaba $E (Vercel no termino, o quedo Blocked por el autor del commit).");; esac
  fi
fi

# Logs de Railway (lectura). Prueba backend/ de este repo y la del repo principal si es un worktree.
if ! command -v railway >/dev/null 2>&1; then
  echo "Logs Railway     : OMITIDO (no esta instalado el CLI 'railway')"
else
  COMUN="$(git -C "$RAIZ" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
  DIR=""
  for c in "$RAIZ/backend" "$( [ -n "$COMUN" ] && dirname "$COMUN" )/backend"; do
    if [ -d "$c" ] && (cd "$c" && railway status >/dev/null 2>&1); then DIR="$c"; break; fi
  done
  if [ -z "$DIR" ]; then
    echo "Logs Railway     : OMITIDO (el CLI no esta enlazado; ejecute 'railway link' en backend/)"
  else
    LOGS="$(cd "$DIR" && railway logs --service backend --since "$VENTANA" --lines 2000 2>/dev/null || true)"
    if [ -z "$LOGS" ]; then echo "Logs Railway     : OMITIDO (no pude leer los logs; revise 'railway login')"
    else
      N500="$(printf '%s\n' "$LOGS" | grep -Ec 'HTTP/[0-9.]+"[[:space:]]+500|Internal Server Error|status[=: ]+500\b' || true)"
      NCOL="$(printf '%s\n' "$LOGS" | grep -c 'UndefinedColumn' || true)"
      NTB="$(printf '%s\n' "$LOGS" | grep -c 'Traceback' || true)"
      echo "Logs (ultima $VENTANA) : $N500 respuestas 500, $NCOL UndefinedColumn, $NTB Traceback"
      [ "$NCOL" -gt 0 ] && PROBLEMAS+=("Hay $NCOL errores UndefinedColumn: falta una migracion en la base (ver docs/OPERACION.md).")
      [ "$N500" -gt 0 ] && PROBLEMAS+=("Hay $N500 respuestas 500 en la ultima $VENTANA (en la app se ven como 'Sin conexion').")
      [ "$NTB" -gt 0 ] && [ "$N500" -eq 0 ] && [ "$NCOL" -eq 0 ] && PROBLEMAS+=("Hay $NTB Traceback en los logs de la ultima $VENTANA.")
    fi
  fi
fi

echo
if [ ${#PROBLEMAS[@]} -gt 0 ]; then
  echo "=== PRODUCCION: HAY PROBLEMAS ==="
  for p in "${PROBLEMAS[@]}"; do echo "- $p"; done
  exit 1
fi
echo "=== PRODUCCION: todo bien ==="
