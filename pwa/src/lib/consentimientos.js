// Textos y reglas del flujo de autorización de tratamiento de datos (Ley 1581 de 2012).
// VERSION_TEXTOS debe coincidir con backend/app/routers/consentimientos.py y con la
// versión que muestran las pantallas legales: al cambiar los textos se sube en los tres sitios
// y a todos los usuarios se les vuelve a pedir la autorización.

export const VERSION_TEXTOS = '1.1'
export const CORREO_RESPONSABLE = 'dapxco@gmail.com'

export const FINALIDADES = {
  tratamiento_basico: {
    titulo: 'Tratamiento básico de mis datos',
    obligatoria: true,
    texto:
      'Autorizo a DAPX a tratar mi nombre, correo y la información financiera que yo ingrese (cuentas, movimientos, presupuestos, metas, deudas) para prestarme el servicio de CuadraMe.',
  },
  lectura_correo: {
    titulo: 'Leer mi correo (Gmail, solo lectura)',
    obligatoria: false,
    texto:
      'Autorizo a CuadraMe a leer mi Gmail en modo solo lectura para sugerirme movimientos y encontrar extractos bancarios. No envía, borra ni modifica correos; puedo desconectarlo cuando quiera.',
  },
  ia: {
    titulo: 'Procesar mis datos con inteligencia artificial',
    obligatoria: false,
    texto:
      'Autorizo que el texto que escribo al asistente y las fotos de facturas se envíen a un proveedor de IA para responderme. No se envían claves ni identificadores y no se guardan las conversaciones.',
  },
  notificaciones: {
    titulo: 'Recibir notificaciones',
    obligatoria: false,
    texto: 'Autorizo recibir avisos (alertas de presupuesto, recordatorios de pago, resúmenes) por notificaciones push y correo.',
  },
}

export const ORDEN_OPCIONALES = ['lectura_correo', 'ia', 'notificaciones']

export const DERECHOS = ['Conocer', 'Actualizar', 'Rectificar', 'Suprimir', 'Revocar la autorización']

export function formatearFechaCO(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || '')
  if (!m) return ''
  const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
  const h = +m[4]
  return `${+m[3]} ${meses[+m[2] - 1]} ${m[1]}, ${h % 12 || 12}:${m[5]} ${h < 12 ? 'a. m.' : 'p. m.'} (hora Colombia)`
}
