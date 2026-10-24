import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, BellRing, CreditCard, FileText, PieChart, TrendingUp, X } from 'lucide-react'
import { api } from '../lib/api'
import Icono from './Icono'

const LLAVE = 'cuadrame:recordatorios-descartados'
const ICONOS = { tarjeta: CreditCard, presupuesto: PieChart, extractos: FileText, saldo_negativo: AlertTriangle, gasto_grande: TrendingUp }

// Descartados: se guardan en este dispositivo (solo claves de texto, sin datos del usuario).
// Cada recordatorio trae una `clave` que incluye la fecha o el periodo, así que cuando hay una
// situación nueva (otro mes, otro pago) vuelve a salir aunque hayas descartado la anterior.
function leerDescartados() {
  try {
    const v = JSON.parse(localStorage.getItem(LLAVE) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

function guardarDescartados(claves) {
  try {
    localStorage.setItem(LLAVE, JSON.stringify(claves))
  } catch {
    /* sin almacenamiento: el aviso reaparece al recargar, no pasa nada */
  }
}

/**
 * Tarjetas de recordatorio en Inicio: pago de tarjeta cerca, presupuesto al 80 % o más y
 * extractos de Gmail por revisar. Todo se calcula en el servidor; si falla, no se muestra nada.
 */
// omitirExtractos: Inicio ya muestra «N por resolver» en el botón Traer movimientos; decirlo dos veces confunde.
// soloTipos / omitirTipos: el Inicio simple muestra arriba los urgentes y «Ver más» el resto, sin repetirlos.
export default function Recordatorios({ omitirExtractos = false, soloTipos = null, omitirTipos = [], max = null }) {
  const [lista, setLista] = useState([])
  const [descartados, setDescartados] = useState(leerDescartados)

  useEffect(() => {
    let activo = true
    Promise.resolve()
      .then(() => api.recordatorios?.())
      .then((r) => {
        if (!activo || !Array.isArray(r)) return
        setLista(r)
        // Limpia claves viejas que ya no existen, para que la lista no crezca sin fin.
        const vigentes = leerDescartados().filter((k) => r.some((x) => x.clave === k))
        guardarDescartados(vigentes)
      })
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [])

  const visibles = lista
    .filter((r) => !descartados.includes(r.clave) && !(omitirExtractos && r.tipo === 'extractos'))
    .filter((r) => (soloTipos ? soloTipos.includes(r.tipo) : !omitirTipos.includes(r.tipo)))
    .slice(0, max || undefined)
  if (!visibles.length) return null

  function descartar(clave) {
    const nuevos = [...descartados, clave]
    setDescartados(nuevos)
    guardarDescartados(nuevos)
  }

  return (
    <section className="mx-6 mt-4 space-y-2" aria-label="Recordatorios" data-testid="recordatorios">
      {visibles.map((r) => (
        <div
          key={r.clave}
          data-testid="recordatorio"
          className="rounded-2xl bg-paper-raised border border-line flex items-stretch"
        >
          <Link to={r.ruta} className="flex-1 min-w-0 flex items-center gap-3 pl-4 py-3 min-h-[56px]">
            <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
              <Icono icono={ICONOS[r.tipo] || BellRing} tam="md" />
            </span>
            <span className="min-w-0">
              <span className="block t-cuerpo font-semibold">{r.titulo}</span>
              <span className="block t-apoyo">{r.texto}</span>
            </span>
          </Link>
          <button
            type="button"
            onClick={() => descartar(r.clave)}
            aria-label={`Descartar: ${r.titulo}`}
            className="shrink-0 w-12 flex items-center justify-center text-ink-soft"
          >
            <Icono icono={X} tam="sm" />
          </button>
        </div>
      ))}
    </section>
  )
}
