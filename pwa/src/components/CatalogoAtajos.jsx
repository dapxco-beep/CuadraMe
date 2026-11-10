import { useState } from 'react'
import { Bell, CreditCard, Download, Hand } from 'lucide-react'
import ClaveAtajo from './ClaveAtajo'
import Icono from './Icono'
import {
  CapturaAutomatizacion, CapturaGesto, CapturaNotificacion, CapturaPegarClave,
} from './AtajoIlustraciones'
import { api } from '../lib/api'
import { CAPTURAS_REALES } from '../lib/capturasGuia'
import { haceCuanto } from '../lib/sincronizarGmail'
import {
  ATAJO_ICLOUD_URL, ATAJO_NOTIFICACIONES_URL, ATAJO_REGISTRAR_URL, ATAJOS_ACTUALIZADOS,
} from '../lib/atajosEnlaces'

// Los atajos de CuadraMe para iPhone como una guía corta: la persona elige QUÉ quiere conectar y ve solo los pasos de eso, en tres
// etapas (Instalar, Activar, Probar). Lo que registran queda siempre «por confirmar». El nombre debe coincidir con el del atajo compartido.
// En los pasos, lo que va entre « » es texto EXACTO de un botón de iOS y se resalta para encontrarlo rápido.
const INSTALAR = [
  'Toca «Instalar» (botón de abajo). Se abre la app Atajos.',
  'Toca «Agregar atajo». Cuando pida tu clave, pégala (la copiaste arriba).',
]

