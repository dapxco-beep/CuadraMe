// Mensajes por país: andamiaje ligero de i18n (NO traduce toda la app).
//
// Cómo funciona: `t(clave, pais, vars)` busca el texto en este orden
//   1. el país exacto (MX, AR...)         -> TEXTOS_PAIS[pais][clave]
//   2. el idioma regional (es-MX, es-AR)  -> TEXTOS_IDIOMA['es-MX'][clave]   (opcional)
//   3. el español neutro                  -> TEXTOS_BASE[clave]              (siempre existe)
// Solo van aquí los textos que cambian por país (impuestos, pago inmediato, ayuda, tratamiento).
// El resto de la app sigue en español neutro dentro de los componentes.
//
// Cómo agregar:
//   - Una clave nueva: agrégala a TEXTOS_BASE y, si cambia en un país, a TEXTOS_PAIS[país].
//   - es-MX / es-AR: crea TEXTOS_IDIOMA['es-AR'] con solo lo que difiere (p. ej. voseo).
//   - pt-BR: crea TEXTOS_IDIOMA['pt-BR'] COMPLETO (no hereda del español) y marca Brasil
//     `disponible: True` en backend/app/paises.py; antes hay que extraer el resto de la UI.
import { configPais } from './paises'

export const TEXTOS_BASE = {
  'impuestos.titulo': 'Impuestos',
  'impuestos.aviso': 'Información de apoyo, no asesoría tributaria. Confirma siempre con un contador y con la autoridad tributaria de tu país.',
  'impuestos.declaracion': 'Declaración anual de impuestos',
  'impuestos.recordatorio': 'Recuerda revisar el calendario de la declaración anual en {autoridad}.',
  'pago_inmediato.explica': 'Pagos inmediatos entre cuentas: {nombre}.',
  'tasas.titulo': 'Tasas de referencia',
  'tasas.fuente': 'Tasa de referencia: {entidad} ({sigla}).',
  'cuentas.escribe_banco': 'Escribe el nombre de tu banco o billetera.',
  'extractos.aun_no': 'Aún no leemos extractos de {pais} automáticamente: usa un archivo Excel/CSV o agrega los movimientos a mano.',
}

export const TEXTOS_PAIS = {
  CO: {
    'impuestos.aviso': 'Información de apoyo, no asesoría tributaria. Los valores son estimaciones; confirma siempre con tu contador y con la normativa vigente de la DIAN.',
    'impuestos.recordatorio': 'Recuerda revisar el calendario de renta de la DIAN.',
  },
  MX: {
    'impuestos.declaracion': 'Declaración anual (SAT)',
    'impuestos.recordatorio': 'Las personas físicas presentan su declaración anual ante el SAT en abril. Confirma fechas y obligaciones con tu contador.',
  },
  CL: {
    'impuestos.declaracion': 'Operación Renta (SII)',
    'impuestos.recordatorio': 'La Operación Renta del SII se hace en abril. Confirma fechas y obligaciones con tu contador.',
  },
  PE: {
    'impuestos.declaracion': 'Declaración anual de renta (SUNAT)',
    'impuestos.recordatorio': 'La declaración anual de renta ante SUNAT se presenta entre marzo y abril según cronograma. Confírmalo con tu contador.',
  },
  AR: {
    'impuestos.declaracion': 'Ganancias y Bienes Personales (ARCA)',
    'impuestos.recordatorio': 'Revisá el calendario de ARCA para Ganancias y Bienes Personales.',
    'cuentas.escribe_banco': 'Escribí el nombre de tu banco o billetera.',
  },
}

export const TEXTOS_IDIOMA = {}

const AUTORIDAD = {
  CO: 'la DIAN', MX: 'el SAT', CL: 'el SII', PE: 'SUNAT', AR: 'ARCA', UY: 'la DGI', EC: 'el SRI',
  PA: 'la DGI', CR: 'Hacienda', BR: 'la Receita Federal',
}

function rellenar(texto, vars) {
  return texto.replace(/\{(\w+)\}/g, (_, k) => (vars && vars[k] != null ? String(vars[k]) : `{${k}}`))
}

export function t(clave, pais, vars = {}) {
  const c = configPais(pais)
  const texto = TEXTOS_PAIS[pais]?.[clave] ?? (c ? TEXTOS_IDIOMA[c.idioma]?.[clave] : undefined) ?? TEXTOS_BASE[clave] ?? clave
  return rellenar(texto, {
    autoridad: AUTORIDAD[pais] || 'tu autoridad tributaria',
    nombre: c?.pago_inmediato?.nombre,
    entidad: c?.banco_central?.nombre,
    sigla: c?.banco_central?.sigla,
    pais: c?.nombre,
    ...vars,
  })
}
