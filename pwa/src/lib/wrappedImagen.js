// Lógica del resumen mensual "Wrapped": diapositivas, imagen para compartir y
// envío. Sin dependencias nuevas: la imagen se dibuja con la API Canvas nativa
// (html-to-image pesaría ~15 KB y fallaría con fuentes/SVG en Safari; aquí la
// tarjeta es simple y la dibujamos nosotros, con resultado idéntico en todos
// los navegadores).
import { formatCOP, formatPorcentaje } from './format'
import { CUERPO, FICHA, CHECK } from '../brand/geometria'

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
      detalle: d.categoria_top ? `${fmt(d.categoria_top.monto)} (${formatPorcentaje((d.categoria_top.monto / d.gasto_total) * 100, { decimales: 0 })} de tu gasto)` : 'Registra gastos para verla',
    },
    {
      id: 'ahorro', emoji: d.ahorro >= 0 ? '🌱' : '⚠️', titulo: d.ahorro >= 0 ? 'Lograste ahorrar' : 'Gastaste más de lo que entró',
      valor: fmt(Math.abs(d.ahorro)),
      detalle: d.ingresos > 0 ? `${formatPorcentaje(d.tasa_ahorro)} de tus ingresos` : 'No registraste ingresos este mes',
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
      valor: `${baja ? '↓' : '↑'} ${formatPorcentaje(Math.abs(d.variacion_gasto_pct))}`,
      detalle: `${baja ? 'menos' : 'más'} que el mes anterior (${fmt(d.gasto_mes_anterior)})`,
    }
  }
  diapos.push({ id: 'comparacion', emoji: '📊', titulo: 'Frente al mes pasado', ...comparacion })
  return diapos
}

const FUENTE = "'Sora', system-ui, -apple-system, sans-serif"

// Dibuja el isotipo con la misma geometría de la app (Path2D acepta los mismos
// paths SVG). Si el navegador no tiene Path2D, simplemente se omite.
function dibujarIsotipo(ctx, x, y, lado, { cuerpo = '#e8823f', ficha = '#e8bc63', check = '#17140f', conFicha = true } = {}) {
  if (typeof Path2D === 'undefined') return
  const k = lado / 64
  ctx.save()
  ctx.translate(x, y)
  ctx.scale(k, k)
  ctx.fillStyle = cuerpo
  ctx.fill(new Path2D(CUERPO))
  if (conFicha) {
    ctx.fillStyle = ficha
    ctx.fill(new Path2D(FICHA))
    ctx.strokeStyle = check
    ctx.lineWidth = 3.4
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.stroke(new Path2D(CHECK))
  }
  ctx.restore()
}

// Dibuja la tarjeta compartible (1080x1350) en un contexto 2D.
// `fmt` formatea los montos: pásale el `fmt` de useBloqueo() y, con "ocultar
// saldos" activo, la imagen sale con •••• en vez de cifras reales (quien
// comparte una imagen no debería filtrar su plata por accidente).
export function dibujarTarjeta(ctx, d, fmt = formatCOP) {
  const W = 1080
  const H = 1350
  const diapos = construirDiapositivas(d, fmt)

  // Fondo: noche cálida + papel cuadriculado (la retícula del libro contable)
  const grad = ctx.createLinearGradient(0, 0, W, H)
  grad.addColorStop(0, '#17140f')
  grad.addColorStop(1, '#3a2312')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, W, H)
  ctx.strokeStyle = 'rgba(255,255,255,0.045)'
  ctx.lineWidth = 2
  ctx.beginPath()
  for (let p = 0; p <= W; p += 54) {
    ctx.moveTo(p, 0)
    ctx.lineTo(p, H)
  }
  for (let p = 0; p <= H; p += 54) {
    ctx.moveTo(0, p)
    ctx.lineTo(W, p)
  }
  ctx.stroke()

  // Marca arriba: isotipo + wordmark
  dibujarIsotipo(ctx, 70, 62, 92)
  ctx.textAlign = 'left'
  ctx.font = `700 52px ${FUENTE}`
  ctx.fillStyle = '#f5f1e8'
  ctx.fillText('Cuadra', 184, 130)
  const anchoCuadra = ctx.measureText('Cuadra')?.width ?? 170
  ctx.fillStyle = '#e8823f'
  ctx.fillText('Me', 184 + anchoCuadra, 130)

  ctx.fillStyle = '#f5f1e8'
  ctx.font = `800 88px ${FUENTE}`
  ctx.fillText(`Mi ${nombreMes(d.mes)}`, 80, 280)

  // Tarjetas con la esquina firme de la marca (arriba a la derecha, grande)
  let y = 350
  for (const s of diapos) {
    ctx.fillStyle = 'rgba(255,255,255,0.08)'
    ctx.beginPath()
    ctx.roundRect(60, y, W - 120, 160, [28, 64, 28, 28])
    ctx.fill()
    ctx.fillStyle = '#b9b19e'
    ctx.font = `500 29px ${FUENTE}`
    ctx.fillText(`${s.emoji}  ${s.titulo}`, 96, y + 50)
    ctx.fillStyle = '#f5f1e8'
    ctx.font = `800 56px ${FUENTE}`
    ctx.fillText(s.valor, 96, y + 108)
    ctx.fillStyle = '#b9b19e'
    ctx.font = `400 25px ${FUENTE}`
    ctx.fillText(s.detalle.slice(0, 62), 96, y + 143)
    y += 180
  }

  // Firma: sello de cuadre + lema (marca de agua de autoría)
  const yPie = H - 62
  dibujarIsotipo(ctx, 70, yPie - 38, 54)
  ctx.fillStyle = '#e8bc63'
  ctx.font = `700 28px ${FUENTE}`
  ctx.fillText('Cuadra tus cuentas, simple y al día', 140, yPie - 4)
  ctx.textAlign = 'right'
  ctx.fillStyle = '#8a8372'
  ctx.font = `500 24px ${FUENTE}`
  ctx.fillText('Hecho con CuadraMe', W - 70, yPie - 4)
  ctx.textAlign = 'left'
}

export function generarImagen(d, fmt = formatCOP) {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement('canvas')
    canvas.width = 1080
    canvas.height = 1350
    const ctx = canvas.getContext('2d')
    if (!ctx) return reject(new Error('Tu navegador no puede generar la imagen'))
    // Espera a que la tipografía de marca esté lista, para que la imagen salga en Sora
    const listo = document.fonts?.load ? document.fonts.load(`700 40px Sora`).catch(() => {}) : Promise.resolve()
    listo.then(() => {
      dibujarTarjeta(ctx, d, fmt)
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('No se pudo crear la imagen'))), 'image/png')
    })
  })
}

// Web Share API con archivo; si no se puede (escritorio, navegadores viejos),
// descarga el PNG. Devuelve 'compartido' | 'descargado' | 'cancelado'.
export async function compartirImagen(d, fmt = formatCOP) {
  const blob = await generarImagen(d, fmt)
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