export const ATAJOS = [
  {
    id: 'apple-pay',
    nombre: 'CuadraMe Apple Pay',
    icono: CreditCard,
    opcion: 'Pagos con Apple Pay',
    paraQuien: 'Pagas con Apple Pay',
    queHace: 'Cada pago que haces con Apple Pay se anota solo, con el comercio, el valor y la tarjeta.',
    url: ATAJO_ICLOUD_URL,
    fases: [
      { id: 'instalar', titulo: 'Instalar', pasos: INSTALAR },
      {
        id: 'activar',
        titulo: 'Activar (una sola vez)',
        pasos: [
          'En Atajos abre «Automatización» y toca «+» (arriba a la derecha).',
          'Elige «Transacción», marca tus tarjetas de Wallet y toca «Siguiente».',
          'Elige «Ejecutar atajo» y escoge «CuadraMe Apple Pay».',
          'Activa «Ejecutar inmediatamente» y toca «Listo».',
        ],
      },
      { id: 'probar', titulo: 'Probar', pasos: ['Haz un pago pequeño con Apple Pay. Debe salir una notificación de CuadraMe y el movimiento queda «por confirmar».'] },
    ],
    dibujos: [<CapturaPegarClave key="a" />, <CapturaAutomatizacion key="b" />],
    leyendas: ['Al instalar, pega tu clave', 'Así queda la automatización'],
  },
  {
    id: 'notificaciones',
    nombre: 'CuadraMe Notificaciones',
    icono: Bell,
    opcion: 'Mi banco me avisa (Nequi, Nu…)',
    paraQuien: 'Tu banco te avisa al pagar o recibir (Nequi, Nu…)',
    queHace: 'Lee el aviso que te manda el banco y lo registra. Se instala una sola vez y sirve para todos tus bancos.',
    url: ATAJO_NOTIFICACIONES_URL,
    nota: 'Necesita iOS 27. Cada banco necesita su propia automatización (iOS vigila una app por automatización), pero todas usan este mismo atajo.',
    fases: [
      { id: 'instalar', titulo: 'Instalar', pasos: INSTALAR },
      {
        id: 'activar',
        titulo: 'Activar (una vez por banco)',
        pasos: [
          'En Atajos abre «Automatización» y toca «+».',
          'Elige «Cuando recibo una notificación» y escoge la app de tu banco (por ejemplo Nequi). Toca «Siguiente».',
          'Elige «Ejecutar atajo» y escoge «CuadraMe Notificaciones».',
          'Activa «Ejecutar inmediatamente» y toca «Listo». Repite con cada banco que te avise.',
        ],
      },
      { id: 'probar', titulo: 'Probar', pasos: ['Haz un pago pequeño, o pídele a alguien que te envíe $1. Debe salir una notificación de CuadraMe y el movimiento queda «por confirmar».'] },
    ],
    dibujos: [<CapturaNotificacion key="a" />],
    leyendas: ['Así queda la automatización de tu banco'],
  },
  {
    id: 'registrar',
    nombre: 'CuadraMe Registrar',
    icono: Hand,
    opcion: 'Mi banco no avisa al enviar (Nu…)',
    paraQuien: 'Tu banco NO avisa al enviar plata (Nu…)',
    queHace: 'Con un gesto lee el comprobante que tienes en pantalla y lo registra. La foto no sale de tu iPhone: solo viaja el texto.',
    url: ATAJO_REGISTRAR_URL,
    nota: 'Casi nunca pregunta nada: reconoce solo el banco, el valor y a quién le enviaste. Si no sabe de qué banco es, lo guarda en la cuenta más probable, te lo dice y te pregunta «¿De qué cuenta es?» con tus cuentas registradas: si eliges otra, la pasa y aprende, y la próxima vez reconoce esa pantalla solo.',
    fases: [
      { id: 'instalar', titulo: 'Instalar', pasos: INSTALAR },
      {
        id: 'activar',
        titulo: 'Elegir tu gesto (una sola vez)',
        pasos: [
          'Abre Ajustes › Accesibilidad › Tocar › «Tocar atrás».',
          'Toca «Doble toque» y, al final de la lista, en «Atajos», escoge «CuadraMe Registrar».',
          'Alternativas: el Botón de acción (iPhone 15 Pro o más nuevo) o decir «Oye Siri, CuadraMe Registrar».',
        ],
      },
      {
        id: 'probar',
        titulo: 'Probar',
        pasos: [
          'Envía tu plata en el banco y deja abierto el comprobante.',
          'Toca dos veces la parte de atrás del iPhone. En unos segundos sale una notificación de CuadraMe y el movimiento queda «por confirmar».',
        ],
      },
    ],
    dibujos: [<CapturaGesto key="a" />],
    leyendas: ['Así eliges tu gesto en Ajustes'],
  },
]

// Lo que va entre « » es texto exacto de un botón de iOS: se resalta.
function Resaltar({ texto }) {
  return texto.split(/(«[^»]*»)/).map((trozo, i) =>
    trozo.startsWith('«') ? <b key={i} className="text-ink">{trozo}</b> : <span key={i}>{trozo}</span>
  )
}

// Una captura REAL si la hay para este atajo y este dibujo; si no, el dibujo propio.
function Imagen({ id, indice, dibujo, leyenda }) {
  const real = (CAPTURAS_REALES[id] || [])[indice]
  return (
    <figure className="mt-3">
      {real ? (
        <img src={real.src} alt={real.alt} loading="lazy" className="w-full max-w-xs mx-auto rounded-xl border border-line" />
      ) : (
        dibujo
      )}
      <figcaption className="text-[11px] text-ink-soft text-center mt-1">{leyenda}</figcaption>
    </figure>
  )
}

