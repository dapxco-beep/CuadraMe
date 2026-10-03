// Lógica del resumen mensual "Wrapped": diapositivas, imagen para compartir y
// envío. Sin dependencias nuevas: la imagen se dibuja con la API Canvas nativa
// (html-to-image pesaría ~15 KB y fallaría con fuentes/SVG en Safari; aquí la
// tarjeta es simple y la dibujamos nosotros, con resultado idéntico en todos
// los navegadores).
import { formatCOP } from './format'

export function nombreMes(mes) {
  const [a, m] = mes.split('-').map(Number)
  const nombre = new Date(a, m - 1, 1).toLocaleDateString('es-CO', { month: 'long' })
  return nombre.charAt(0).toUpperCase() + nombre.slice(1)
}

// Devuelve las diapositivas a partir de los datos del backend. `fmt` permite
// enmascarar montos en pantalla; para la imagen se usa formatCOP real.
export function construirDiapositivas(d, fmt = formatCOP) {
  const mes = nombreMes(d.mes)
  const vacio = d.num_movimientos === 0
  const diapos = [
    {
      id: 'gasto', emoji: '💸', titulo: `Gastaste en ${mes}`,
      valor: fmt(d.gasto_total),
      detalle: vacio ? 'Aún no hay movimientos este mes' : `en ${d.num_movimientos} movimientos`,
    },
    {
      id: 'categoria', emoji: '🏆', titulo: 'Tu categoría top',
      valor: d.categoria_top ? d.categoria_top.categoria : 'Sin gastos',
      detalle: d.categoria_top ? `${fmt(d.categoria_top.monto)} (${Math.round((d.categoria_top.monto / d.gasto_total) * 100)}% de tu gasto)` : 'Registra gastos para verla',
    },
    {
      id: 'ahorro', emoji: d.ahorro >= 0 ? '🌱' : '⚠️', titulo: d.ahorro >= 0 ? 'Lograste ahorrar' : 'Gastaste más de lo que entró',
      valor: fmt(Math.abs(d.ahorro)),
      detalle: d.ingresos > 0 ? `${d.tasa_ahorro}% de tus ingresos` : 'No registraste ingresos este mes',
    },
    {
      id: 'racha', emoji: '🔥', titulo: 'Tu mejor racha',
      valor: `${d.mejor_racha} ${d.mejor_racha === 1 ? 'día' : 'días'}`,
      detalle: 'seguidos registrando movimientos',
    },
  ]
  let comparacion
  if (d.variacion_gasto_pct === null || d.variacion_gasto_pct === undefined) {
    comparacion = { valor: '—', detalle: 'No hay mes anterior con gastos para comparar' }
  } else if (d.variacion_gasto_pct === 0) {
    comparacion = { valor: 'Igual', detalle: 'que el mes anterior' }
  } else {
    const baja = d.variacion_gasto_pct < 0
    comparacion = {
      valor: `${baja ? '↓' : '↑'} ${Math.abs(d.variacion_gasto_pct)}%`,
      detalle: `${baja ? 'menos' : 'más'} que el mes anterior (${fmt(d.gasto_mes_anterior)})`,
    }
  }
  diapos.push({ id: 'comparacion', emoji: '📊', titulo: 'Frente al mes pasado', ...comparacion })
  return diapos
}

// Dibuja la tarjeta compartible (1080x1350) en un contexto 2D.
export function dibujarTarjeta(ctx, d) {
  const W = 1080
  const H = 1350
  const diapos = construirDiapositivas(d)
  const grad = ctx.createLinearGradient(0, 0, W, H)
  grad.addColorStop(0, '#17140f')
  grad.addColorStop(1, '#3a2312')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, W, H)

  ctx.textAlign = 'left'
  ctx.fillStyle = '#e8823f'
  ctx.font = '700 40px system-ui, sans-serif'
  ctx.fillText('CuadraMe', 80, 120)
  ctx.fillStyle = '#f5f1e8'
  ctx.font = '800 84px system-ui, sans-serif'
  ctx.fillText(`Mi ${nombreMes(d.mes)}`, 80, 240)

  let y = 340
  for (const s of diapos) {
    ctx.fillStyle = 'rgba(255,255,255,0.07)'
    ctx.beginPath()
    ctx.roundRect(60, y, W - 120, 168, 32)
    ctx.fill()
    ctx.fillStyle = '#a39c8a'
    ctx.font = '500 30px system-ui, sans-serif'
    ctx.fillText(`${s.emoji}  ${s.titulo}`, 96, y + 52)
    ctx.fillStyle = '#f5f1e8'
    ctx.font = '800 56px system-ui, sans-serif'
    ctx.fillText(s.valor, 96, y + 112)
    ctx.fillStyle = '#a39c8a'
    ctx.font = '400 26px system-ui, sans-serif'
    ctx.fillText(s.detalle.slice(0, 60), 96, y + 150)
    y += 192
  }
  ctx.fillStyle = '#6b6656'
  ctx.font = '400 28px system-ui, sans-serif'
  ctx.fillText('Hecho con CuadraMe', 80, H - 50)
}

export function generarImagen(d) {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement('canvas')
    canvas.width = 1080
    canvas.height = 1350
    const ctx = canvas.getContext('2d')
    if (!ctx) return reject(new Error('Tu navegador no puede generar la imagen'))
    dibujarTarjeta(ctx, d)
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('No se pudo crear la imagen'))), 'image/png')
  })
}

// Web Share API con archivo; si no se puede (escritorio, navegadores viejos),
// descarga el PNG. Devuelve 'compartido' | 'descargado' | 'cancelado'.
export async function compartirImagen(d) {
  const blob = await generarImagen(d)
  const nombre = `cuadrame-${d.mes}.png`
  const archivo = new File([blob], nombre, { type: 'image/png' })
  if (navigator.canShare?.({ files: [archivo] }) && navigator.share) {
    try {
      await navigator.share({ files: [archivo], title: `Mi ${nombreMes(d.mes)} en CuadraMe` })
      return 'compartido'
    } catch (err) {
      if (err?.name === 'AbortError') return 'cancelado'
      // cualquier otro fallo: cae a la descarga
    }
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return 'descargado'
}
