#!/usr/bin/env bash
# Despliega CuadraMe a produccion (backend Railway, PWA Vercel) por CLI. NO hace git push.
#   scripts/desplegar.sh --solo-verificar [--rapido]   verifica y termina (no despliega)
#   scripts/desplegar.sh [--rama-ok]                    despliega; pide escribir DESPLEGAR
# Usa las sesiones ya iniciadas de los CLI; no lee ni imprime secretos.
set -u
SOLO=0; RAPIDO=0; RAMA_OK=0
for a in "$@"; do case "$a" in
  --solo-verificar|-SoloVerificar) SOLO=1;; --rapido|-Rapido) RAPIDO=1;; --rama-ok|-PermitirRama) RAMA_OK=1;;
esac; done
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S="$RAIZ/scripts"
parar() { echo; echo "DETENIDO: $1"; echo 'Si algo quedo a medias, vea docs/OPERACION.md (seccion "Si algo sale mal").'; exit 1; }

if [ $SOLO = 1 ]; then
  echo "== Modo --solo-verificar: no se despliega nada =="
  if [ $RAPIDO = 1 ]; then bash "$S/verificar_todo.sh" --rapido; else bash "$S/verificar_todo.sh"; fi; A=$?
  bash "$S/verificar_produccion.sh"; B=$?
  [ $A -eq 0 ] && [ $B -eq 0 ] && exit 0 || exit 1
fi

for cli in git railway vercel; do command -v $cli >/dev/null 2>&1 || parar "No esta instalado el CLI '$cli'."; done
RAMA="$(git -C "$RAIZ" rev-parse --abbrev-ref HEAD)"
[ "$RAMA" = main ] || [ $RAMA_OK = 1 ] || parar "Esta en la rama '$RAMA', no en main. Use --rama-ok si es a proposito."
[ -z "$(git -C "$RAIZ" status --porcelain --untracked-files=no)" ] || parar "Hay cambios sin commitear en archivos versionados. Haga commit antes."

echo "Se va a desplegar a PRODUCCION la rama '$RAMA' en $(git -C "$RAIZ" rev-parse --short HEAD)."
echo "Backend: Railway | PWA: Vercel (cuadrame.dapx.shop). No se hace git push."
read -r -p "Escriba DESPLEGAR (en mayusculas) para continuar: " CONF
[ "$CONF" = "DESPLEGAR" ] || parar "No se escribio DESPLEGAR. No se hizo nada."

echo; echo "== 1/6 Verificar todo =="
bash "$S/verificar_todo.sh" || parar "Las pruebas fallaron. No se desplego nada."

echo; echo "== 2/6 Commit de despliegue (autor del equipo) =="
git -C "$RAIZ" -c user.name=DAPX -c user.email=dapxco@gmail.com commit --allow-empty -m "Despliegue a produccion $(date '+%Y-%m-%d %H:%M')" || parar "No pude crear el commit."
SHA="$(git -C "$RAIZ" rev-parse HEAD)"; CORTO="${SHA:0:7}"
echo "Commit a desplegar: $CORTO"

echo; echo "== 3/6 Backend (Railway) =="
( cd "$RAIZ/backend" && railway variables --set "GIT_COMMIT_SHA=$SHA" --service backend ) || parar "No pude fijar GIT_COMMIT_SHA en Railway."
( cd "$RAIZ/backend" && railway up --service backend --detach ) || parar "railway up fallo. El backend sigue en la version anterior."

echo; echo "== 4/6 PWA (Vercel) =="
if ! ( cd "$RAIZ/pwa" && vercel deploy --prod --yes --build-env "COMMIT_SHA=$CORTO" ); then
  echo "Vercel fallo (a veces 'Not authorized' transitorio); reintento una vez..."; sleep 10
  ( cd "$RAIZ/pwa" && vercel deploy --prod --yes --build-env "COMMIT_SHA=$CORTO" ) || parar "vercel deploy fallo. El backend YA se subio; la PWA sigue en la version anterior."
fi

echo; echo "== 5/6 Esperando que Railway termine de construir =="
OK=0
for i in $(seq 1 12); do
  sleep 30; echo "-- Intento $i de 12 --"
  if bash "$S/verificar_produccion.sh" "$CORTO"; then OK=1; break; fi
done
echo; echo "== 6/6 Resultado =="
[ $OK = 1 ] || parar "Produccion no quedo en $CORTO despues de 6 minutos."
echo "Desplegado y verificado: $CORTO. Este script NO hizo push."