// «¿Ya llegó?»: el servidor anota cada vez que un atajo se conecta. Si fue hace poco, la prueba funcionó.
function ComprobarLlegada() {
  const [estado, setEstado] = useState(null)

  async function comprobar() {
    setEstado({ tipo: 'cargando' })
    try {
      const r = await api.conexionesEstado()
      const uso = r?.atajo?.ultimo_uso || null
      const t = uso ? Date.parse(/(Z|[+-]\d\d:?\d\d)$/.test(uso) ? uso : `${uso}Z`) : NaN
      const minutos = Number.isNaN(t) ? Infinity : (Date.now() - t) / 60000
      if (minutos <= 10) {
        setEstado({ tipo: 'llego', texto: `¡Llegó! Tu atajo se conectó ${haceCuanto(uso)}. Mira «Por confirmar» en Movimientos.` })
      } else {
        setEstado({
          tipo: 'nada',
          texto: `${uso ? `La última conexión fue ${haceCuanto(uso)}. ` : 'Todavía no llega nada. '}Haz la prueba y toca «Comprobar» otra vez. Si sigue igual, mira «¿No funciona?» más abajo.`,
        })
      }
    } catch {
      setEstado({ tipo: 'error', texto: 'No pude comprobarlo ahora. Revisa tu conexión e inténtalo otra vez.' })
    }
  }

  return (
    <div className="mt-3" data-testid="comprobar-llegada">
      <button
        onClick={comprobar}
        disabled={estado?.tipo === 'cargando'}
        className="btn btn-suave btn-bloque inline-flex items-center justify-center gap-2 disabled:opacity-60"
      >
        {estado?.tipo === 'cargando' ? 'Comprobando…' : 'Comprobar si llegó'}
      </button>
      {estado?.texto && (
        <p
          role="status"
          data-resultado={estado.tipo}
          className={`text-sm mt-2 rounded-xl p-3 leading-relaxed ${estado.tipo === 'llego' ? 'bg-cuadra-soft font-semibold' : 'bg-paper text-ink-soft'}`}
        >
          <Resaltar texto={estado.texto} />
        </p>
      )}
    </div>
  )
}

function Fase({ n, fase, children }) {
  return (
    <section className="mt-4" aria-label={`${n}. ${fase.titulo}`} data-testid={`fase-${fase.id}`}>
      <h4 className="flex items-center gap-2 text-sm font-bold">
        <span
          className="shrink-0 w-6 h-6 rounded-full bg-accent text-paper-raised text-xs font-bold flex items-center justify-center"
          aria-hidden="true"
        >
          {n}
        </span>
        {fase.titulo}
      </h4>
      <ol className="list-decimal pl-11 mt-2 space-y-1.5 text-sm text-ink-soft leading-relaxed">
        {fase.pasos.map((p) => (
          <li key={p}><Resaltar texto={p} /></li>
        ))}
      </ol>
      {children}
    </section>
  )
}

function GuiaAtajo({ a }) {
  return (
    <article className="mt-3 rounded-2xl bg-paper-raised border border-line p-4" data-testid={`atajo-${a.id}`} aria-label={a.nombre}>
      <div className="flex items-start gap-3">
        <span className="shrink-0 w-10 h-10 rounded-xl bg-accent-soft text-accent flex items-center justify-center" aria-hidden="true">
          <Icono icono={a.icono} tam="md" />
        </span>
        <div className="min-w-0">
          <h3 className="text-[15px] font-bold leading-tight">{a.nombre}</h3>
          <p className="text-xs font-semibold text-accent mt-0.5">Para ti si: {a.paraQuien}</p>
        </div>
      </div>
      <p className="text-sm text-ink-soft mt-2 leading-relaxed">{a.queHace}</p>

      <div data-testid={`pasos-${a.id}`}>
        {a.fases.map((fase, i) => (
          <Fase key={fase.id} n={i + 1} fase={fase}>
            {fase.id === 'instalar' && (
              <a
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-primario btn-bloque mt-3 inline-flex items-center justify-center gap-2"
                aria-label={`Instalar ${a.nombre}`}
              >
                <Icono icono={Download} tam="md" /> Instalar
              </a>
            )}
            {fase.id === 'activar' &&
              a.dibujos.map((d, j) => <Imagen key={a.leyendas[j]} id={a.id} indice={j} dibujo={d} leyenda={a.leyendas[j]} />)}
            {fase.id === 'probar' && <ComprobarLlegada />}
          </Fase>
        ))}
      </div>
      {a.nota && <p className="text-xs text-ink-soft mt-4 rounded-xl bg-paper p-3 leading-relaxed">{a.nota}</p>}
    </article>
  )
}

