import { Bell, CreditCard, Download, Hand } from 'lucide-react'
import ClaveAtajo from './ClaveAtajo'
import Icono from './Icono'
import {
  CapturaAutomatizacion, CapturaGesto, CapturaNotificacion, CapturaPegarClave,
} from './AtajoIlustraciones'
import { CAPTURAS_REALES } from '../lib/capturasGuia'
import {
  ATAJO_ICLOUD_URL, ATAJO_NOTIFICACIONES_URL, ATAJO_REGISTRAR_URL,
} from '../lib/atajosEnlaces'

// Los atajos de CuadraMe para iPhone en un solo lugar: qué hace cada uno, para qué banco sirve, el botón para instalarlo
// y sus pasos. Lo que registran queda siempre «por confirmar». El nombre debe coincidir con el del atajo compartido.
export const ATAJOS = [
  {
    id: 'apple-pay',
    nombre: 'CuadraMe Apple Pay',
    icono: CreditCard,
    paraQuien: 'Pagas con Apple Pay',
    queHace: 'Cada pago que haces con Apple Pay se anota solo, con el comercio, el valor y la tarjeta.',
    url: ATAJO_ICLOUD_URL,
    pasos: [
      'Toca «Instalar», luego «Agregar atajo» y pega tu clave de CuadraMe (cópiala arriba, en «Tu clave»).',
      'Abre la app Atajos, ve a «Automatización» y toca + (arriba a la derecha). Elige «Transacción».',
      'Marca tus tarjetas de Wallet, toca «Siguiente», elige «Ejecutar atajo» y escoge «CuadraMe Apple Pay».',
      'Activa «Ejecutar inmediatamente» y toca «Listo». Haz un pago pequeño: aparece «por confirmar» en CuadraMe.',
    ],
    dibujos: [<CapturaPegarClave key="a" />, <CapturaAutomatizacion key="b" />],
    leyendas: ['Al instalar, pega tu clave', 'Así queda la automatización'],
  },
  {
    id: 'notificaciones',
    nombre: 'CuadraMe Notificaciones',
    icono: Bell,
    paraQuien: 'Tu banco te avisa al pagar o recibir (Nequi, Nu…)',
    queHace: 'Lee el aviso que te manda el banco y lo registra. Se instala una sola vez y sirve para todos tus bancos.',
    url: ATAJO_NOTIFICACIONES_URL,
    nota: 'Necesita iOS 27. Cada banco necesita su propia automatización (iOS vigila una app por automatización), pero todas usan este mismo atajo.',
    pasos: [
      'Toca «Instalar», luego «Agregar atajo» y pega tu clave de CuadraMe.',
      'En la app Atajos ve a «Automatización», toca + y elige «Cuando recibo una notificación».',
      'Elige la app de tu banco (por ejemplo Nequi), toca «Siguiente», elige «Ejecutar atajo» y escoge «CuadraMe Notificaciones».',
      'Activa «Ejecutar inmediatamente». Repite los pasos 2 y 3 con cada banco que te avise.',
    ],
    dibujos: [<CapturaNotificacion key="a" />],
    leyendas: ['Así queda la automatización de tu banco'],
  },
  {
    id: 'registrar',
    nombre: 'CuadraMe Registrar',
    icono: Hand,
    paraQuien: 'Tu banco NO avisa al enviar plata (Nu…)',
    queHace: 'Con un gesto lee el comprobante que tienes en pantalla y lo registra. La foto no sale de tu iPhone: solo viaja el texto.',
    url: ATAJO_REGISTRAR_URL,
    nota: 'Casi nunca pregunta nada: reconoce solo el banco, el valor y a quién le enviaste. Solo pregunta si no está seguro, y aprende.',
    pasos: [
      'Toca «Instalar», luego «Agregar atajo» y pega tu clave de CuadraMe.',
      'Elige tu gesto. El más fácil: Ajustes › Accesibilidad › Tocar › Tocar atrás › «Doble toque» › «CuadraMe Registrar». También sirve el Botón de acción (iPhone 15 Pro o más nuevo) o decir «Oye Siri, CuadraMe Registrar».',
      'Envía tu plata en el banco y deja abierto el comprobante.',
      'Haz tu gesto (por ejemplo, toca dos veces la parte de atrás del iPhone). En unos segundos aparece «por confirmar» en CuadraMe.',
    ],
    dibujos: [<CapturaGesto key="a" />],
    leyendas: ['Así eliges tu gesto en Ajustes'],
  },
]

