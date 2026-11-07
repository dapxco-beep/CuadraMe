import { useState } from 'react'
import { Check, Hand, Smartphone } from 'lucide-react'

// «Cuando el banco no avisa» (Nu al enviar plata, por ejemplo): un gesto del iPhone toma un pantallazo del comprobante,
// el teléfono saca el texto y manda SOLO el texto a CuadraMe. El gesto lo elige cada persona en los Ajustes de su iPhone
// (CuadraMe no puede ponerlo por ella), por eso esta guía: eliges uno y ves solo los pasos de ese.
// Solo gestos que se hacen SIN salir del comprobante (Centro de control o widgets lo taparían en el pantallazo).
export const GESTOS = [
  {
    id: 'atras',
    titulo: 'Tocar atrás del iPhone',
    nota: 'La más fácil · iPhone 8 o más nuevo',
    recomendado: true,
    pasos: [
      'Abre Ajustes > Accesibilidad > Tocar > Tocar atrás.',
      'Elige «Doble toque» (o «Triple toque»).',
      'Baja hasta la sección «Atajos» y escoge «CuadraMe Registrar».',
    ],
    uso: 'Con el comprobante abierto, toca dos veces la parte de atrás del iPhone.',
  },
  {
    id: 'boton',
    titulo: 'Botón de acción',
    nota: 'iPhone 15 Pro o más nuevo',
    pasos: [
      'Abre Ajustes > Botón de acción.',
      'Desliza hasta «Atajo» y toca «Elegir un atajo».',
      'Escoge «CuadraMe Registrar».',
    ],
    uso: 'Con el comprobante abierto, mantén presionado el botón de acción.',
  },
  {
    id: 'siri',
    titulo: 'Decirle a Siri',
    nota: 'Cualquier iPhone con Siri',
    pasos: ['No hay que configurar nada: Siri reconoce el nombre del atajo.'],
    uso: 'Con el comprobante abierto, di «Oye Siri, CuadraMe Registrar».',
  },
]

const LLAVE = 'cuadrame:gesto-registro'

function gestoGuardado() {
  try {
    const id = localStorage.getItem(LLAVE)
    return GESTOS.some((g) => g.id === id) ? id : 'atras'
  } catch {
    return 'atras'
  }
}

export default function TarjetaGestoRegistro({ url }) {
  const [id, setId] = useState(gestoGuardado)
  const gesto = GESTOS.find((g) => g.id === id) || GESTOS[0]

  function elegir(nuevo) {
    setId(nuevo)
    try {
      localStorage.setItem(LLAVE, nuevo)
    } catch {
      /* sin almacenamiento la elección solo dura mientras la pantalla esté abierta */
    }
  }

  return (
    <section
      className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4"
      data-testid="tarjeta-gesto-registro"
      aria-label="Cuando el banco no avisa"
    >
      <div className="flex items-center gap-3">
        <Hand size={20} className="text-accent shrink-0" />
        <h2 className="text-[15px] font-semibold flex-1">Cuando el banco no avisa (Nu y otros)</h2>
      </div>
      <p className="text-xs text-ink-soft mt-2 leading-relaxed">
        Algunos bancos no mandan aviso al enviar plata. Con un gesto, CuadraMe lee el comprobante que tienes en pantalla y lo
        registra. La foto no sale de tu iPhone: solo se envía el texto.
      </p>

      <ol className="mt-3 space-y-3 text-sm">
        <li>
          <p className="font-semibold">1. Instala el atajo</p>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1.5 rounded-xl py-2.5 px-3 text-sm font-semibold bg-accent text-paper-raised mt-2"
          >
            <Smartphone size={16} /> Instalar «CuadraMe Registrar»
          </a>
          <p className="text-xs text-ink-soft mt-1.5">Pulsa «Agregar atajo» y pega tu clave de CuadraMe cuando la pida.</p>
        </li>
        <li>
          <p className="font-semibold">2. Elige cómo quieres activarlo</p>
          <div role="group" aria-label="Gesto para activar el atajo" className="mt-2 grid gap-2">
            {GESTOS.map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => elegir(g.id)}
                aria-pressed={id === g.id}
                className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-left ${
                  id === g.id ? 'border-accent bg-paper' : 'border-line'
                }`}
              >
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">
                    {g.titulo}
                    {g.recomendado && <span className="ml-2 text-[11px] font-semibold text-cuadra">Recomendado</span>}
                  </span>
                  <span className="block text-xs text-ink-soft">{g.nota}</span>
                </span>
                {id === g.id && <Check size={20} className="text-accent shrink-0" aria-hidden="true" />}
              </button>
            ))}
          </div>
          <ol className="list-decimal pl-5 mt-3 space-y-1 text-xs text-ink-soft leading-relaxed" data-testid="pasos-gesto">
            {gesto.pasos.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ol>
        </li>
        <li>
          <p className="font-semibold">3. Úsalo</p>
          <p className="text-xs text-ink-soft mt-1 leading-relaxed" data-testid="uso-gesto">
            {gesto.uso} CuadraMe reconoce solo el banco, el valor y a quién le enviaste, y deja el movimiento «por confirmar».
            Solo te pregunta si no está seguro de algo, y aprende para no volver a preguntar.
          </p>
        </li>
      </ol>
    </section>
  )
}