const CLAVE_AVISO = 'cuadrame:atajos-aviso'
const CLAVE_ELEGIDO = 'cuadrame:atajo-elegido'

function leerElegido() {
  try {
    const id = localStorage.getItem(CLAVE_ELEGIDO)
    return ATAJOS.some((a) => a.id === id) ? id : null
  } catch {
    return null
  }
}

// «Actualizamos los atajos»: iOS no los actualiza solo y la app no sabe qué versión tiene cada persona, así que se avisa a todos
// hasta que cada quien lo cierre. Vuelve a salir cuando cambia ATAJOS_ACTUALIZADOS.version.
function AvisoActualizados() {
  const [visto, setVisto] = useState(() => {
    try {
      return localStorage.getItem(CLAVE_AVISO) === ATAJOS_ACTUALIZADOS.version
    } catch {
      return false
    }
  })
  if (visto) return null
  function cerrar() {
    setVisto(true)
    try {
      localStorage.setItem(CLAVE_AVISO, ATAJOS_ACTUALIZADOS.version)
    } catch {
      /* sin almacenamiento el aviso reaparece la próxima vez: no pasa nada */
    }
  }
  return (
    <div role="status" className="mt-3 rounded-2xl bg-accent-soft p-4" data-testid="aviso-atajos-actualizados">
      <p className="text-sm font-bold">Actualizamos los atajos ({ATAJOS_ACTUALIZADOS.fecha})</p>
      <p className="text-sm mt-1 leading-relaxed">
        Si los instalaste antes de esa fecha, vuelve a tocar «Instalar» en cada uno para tener la versión nueva: ahora casi no preguntan,
        reconocen solo el banco y siempre te dicen qué pasó. Los anteriores siguen funcionando, pero sin esas mejoras. Al instalar, pega
        tu clave otra vez y cambia el atajo en tus automatizaciones (abajo está explicado).
      </p>
      <button onClick={cerrar} className="mt-2 min-h-11 text-sm font-semibold underline">
        Entendido
      </button>
    </div>
  )
}

