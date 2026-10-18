#!/usr/bin/env bash
# Verifica CuadraMe: pruebas del backend y de la PWA. Sale con codigo != 0 si algo falla.
#   scripts/verificar_todo.sh            completo (pytest tests + vitest run, 3-5 min)
#   scripts/verificar_todo.sh --rapido   solo casos_reales + guardianes (segundos)
# Solo lee y prueba: no toca produccion, no usa secretos, no hace push.
set -u
RAPIDO=0
[ "${1:-}" = "--rapido" ] || [ "${1:-}" = "-Rapido" ] && RAPIDO=1

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FALLOS=()
RESUMEN=()

buscar_python() {
  local comun principal c
  comun="$(git -C "$RAIZ" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
  principal=""
  [ -n "$comun" ] && principal="$(dirname "$comun")"
  for c in "${CUADRAME_PYTHON:-}" \
           "$RAIZ/backend/venv/Scripts/python.exe" "$RAIZ/backend/venv/bin/python" \
           "$principal/backend/venv/Scripts/python.exe" "$principal/backend/venv/bin/python"; do
    if [ -n "$c" ] && [ -x "$c" ]; then echo "$c"; return 0; fi
  done
  return 1
}

# ── Backend ──
if PY="$(buscar_python)"; then
  if [ "$RAPIDO" = 1 ]; then
    OBJ=(tests/casos_reales tests/test_guardian_contabilidad.py tests/test_columnas_de_arranque.py tests/test_errores_500_cors.py)
  else
    OBJ=(tests)
  fi
  echo ">> Backend: pytest ${OBJ[*]}"
  SAL="$(cd "$RAIZ/backend" && "$PY" -m pytest "${OBJ[@]}" -q -p no:warnings -p no:cacheprovider 2>&1)"; COD=$?
  LINEA="$(printf '%s\n' "$SAL" | grep -E '(passed|failed|error)' | tail -1)"
  if [ $COD -eq 0 ]; then
    RESUMEN+=("BACKEND  OK     $LINEA")
  else
    printf '%s\n' "$SAL" | tail -40
    RESUMEN+=("BACKEND  FALLO  $LINEA")
    FALLOS+=("Backend: fallaron pruebas (ver arriba).")
  fi
else
  RESUMEN+=("BACKEND  FALLO  sin venv de Python")
  FALLOS+=("Backend: no encuentro el venv (backend/venv). Defina CUADRAME_PYTHON.")
fi

# ── PWA ──
if [ "$RAPIDO" = 1 ]; then
  RESUMEN+=("PWA      OMITIDA (modo --rapido)")
elif [ ! -d "$RAIZ/pwa/node_modules" ]; then
  RESUMEN+=("PWA      FALLO  falta pwa/node_modules (npm ci)")
  FALLOS+=("PWA: no hay node_modules. Ejecute 'npm ci' dentro de pwa.")
else
  echo ">> PWA: npx vitest run"
  SAL="$(cd "$RAIZ/pwa" && npx vitest run 2>&1)"; COD=$?
  LINEA="$(printf '%s\n' "$SAL" | sed 's/\x1b\[[0-9;]*m//g' | grep -E '^\s*Tests\s' | tail -1 | sed 's/^ *//')"
  if [ $COD -eq 0 ]; then
    RESUMEN+=("PWA      OK     $LINEA")
  else
    printf '%s\n' "$SAL" | tail -40
    RESUMEN+=("PWA      FALLO  $LINEA")
    FALLOS+=("PWA: fallaron pruebas (ver arriba).")
  fi
fi

echo; echo "=== RESUMEN ==="
printf '%s\n' "${RESUMEN[@]}"
if [ ${#FALLOS[@]} -gt 0 ]; then
  echo; for f in "${FALLOS[@]}"; do echo "FALLO: $f"; done
  exit 1
fi
echo "Todo en verde."
