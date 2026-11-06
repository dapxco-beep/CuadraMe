#!/usr/bin/env bash
# Muestra las formas de aviso (notificaciones de bancos) que el lector NO entiende, de más a menos frecuentes.
# Solo trae plantillas anónimas de quienes aceptaron «estadísticas anónimas»: palabras fijas, sin textos, nombres ni montos.
# Dominio «aviso:nequi» = notificación de Nequi; «correo.com» = correos. Sirve para decidir qué banco enseñarle al lector.
# Uso:  bash backend/tools/ver_avisos_no_entendidos.sh [limite]
set -euo pipefail
ENV="$(dirname "$0")/../../../.secretos/daniel.env"
SECRETO="$(grep '^DANIEL_X_CRON_SECRET=' "$ENV" | cut -d= -f2-)"  # nunca se imprime
curl -s -H "X-Cron-Secret: $SECRETO" "https://api.cuadrame.dapx.shop/formas-asunto/cron/mas-frecuentes?limite=${1:-50}"
echo