export default function CatalogoAtajos({ claveAtajo }) {
  const [elegido, setElegido] = useState(leerElegido)
  const atajo = ATAJOS.find((a) => a.id === elegido) || null

  function elegir(id) {
    setElegido(id)
    try {
      localStorage.setItem(CLAVE_ELEGIDO, id)
    } catch {
      /* sin almacenamiento la elección dura mientras la pantalla esté abierta */
    }
  }

  return (
    <section className="mx-6 mt-6" aria-label="Todos los atajos de CuadraMe" data-testid="catalogo-atajos">
      <h2 className="text-lg font-bold">Conecta tu iPhone</h2>
      <p className="text-sm text-ink-soft mt-1 leading-relaxed">
        Tus pagos se anotan solos. Se instala una vez y sirve para todos tus bancos. Lo que registra queda «por confirmar» hasta que lo revises.
      </p>
      <AvisoActualizados />

      <div className="mt-3 rounded-2xl bg-paper-raised border border-line p-4" data-testid="clave-catalogo">
        <h3 className="text-sm font-bold">Primero: copia tu clave</h3>
        <p className="text-xs text-ink-soft mt-1 mb-2">Cada atajo te la pide al instalarlo.</p>
        <ClaveAtajo {...claveAtajo} />
      </div>

      <div className="mt-3 rounded-2xl bg-paper-raised border border-line p-4" data-testid="cual-instalo">
        <h3 className="text-sm font-bold">Luego: ¿qué quieres conectar?</h3>
        <div role="group" aria-label="Qué quieres conectar" className="mt-2 grid gap-2">
          {ATAJOS.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => elegir(a.id)}
              aria-pressed={elegido === a.id}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left min-h-11 ${
                elegido === a.id ? 'border-accent bg-paper' : 'border-line'
              }`}
            >
              <span className="shrink-0 w-9 h-9 rounded-lg bg-accent-soft text-accent flex items-center justify-center" aria-hidden="true">
                <Icono icono={a.icono} tam="md" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold">{a.opcion}</span>
                <span className="block text-xs text-ink-soft">{a.nombre}</span>
              </span>
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-soft mt-2">Puedes conectar varios: no se estorban.</p>
      </div>

      {atajo ? (
        <GuiaAtajo a={atajo} />
      ) : (
        <p className="text-sm text-ink-soft mt-3 text-center" data-testid="elige-una-opcion">Elige una opción y te muestro los pasos.</p>
      )}

      <details className="mt-4 rounded-2xl bg-paper-raised border border-line p-4" data-testid="ya-lo-tenias">
        <summary className="text-sm font-bold cursor-pointer min-h-6">¿Ya tenías un atajo instalado?</summary>
        <p className="text-sm text-ink-soft mt-2 leading-relaxed">
          iOS no actualiza los atajos solo. Si instalaste uno hace tiempo, conviene cambiarlo por el nuevo: casi no pregunta,
          reconoce solo el banco y siempre te dice qué pasó. Los anteriores siguen funcionando, pero sin esas mejoras.
        </p>
        <ol className="list-decimal pl-5 mt-2 space-y-2 text-sm text-ink-soft leading-relaxed">
          <li>Elige arriba lo que quieres conectar y toca «Instalar». Luego «Agregar atajo», y pega tu clave otra vez.</li>
          <li>Si iOS lo agrega con un «2» al final, ese es el nuevo: en la app Atajos mantén presionado el viejo y toca «Eliminar».</li>
          <li>Abre «Automatización» y, en cada automatización que usaba el viejo, cambia «Ejecutar atajo» al nuevo.</li>
        </ol>
      </details>

      <details className="mt-3 rounded-2xl bg-paper-raised border border-line p-4" data-testid="no-funciona">
        <summary className="text-sm font-bold cursor-pointer min-h-6">¿No funciona? Revisa esto</summary>
        <ul className="list-disc pl-5 mt-2 space-y-2 text-sm text-ink-soft leading-relaxed">
          <li><b className="text-ink">Pruébalo sin gesto:</b> en la app Atajos toca el botón de reproducir (el triángulo) del atajo. Debe salir una notificación de CuadraMe. Con «CuadraMe Registrar», abre antes un comprobante.</li>
          <li><b className="text-ink">Dice «clave no válida»:</b> copia tu clave aquí arriba y pégala en el primer cuadro de texto del atajo (en Atajos, toca el atajo y busca la primera acción «Texto»).</li>
          <li><b className="text-ink">La automatización no corre:</b> en Atajos › Automatización debe estar activada y con «Ejecutar inmediatamente». Los atajos instalados por enlace suelen traerla apagada.</li>
          <li><b className="text-ink">El gesto no hace nada:</b> en Ajustes › Accesibilidad › Tocar › Tocar atrás revisa que el «Doble toque» tenga «CuadraMe Registrar».</li>
          <li><b className="text-ink">No llegan los avisos del banco:</b> la app del banco debe tener las notificaciones activadas en los Ajustes de iOS, y esta función necesita iOS 27.</li>
          <li><b className="text-ink">Dice «No encontré un pago»:</b> deja el comprobante completo en pantalla antes de hacer el gesto.</li>
        </ul>
        <p className="text-xs text-ink-soft mt-3 leading-relaxed">
          Para ver si CuadraMe está recibiendo avisos, mira la tarjeta «Registro automático desde el banco» en Conexiones: dice cuándo llegó el último de cada banco.
        </p>
      </details>
    </section>
  )
}
