import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileUp, Mail, Mic, Users, Wand2 } from 'lucide-react'

// Tarjetas de descubribilidad, mismo patrón visual que la alerta de Gmail que
// ya funcionaba bien — pero rotando varias funciones en vez de mostrar solo
// una, para que el usuario se tope con más cosas de la app sin tener que
// buscarlas en Perfil.
const TARJETAS_BASE = [
  {
    id: 'correos',
    to: '/correos',
    icon: Mail,
    titulo: 'Deja que CuadraMe registre por ti',
    texto: 'Conecta tu Gmail y te sugerimos cada movimiento del banco',
    mostrarSi: (ctx) => !ctx.gmailConectado,
  },
  {
    id: 'voz',
    to: '/conectar-dispositivo',
    icon: Mic,
    titulo: 'Registra gastos hablando',
    texto: 'Di "gasté 20 mil en el almuerzo" y Siri lo registra por ti',
    mostrarSi: () => true,
  },
  {
    id: 'reglas',
    to: '/reglas-categoria',
    icon: Wand2,
    titulo: 'Enséñale tus categorías',
    texto: 'Crea reglas para que Netflix, Uber o tu arriendo se categoricen solos',
    mostrarSi: () => true,
  },
  {
    id: 'conciliacion',
    to: '/conciliacion',
    icon: FileUp,
    titulo: 'Sube tu extracto del banco',
    texto: 'Compáralo con tus movimientos y encuentra lo que falta registrar',
    mostrarSi: () => true,
  },
  {
    id: 'compartir',
    to: '/compartir',
    icon: Users,
    titulo: 'Comparte una cuenta',
    texto: 'Lleva las finanzas del hogar o de pareja en un solo lugar',
    mostrarSi: (ctx) => ctx.cuentasCount > 0,
  },
]

export default function CarruselDescubrir({ gmailConectado, cuentasCount }) {
  const [indice, setIndice] = useState(0)
  const scrollRef = useRef(null)

  const tarjetas = TARJETAS_BASE.filter((t) => t.mostrarSi({ gmailConectado, cuentasCount }))

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    function onScroll() {
      const ancho = el.children[0]?.offsetWidth || 1
      const nuevoIndice = Math.round(el.scrollLeft / (ancho + 12))
      setIndice(nuevoIndice)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [tarjetas.length])

  if (tarjetas.length === 0) return null

  return (
    <div className="mt-4">
      <div ref={scrollRef} className="flex gap-3 overflow-x-auto no-scrollbar px-6 snap-x snap-mandatory">
        {tarjetas.map((t) => (
          <Link
            key={t.id}
            to={t.to}
            className="shrink-0 w-[calc(100%-24px)] snap-center rounded-2xl bg-accent-soft p-4 flex items-center gap-3"
          >
            <div className="w-11 h-11 rounded-full bg-paper-raised flex items-center justify-center shrink-0 pop-in">
              <t.icon size={18} className="text-accent" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-ink">{t.titulo}</p>
              <p className="text-xs text-ink-soft mt-0.5">{t.texto}</p>
            </div>
          </Link>
        ))}
      </div>

      {tarjetas.length > 1 && (
        <div className="flex items-center justify-center gap-1.5 mt-2.5">
          {tarjetas.map((t, i) => (
            <span
              key={t.id}
              className={`h-1.5 rounded-full transition-all ${
                i === indice ? 'w-5 bg-accent' : 'w-1.5 bg-line'
              }`}
            />
          ))}
        </div>
      )}
    </div>
  )
}
