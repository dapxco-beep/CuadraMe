import { useState } from 'react'
import { Bell, Check, CreditCard, Download, Hand, Link2, ShieldCheck, Smartphone, Trash2 } from 'lucide-react'
import ClaveAtajo from './ClaveAtajo'
import Icono from './Icono'
import {
  CapturaAbrirDescarga, CapturaAgregarAtajo, CapturaAutomatizacion, CapturaDescargaSafari, CapturaGesto, CapturaNotificacion,
  CapturaPegarClave,
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
  'Hazlo desde tu iPhone, en Safari. Toca «Instalar» (botón de abajo): se descarga el atajo.',
  'Abre el archivo descargado (el botón de descargas de Safari, o la app Archivos › Descargas) y toca «Agregar atajo».',
  'Cuando pida tu clave, pégala (la copiaste arriba).',
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
          'Este atajo ya trae su automatización de Wallet: al agregarlo, si iOS pregunta si la activas, elige «Ejecutar inmediatamente». Si no la ves en «Automatización», créala así:',
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
    nombre: 'CuadraMe Registrar',
    icono: Bell,
    opcion: 'Mi banco me avisa (Nequi, Nu…)',
    paraQuien: 'Tu banco te avisa al pagar o recibir (Nequi, Nu…)',
    queHace: 'Lee el aviso que te manda el banco y lo registra. Es el mismo atajo del gesto: si ya instalaste «CuadraMe Registrar», no necesitas instalar otro.',
    url: ATAJO_NOTIFICACIONES_URL,
    nota: 'Necesita iOS 27. Cada banco necesita su propia automatización (iOS vigila una app por automatización), pero todas usan este mismo atajo, «CuadraMe Registrar».',
    fases: [
      { id: 'instalar', titulo: 'Instalar', pasos: INSTALAR },
      {
        id: 'activar',
        titulo: 'Activar (una vez por banco)',
        pasos: [
          'En Atajos abre «Automatización» y toca «+».',
          'Elige «Cuando recibo una notificación» y escoge la app de tu banco (por ejemplo Nequi). Toca «Siguiente».',
          'Elige «Ejecutar atajo» y escoge «CuadraMe Registrar».',
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
    nota: 'Casi nunca pregunta nada: reconoce solo el banco, el valor y a quién le enviaste. Si no sabe de qué banco es, lo guarda en la cuenta que más usas y te lo dice. Cuando lo mueves de cuenta o lo confirmas, aprende: la próxima vez reconoce esa pantalla solo.',
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

// Los tres momentos de instalar, dibujados como pantallas de iPhone (se desliza de lado si no caben).
function PasosInstalar() {
  const pasos = [
    { titulo: 'Descarga', texto: 'Toca «Instalar» y luego «Descargar».', dibujo: <CapturaDescargaSafari /> },
    { titulo: 'Ábrelo', texto: 'Botón de descargas de Safari › el archivo.', dibujo: <CapturaAbrirDescarga /> },
    { titulo: 'Agrégalo', texto: 'Pega tu clave y toca «Agregar atajo».', dibujo: <CapturaAgregarAtajo /> },
  ]
  return (
    <ol className="mt-3 flex gap-3 overflow-x-auto snap-x pb-2" data-testid="pasos-instalar-dibujos" aria-label="Los tres pasos para instalar">
      {pasos.map((p, i) => (
        <li key={p.titulo} className="snap-center shrink-0 w-[42%] min-w-[130px] max-w-[170px]">
          <figure>
            {p.dibujo}
            <figcaption className="mt-1.5 text-center">
              <span className="inline-flex w-5 h-5 rounded-full bg-accent text-paper-raised text-[11px] font-bold items-center justify-center">{i + 1}</span>
              <span className="block text-xs font-bold mt-0.5">{p.titulo}</span>
              <span className="block text-[11px] text-ink-soft leading-snug"><Resaltar texto={p.texto} /></span>
            </figcaption>
          </figure>
        </li>
      ))}
    </ol>
  )
}

// Desde el ícono instalado en la pantalla de inicio, iOS no deja descargar archivos: hay que usar Safari.
function esAppInstalada() {
  try {
    return window.navigator.standalone === true || window.matchMedia?.('(display-mode: standalone)').matches === true
  } catch {
    return false
  }
}

function AyudaSiNoAbre() {
  return (
    <>
      {esAppInstalada() && (
        <p role="alert" data-testid="aviso-app-instalada" className="mt-3 rounded-xl bg-accent-soft p-3 text-sm leading-relaxed">
          <b>Estás usando CuadraMe desde el ícono de tu pantalla de inicio.</b> Desde ahí iOS no deja descargar atajos: abre
          {' '}<b>cuadrame.dapx.shop</b> en <b>Safari</b>, entra a esta misma pantalla y toca «Instalar» allí.
        </p>
      )}
      <details className="mt-3 rounded-xl bg-paper p-3" data-testid="no-se-abre">
        <summary className="text-sm font-semibold cursor-pointer min-h-6">¿Tocaste «Instalar» y no pasó nada?</summary>
        <ul className="list-disc pl-5 mt-2 space-y-1.5 text-xs text-ink-soft leading-relaxed">
          <li>Safari no abre el atajo solo: descárgalo y luego toca el botón de descargas (la flecha en un círculo, junto a la barra de direcciones) y el archivo.</li>
          <li>También lo encuentras en la app Archivos › Descargas. Tócalo y elige «Atajos».</li>
          <li>Si usas CuadraMe desde el ícono de la pantalla de inicio, ábrelo en Safari: desde el ícono no se pueden descargar archivos.</li>
          <li>Si nada de eso funciona, escríbenos y te mandamos el atajo por otro medio.</li>
        </ul>
      </details>
    </>
  )
}

// Para quien abre la app en un computador: copia el enlace del atajo y lo abre luego en su iPhone (WhatsApp, notas, AirDrop...).
// Enlace oficial de Apple: abre la app Atajos y ella misma trae el archivo (sin pasar por la descarga de Safari).
function enlaceAtajos(a) {
  const archivo = new URL(a.url, window.location.origin).href
  return `shortcuts://import-shortcut?url=${encodeURIComponent(archivo)}&name=${encodeURIComponent(a.nombre)}`
}

function CopiarEnlace({ url }) {
  const [copiado, setCopiado] = useState(false)
  async function copiar() {
    const completo = new URL(url, window.location.origin).href
    try {
      await navigator.clipboard.writeText(completo)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2500)
    } catch {
      window.prompt('Copia este enlace y ábrelo en tu iPhone:', completo)
    }
  }
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={copiar}
        className="min-h-11 w-full inline-flex items-center justify-center gap-2 text-sm font-semibold text-accent"
      >
        <Icono icono={copiado ? Check : Link2} tam="sm" />
        {copiado ? 'Enlace copiado' : '¿Estás en un computador? Copia el enlace para abrirlo en tu iPhone'}
      </button>
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
              <>
                <a
                  href={enlaceAtajos(a)}
                  className="btn btn-primario btn-bloque mt-3 inline-flex items-center justify-center gap-2"
                  aria-label={`Instalar ${a.nombre}`}
                >
                  <Icono icono={Download} tam="md" /> Instalar
                </a>
                <a
                  href={a.url}
                  download
                  className="min-h-11 w-full inline-flex items-center justify-center gap-2 text-sm font-semibold text-accent"
                >
                  Si no abre Atajos, descarga el archivo
                </a>
                <CopiarEnlace url={a.url} />
                <AyudaSiNoAbre />
                <PasosInstalar />
              </>
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
        reconocen solo el banco y siempre te dicen qué pasó. «CuadraMe Notificaciones» y «CuadraMe Registrar» son ahora un solo atajo.
        Al instalar, pega tu clave otra vez y cambia el atajo en tus automatizaciones (abajo está explicado).
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

      <div className="mt-3 rounded-2xl bg-paper-raised border border-line p-4" data-testid="antes-de-empezar">
        <h3 className="text-sm font-bold">Antes de empezar</h3>
        <ul className="mt-2 space-y-2.5 text-sm text-ink-soft leading-relaxed">
          <li className="flex gap-3">
            <span className="shrink-0 text-accent mt-0.5" aria-hidden="true"><Icono icono={Smartphone} tam="md" /></span>
            <span>Necesitas un iPhone con <b className="text-ink">iOS 27</b>. Abre esta pantalla en Safari desde el propio iPhone.</span>
          </li>
          <li className="flex gap-3">
            <span className="shrink-0 text-accent mt-0.5" aria-hidden="true"><Icono icono={Trash2} tam="md" /></span>
            <span>
              Si ya tienes atajos «CuadraMe …» instalados, <b className="text-ink">bórralos primero</b> (en Atajos, mantén presionado y toca «Eliminar»).
              Los nuevos los reemplazan, y «CuadraMe Notificaciones» ahora es parte de «CuadraMe Registrar».
            </span>
          </li>
          <li className="flex gap-3">
            <span className="shrink-0 text-accent mt-0.5" aria-hidden="true"><Icono icono={ShieldCheck} tam="md" /></span>
            <span>La foto de tu comprobante <b className="text-ink">nunca sale del iPhone</b>: solo viaja el texto. Todo lo que se anota queda «por confirmar» hasta que lo revises.</span>
          </li>
        </ul>
      </div>

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
          <li>Elige arriba lo que quieres conectar y toca «Instalar». Abre el archivo descargado, toca «Agregar atajo» y pega tu clave otra vez.</li>
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
