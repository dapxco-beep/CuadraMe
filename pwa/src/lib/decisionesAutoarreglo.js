// Decisiones del autoarreglo en lenguaje de la persona (docs/GUIA_DE_TEXTOS.md). El servidor manda `tipo`, `cantidad`,
// `texto`, `accion` y `ruta`; aquí se decide qué se MUESTRA. Un tipo que no conocemos cae al `texto` del servidor.

const mov = (n) => `${n} ${n === 1 ? 'movimiento' : 'movimientos'}`
const ext = (n) => `${n} ${n === 1 ? 'extracto' : 'extractos'}`
const ruta = '/sincronizacion'

// tipo → { texto(n), accion, ruta? }. Sin cantidad (0 o ausente) se usa la forma sin número.
export const FRASES_DECISION = {
  dudosas: { texto: (n) => `Tengo una duda con ${n ? mov(n) : 'algunos movimientos'}. ¿Los revisamos?`, accion: 'Revisar' },
  varias_tarjetas: { texto: () => 'Tienes varias tarjetas del mismo banco y no sé a cuál va cada extracto.', accion: 'Elegir tarjeta' },
  clave_pdf: { texto: (n) => `Necesito la clave de ${n ? ext(n) : 'tus extractos'} en PDF para poder leer${n === 1 ? 'lo' : 'los'}.`, accion: 'Poner la clave' },
  fechas_dudosas: { texto: (n) => `Tengo una duda con las fechas de ${n ? ext(n) : 'algunos extractos'}. ¿Los revisamos?`, accion: 'Revisar' },
  deuda_inicial_sin_lectura: { texto: () => 'Aún no sé con cuánto empezó tu tarjeta: me falta tu primer extracto.', accion: 'Ver' },
  tarjeta_sin_verificar: { texto: (n) => `No pude comprobar ${n ? ext(n) : 'algunos extractos'} de tu tarjeta contra el banco. ¿Los vemos?`, accion: 'Revisar' },
}

/** Una decisión del servidor lista para pintar: { clave, texto, accion, ruta, cantidad }. */
export function decisionVisible(d) {
  const f = FRASES_DECISION[d?.tipo]
  const n = Number(d?.cantidad) || 0
  return {
    clave: d?.tipo,
    texto: f ? f.texto(n) : d?.texto,
    accion: f ? f.accion : d?.accion,
    ruta: d?.ruta || f?.ruta || ruta,
    cantidad: d?.cantidad,
  }
}