// Una captura REAL si la hay para este atajo y este paso; si no, el dibujo propio.
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

function TarjetaAtajo({ a }) {
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
      <a
        href={a.url}
        target="_blank"
        rel="noopener noreferrer"
        className="btn btn-primario btn-bloque mt-3 inline-flex items-center justify-center gap-2"
        aria-label={`Instalar ${a.nombre}`}
      >
        <Icono icono={Download} tam="md" /> Instalar
      </a>
      <details className="mt-3" data-testid={`pasos-${a.id}`}>
        <summary className="text-sm font-semibold cursor-pointer min-h-6">Paso a paso</summary>
        <ol className="list-decimal pl-5 mt-2 space-y-2 text-sm text-ink-soft leading-relaxed">
          {a.pasos.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ol>
        {a.dibujos.map((d, i) => (
          <Imagen key={a.leyendas[i]} id={a.id} indice={i} dibujo={d} leyenda={a.leyendas[i]} />
        ))}
        {a.nota && <p className="text-xs text-ink-soft mt-3 rounded-xl bg-paper p-3 leading-relaxed">{a.nota}</p>}
      </details>
    </article>
  )
}

export default function CatalogoAtajos({ claveAtajo }) {
  return (
    <section className="mx-6 mt-6" aria-label="Todos los atajos de CuadraMe" data-testid="catalogo-atajos">
      <h2 className="text-lg font-bold">Atajos de CuadraMe para tu iPhone</h2>
      <p className="text-sm text-ink-soft mt-1 leading-relaxed">
        Se instalan una vez y sirven para todos tus bancos. Lo que registran queda «por confirmar».
      </p>

      <div className="mt-3 rounded-2xl bg-paper-raised border border-line p-4" data-testid="cual-instalo">
        <h3 className="text-sm font-bold">¿Cuál instalo?</h3>
        <ul className="mt-2 space-y-1.5 text-sm text-ink-soft leading-relaxed">
          <li><b className="text-ink">Pagas con Apple Pay</b> → CuadraMe Apple Pay</li>
          <li><b className="text-ink">Tu banco te avisa</b> cuando pagas o recibes → CuadraMe Notificaciones</li>
          <li><b className="text-ink">Tu banco no avisa</b> al enviar plata (Nu) → CuadraMe Registrar</li>
        </ul>
        <p className="text-xs text-ink-soft mt-2">Puedes instalar varios: no se estorban.</p>
      </div>

      <div className="mt-3 rounded-2xl bg-paper-raised border border-line p-4" data-testid="clave-catalogo">
        <h3 className="text-sm font-bold">Tu clave de conexión</h3>
        <p className="text-xs text-ink-soft mt-1 mb-2">Cada atajo te la pide al instalar. Cópiala aquí.</p>
        <ClaveAtajo {...claveAtajo} />
      </div>

      {ATAJOS.map((a) => (
        <TarjetaAtajo key={a.id} a={a} />
      ))}

      <details className="mt-4 rounded-2xl bg-paper-raised border border-line p-4" data-testid="ya-lo-tenias">
        <summary className="text-sm font-bold cursor-pointer min-h-6">¿Ya tenías un atajo instalado?</summary>
        <p className="text-sm text-ink-soft mt-2 leading-relaxed">
          iOS no actualiza los atajos solo. Si instalaste uno hace tiempo, conviene cambiarlo por el nuevo: casi no pregunta,
          reconoce solo el banco y siempre te dice qué pasó. Los anteriores siguen funcionando, pero sin esas mejoras.
        </p>
        <ol className="list-decimal pl-5 mt-2 space-y-2 text-sm text-ink-soft leading-relaxed">
          <li>Toca «Instalar» en el atajo de arriba y luego «Agregar atajo». Pega tu clave otra vez.</li>
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
