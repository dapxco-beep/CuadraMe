// Armado de los datos al crear una cuenta. Para una tarjeta de crédito el
// cliente escribe lo que DEBE (positivo) y se guarda como saldo NEGATIVO:
// en CuadraMe un gasto resta, así que saldo -1.200.000 = cupo usado 1.200.000.

// Lee un monto escrito a la colombiana: "1.200.000" -> 1200000, "1.200,50" ->
// 1200.5, "1200.5" -> 1200.5. Un punto seguido de exactamente 3 dígitos (o
// varios puntos) es separador de miles; la coma es el decimal.
export function leerMonto(texto) {
  const t = String(texto ?? '').trim().replace(/[^\d.,]/g, '')
  if (!t) return 0
  let limpio
  if (t.includes(',')) {
    limpio = t.replace(/\./g, '').replace(',', '.')
  } else if ((t.match(/\./g) || []).length > 1 || /^\d{1,3}\.\d{3}$/.test(t)) {
    limpio = t.replace(/\./g, '')
  } else {
    limpio = t
  }
  const n = Number(limpio)
  return Number.isFinite(n) ? n : 0
}

// Campos: texto tal cual lo escribió el cliente en el formulario.
export function datosCuentaNueva({ nombre, tipo, icono, moneda, saldo, cupo, debes, corte, pago, tasa, alias }) {
  const base = { nombre: nombre.trim(), tipo, icono, moneda }
  if (alias && alias.trim()) base.alias_tarjeta = alias.trim()
  if (tipo !== 'credito') return { ...base, saldo: leerMonto(saldo) }
  const datos = { ...base, saldo: -Math.abs(leerMonto(debes)) }
  if (cupo) datos.cupo_total = leerMonto(cupo)
  if (corte) datos.dia_corte = Number(corte)
  if (pago) datos.dia_pago = Number(pago)
  if (tasa) datos.tasa_ea = Number(tasa)
  return datos
}

// ── Cuenta guiada por banco ────────────────────────────────────────────────
// Un mismo banco suele dar dos productos: la cuenta de ahorros/débito y la tarjeta de crédito.
// Estas reglas puras dicen cuál es «la otra» para ofrecerla justo después de crear la primera.

/** 'Nu Colombia' -> 'Nu' (el nombre que la persona dice en voz alta). */
export function nombreCortoBanco(banco) {
  return String(banco || '').replace(/\s+Colombia$/i, '').trim() || String(banco || '').trim()
}

/** Tipo que NO acaba de crear: ahorro -> credito, credito -> ahorro. null si no aplica (efectivo, inversión). */
export function productoAlterno(tipo) {
  if (tipo === 'ahorro') return 'credito'
  if (tipo === 'credito') return 'ahorro'
  return null
}

/** Texto del botón «Agregar también mi tarjeta de crédito Nu» / «…mi cuenta de ahorros Nu». */
export function textoAgregarAlterno(banco, tipoCreado) {
  const alterno = productoAlterno(tipoCreado)
  if (!alterno || !banco) return ''
  const corto = nombreCortoBanco(banco)
  return alterno === 'credito' ? `Agregar también mi tarjeta de crédito ${corto}` : `Agregar también mi cuenta de ahorros ${corto}`
}

// null si todo está bien; si no, el mensaje para el cliente.
export function validarTarjetaNueva({ corte, pago, tasa }) {
  const dia = (v) => v === '' || (Number(v) >= 1 && Number(v) <= 31)
  if (!dia(corte) || !dia(pago)) return 'Los días deben estar entre 1 y 31'
  if (tasa !== '' && (Number(tasa) < 0 || Number(tasa) > 200)) return 'La tasa debe estar entre 0 y 200%'
  return null
}
