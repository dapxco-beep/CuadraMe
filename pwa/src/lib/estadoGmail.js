// «Gmail conectado · último extracto leído: 15 oct», avisos amables de extractos que faltan y el mensaje de «estamos
// aprendiendo el formato de tu banco». Puro (sin React) y probado en test/estado_gmail.test.js. Todo sale de datos que
// el backend ya entrega (gmail/estado, conciliacion/historial, sincronizacion/estado); cada campo es opcional.
import { cuentasConExtracto, mesDeHoy } from './estadoPorCuenta'

const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

export const TEXTO_APRENDIENDO = 'Estamos aprendiendo el formato de tu banco; no tienes que hacer nada.'

function fechaDe(valor) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(valor || '')
  return m ? { a: +m[1], m: +m[2], d: +m[3], clave: `${m[1]}-${m[2]}-${m[3]}` } : null
}

/** «15 oct» (sin hora ni zona: se parte a mano para que el teléfono no corra el día). '' si no es una fecha. */
export function fechaCorta(iso) {
  const f = fechaDe(iso)
  return f ? `${f.d} ${MESES_CORTOS[f.m - 1]}` : ''
}

/** El extracto leído más reciente del historial: {fecha, banco} o null. Ignora los que dieron error. */
export function ultimoExtractoLeido(historial) {
  let mejor = null
  for (const h of Array.isArray(historial) ? historial : []) {
    if (!h || /error|fall/i.test(h.estado || '')) continue
    const f = fechaDe(h.fecha_corte) || fechaDe(h.creado_en)
    if (f && (!mejor || f.clave > mejor.clave)) mejor = { fecha: f.clave, banco: h.banco_detectado || '' }
  }
  return mejor ? { fecha: mejor.fecha, banco: mejor.banco } : null
}

/** Línea de estado: «Gmail conectado · último extracto leído: 15 oct», «Gmail conectado · aún no he leído extractos»,
 *  «Gmail sin conectar». null mientras no se sabe el estado de Gmail. */
export function lineaGmail(gmail, ultimo) {
  if (!gmail || typeof gmail !== 'object') return null
  if (!gmail.conectado) return 'Gmail sin conectar'
  return `Gmail conectado · ${ultimo ? `último extracto leído: ${fechaCorta(ultimo.fecha)}` : 'aún no he leído extractos'}`
}

/** «Falta el extracto de septiembre de Nu» para el mes ya cerrado más reciente que tiene movimientos y ningún extracto
 *  (una por cuenta, máx. `max`). El mes en curso nunca cuenta: su extracto llega al cerrar. */
export function extractosFaltantes(cuentas, hoy = new Date(), max = 3) {
  const actual = mesDeHoy(hoy)
  const out = []
  for (const c of cuentasConExtracto(cuentas)) {
    const cerrados = (c.meses || []).filter((x) => x?.mes && x.mes < actual).sort((p, q) => (p.mes < q.mes ? 1 : -1))
    const celda = cerrados[0]
    if (celda && celda.estado === 'sin_extracto') {
      const m = Number(celda.mes.slice(5, 7))
      out.push({ cuentaId: c.id, mes: celda.mes, texto: `Falta el extracto de ${MESES[m - 1]} de ${c.nombre || 'tu cuenta'}` })
    }
    if (out.length >= max) break
  }
  return out
}

const PIDE_EXTRACTO = /m[aá]ndame el extracto para aprender su formato/i

/** Bancos sin lector: el backend puede marcar `estado_aprendizaje` o dejar «Mándame el extracto para aprender su formato»
 *  en el mensaje. Si ninguno existe, devuelve []. Un banco por vez, sin repetir. */
export function bancosAprendiendo(historial) {
  const vistos = new Set()
  for (const h of Array.isArray(historial) ? historial : []) {
    if (!h) continue
    const marca = h.estado_aprendizaje
    const aprende = (marca && !/^(listo|ok|aprendido|no)$/i.test(String(marca))) || PIDE_EXTRACTO.test(`${h.mensaje_lectura || ''} ${h.motivo || ''}`)
    if (aprende) vistos.add(h.banco_detectado || 'tu banco')
  }
  return [...vistos]
}

/** Todo junto para la pantalla. Cualquier entrada puede faltar. */
export function resumenEstadoGmail({ gmail, historial, cuentas, hoy = new Date() } = {}) {
  const ultimo = ultimoExtractoLeido(historial)
  return {
    linea: lineaGmail(gmail, ultimo),
    conectado: !!gmail?.conectado,
    avisos: gmail?.conectado === false ? [] : extractosFaltantes(cuentas, hoy),
    aprendiendo: bancosAprendiendo(historial).length > 0,
  }
}
