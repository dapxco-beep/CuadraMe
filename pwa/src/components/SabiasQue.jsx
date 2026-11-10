import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Lightbulb, X } from 'lucide-react'
import Icono from './Icono'
import { useModoMenu } from '../lib/modoSimple'

// «¿Sabías que…?»: UNA tarjeta con una función que la persona aún no usa. Se elige con lo que Inicio ya
// tiene cargado (funciones en uso, cuentas, Gmail): sin peticiones nuevas. Se descarta por id y se recuerda
// en este dispositivo (solo ids de texto), igual que «Consejo para ti».

const LLAVE = 'cuadrame:sabias-descartados'
const MAX_GUARDADOS = 50

// En orden de importancia; `falta` dice si la persona aún no la usa.
export const SABIAS = [
  { id: 'metas', to: '/metas', titulo: 'Puedes guardar para algo que quieres', texto: 'Crea una meta y ve cuánto llevas, poco a poco.', accion: 'Crear una meta', falta: (c) => !c.enUso.includes('/metas') },
  { id: 'fijos', to: '/recurrentes', titulo: 'Puedes anotar lo que pagas cada mes', texto: 'Arriendo, suscripciones: CuadraMe te avisa antes de que toquen.', accion: 'Agregar pagos fijos', falta: (c) => !c.enUso.includes('/recurrentes') },
  { id: 'correos', to: '/sincronizacion', state: { abrir: 'correo' }, titulo: 'CuadraMe puede registrar por ti', texto: 'Conecta tu Gmail y te sugerimos cada movimiento que te avisa el banco.', accion: 'Conectar Gmail', falta: (c) => !c.gmailConectado },
  { id: 'voz', to: '/conectar-dispositivo', titulo: 'Puedes registrar gastos hablando', texto: 'Dile a tu celular «gasté 20 mil en el almuerzo» con su asistente de voz (Siri en iPhone u otro en Android) y queda anotado.', accion: 'Ver cómo', falta: () => true },
  { id: 'deudas', to: '/deudas', titulo: 'Puedes ver cuál deuda pagar primero', texto: 'Anota lo que debes y mira cuál conviene saldar antes.', accion: 'Ver mis deudas', falta: (c) => !c.enUso.includes('/deudas') },
  { id: 'extracto', to: '/sincronizacion', state: { abrir: 'subir' }, titulo: 'Tu extracto del banco te ayuda a cuadrar', texto: 'Súbelo y mira qué movimientos faltan por registrar.', accion: 'Subir extracto', falta: (c) => c.cuentasCount > 0 },
  { id: 'compartir', to: '/compartir', titulo: 'Puedes compartir con tu pareja o familia', texto: 'Elige qué cuentas ven y si solo miran o también anotan.', accion: 'Compartir', falta: (c) => c.cuentasCount > 0 },
]

export function leerSabiasDescartados() {
  try {
    const v = JSON.parse(localStorage.getItem(LLAVE) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

/** La primera función por descubrir que no se haya descartado, o null. */
export function elegirSabias({ enUso = [], cuentasCount = 0, gmailConectado = true, descartados = [] } = {}) {
  const ctx = { enUso, cuentasCount, gmailConectado }
  return SABIAS.find((s) => !descartados.includes(s.id) && s.falta(ctx)) || null
}

export default function SabiasQue({ cuentasCount = 0, gmailConectado = true, className = 'mx-6 mt-3' }) {
  const { enUso } = useModoMenu()
  const [descartados, setDescartados] = useState(leerSabiasDescartados)
  const s = elegirSabias({ enUso, cuentasCount, gmailConectado, descartados })
  if (!s) return null

  function descartar() {
    const nuevos = [...descartados, s.id].slice(-MAX_GUARDADOS)
    setDescartados(nuevos)
    try {
      localStorage.setItem(LLAVE, JSON.stringify(nuevos))
    } catch {
      /* sin almacenamiento: reaparece al recargar, no pasa nada */
    }
  }

  return (
    <section className={`${className} rounded-2xl bg-accent-soft p-4`} aria-label="¿Sabías que…?" data-testid="sabias-que" data-sabias={s.id}>
      <div className="flex items-start gap-3">
        <span className="w-9 h-9 rounded-full bg-paper-raised text-accent flex items-center justify-center shrink-0">
          <Icono icono={Lightbulb} tam="sm" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="t-kicker text-ink-soft">¿Sabías que…?</p>
          <h2 className="t-cuerpo font-semibold">{s.titulo}</h2>
          <p className="t-apoyo mt-0.5">{s.texto}</p>
          <Link to={s.to} state={s.state} className="text-sm text-accent font-semibold min-h-11 inline-flex items-center">
            {s.accion}
          </Link>
        </div>
        <button type="button" onClick={descartar} aria-label={`Descartar: ${s.titulo}`} className="shrink-0 w-11 h-11 -mt-2 -mr-2 flex items-center justify-center text-ink-soft">
          <Icono icono={X} tam="sm" />
        </button>
      </div>
    </section>
  )
}
