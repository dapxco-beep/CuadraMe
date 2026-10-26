import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import {
  ArrowLeft, ArrowRight, CheckCircle2, Download, ExternalLink, ListChecks, Send, ShieldCheck, Smartphone,
} from 'lucide-react'
import { api } from '../lib/api'
import ClaveAtajo from '../components/ClaveAtajo'
import AtajoAvanzado from '../components/AtajoAvanzado'
import Icono from '../components/Icono'
import Cuadri from '../brand/Cuadri'
import { CapturaAutomatizacion, CapturaCierreApp, CapturaClave, CapturaPegarClave } from '../components/AtajoIlustraciones'
import {
  AndroidAccesoNotificaciones, AndroidDescarga, AndroidPegarClave, AndroidPermitirInstalar, AndroidProbar, FlujoAutomatico,
} from '../components/IlustracionesGuia'
import { useClaveAtajo } from '../lib/useClaveAtajo'
import { detectarDispositivo } from '../lib/primerUso'
import {
  explicarErrorPrueba, fechaLegible, guardarPaso, leerPaso, PASOS_TOTAL, SI_NO_LLEGA,
} from '../lib/atajoPrueba'

// Enlaces de iCloud de los dos atajos ya armados: la persona NO construye nada, solo los instala
// y, cuando iOS le pregunta «Pega tu clave de Cuádrame», pega la clave del paso 1.
//  - Pagos con Apple Pay (la automatización «Transacción» le entrega comercio, monto y tarjeta).
//  - Cierre de la app del banco (opcional: pregunta «¿Hiciste algún movimiento?»).
// Si un enlace cambia, quien ya instaló el atajo conserva su versión: hay que pegar el nuevo aquí.
export const ATAJO_ICLOUD_URL = 'https://www.icloud.com/shortcuts/8b2de178aff84465a938df4a5ef9c0dc'
export const ATAJO_CIERRE_URL = 'https://www.icloud.com/shortcuts/d34fa153ac844631baf36d8e158f7bf4'
// La app de Android («CuadraMe Captura») se descarga de aquí mismo, sin tiendas ni terceros.
export const APK_URL = '/descargas/cuadrame-captura.apk'

const INTERVALO_REVISION_MS = 6000

// Decisiones clave de esta pantalla:
//  - UN solo flujo, una cosa por pantalla: intro → paso 1 (clave) → 2 (instalar) → 3 (Wallet) → probar.
//  - Qué paso sigue se recuerda en el celular, así que se puede cerrar y retomar.
//  - «Ya funciona» NO lo marca la persona: se sabe porque el atajo real ya envió algo (último uso de
//    la clave, que viene de /conexiones/estado). La prueba del botón usa la sesión y no lo toca.
export default function ConectarDispositivo() {
  const volver = useVolver('/perfil')
  const claveAtajo = useClaveAtajo()
  const dispositivo = detectarDispositivo()
  const [plataforma, setPlataforma] = useState(dispositivo === 'android' ? 'android' : 'ios') // iPhone usa Atajos; Android usa la app Captura
  const [paso, setPasoEstado] = useState(() => leerPaso()) // -1 intro, 0..2 pasos, 3 probar
  const [ultimoUso, setUltimoUso] = useState(null)
  const [llegoAhora, setLlegoAhora] = useState(false) // llegó mientras mirabas esta pantalla
  const [verPasos, setVerPasos] = useState(false)
  const sabiaAlInicio = useRef(null)

  const irAPaso = useCallback((n) => {
    setPasoEstado(n)
    guardarPaso(n)
    window.scrollTo?.(0, 0)
  }, [])

  // Revisa si el atajo real ya envió algo. Silencioso si no se puede (sin conexión, sin sesión).
  const revisarUso = useCallback(async () => {
    try {
      const estado = await api.conexionesEstado?.()
      const uso = estado?.atajo?.ultimo_uso || null
      if (sabiaAlInicio.current === null) sabiaAlInicio.current = !!uso
      else if (uso && !sabiaAlInicio.current) setLlegoAhora(true)
      setUltimoUso(uso)
      return uso
    } catch {
      return null
    }
  }, [])

  useEffect(() => {
    revisarUso()
  }, [revisarUso])

  // Mientras espera el primer pago real (pasos 3 y prueba), sigue preguntando cada pocos segundos.
  useEffect(() => {
    if (ultimoUso || paso < 2) return undefined
    const t = setInterval(revisarUso, INTERVALO_REVISION_MS)
    return () => clearInterval(t)
  }, [ultimoUso, paso, revisarUso])

  const yaFunciona = !!ultimoUso && !verPasos

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <Icono icono={ArrowLeft} tam="md" />
        </button>
        <h1 className="text-xl font-bold leading-tight">Registro automático de tus pagos</h1>
      </header>

      {(plataforma === 'android' || paso < 0 || yaFunciona) && (
        <SelectorPlataforma valor={plataforma} onCambio={setPlataforma} />
      )}

      {plataforma === 'android' ? (
        <AndroidCaptura claveAtajo={claveAtajo} />
      ) : yaFunciona ? (
        <PantallaListo
          ultimoUso={ultimoUso}
          llegoAhora={llegoAhora}
          onRepasar={() => { setVerPasos(true); irAPaso(0) }}
        />
      ) : paso < 0 ? (
        <Intro
          dispositivo={dispositivo}
          onEmpezar={() => irAPaso(0)}
        />
      ) : paso < PASOS_TOTAL ? (
        <PasoDelFlujo
          paso={paso}
          claveAtajo={claveAtajo}
          onAtras={() => irAPaso(paso === 0 ? -1 : paso - 1)}
          onSiguiente={() => irAPaso(paso + 1)}
        />
      ) : (
        <Probar
          onAtras={() => irAPaso(PASOS_TOTAL - 1)}
          onResultado={revisarUso}
          ultimoUso={ultimoUso}
        />
      )}

      {plataforma === 'ios' && <AtajoAvanzado claveAtajo={claveAtajo} />}

      <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4 flex items-start gap-3" aria-label="Privacidad">
        <Icono icono={ShieldCheck} tam="md" className="text-accent mt-0.5" />
        <div>
          <p className="text-sm font-semibold">Qué datos viajan</p>
          <p className="text-xs text-ink-soft mt-1 leading-relaxed">
            {plataforma === 'android'
              ? 'La app solo lee los avisos de las apps de pago de la lista (Google Wallet, Nequi, Nu y tus bancos) y manda su texto a CuadraMe junto con tu clave personal. Nunca lee tus chats, correos ni redes, ni tu clave del banco. Todo viaja por conexión segura (HTTPS) y puedes cortar la conexión cuando quieras creando una clave nueva o quitando el permiso en Android.'
              : 'Solo el comercio, el monto, el nombre de la tarjeta, la fecha y la moneda de cada pago, junto con tu clave personal. Nunca el número completo de tu tarjeta, tu clave del banco ni tus otras apps. Todo viaja por conexión segura (HTTPS) y puedes cortar la conexión cuando quieras creando una clave nueva.'}
          </p>
        </div>
      </section>
    </div>
  )
}

/* ---------- Intro: qué es, en 2 frases, y para quién ---------- */

function Intro({ dispositivo, onEmpezar }) {
  const esIphone = dispositivo === 'ios'
  return (
    <section className="mx-6 mt-4" aria-label="Qué es el registro automático">
      <div className="rounded-2xl bg-paper-raised border border-line p-5 flex flex-col items-center text-center">
        <Cuadri pose="senalando" size={88} />
        <h2 className="text-lg font-bold mt-2">Cada vez que pagas con Apple Pay, CuadraMe lo anota solo.</h2>
        <p className="text-sm text-ink-soft mt-2 max-w-xs">
          Tú pagas como siempre y el movimiento aparece en la app para que lo confirmes con un toque.
        </p>
        <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-accent-soft text-accent text-xs font-semibold px-3 py-1.5">
          <Icono icono={Smartphone} tam="sm" /> Funciona en iPhone
        </span>
      </div>

      <div className="mt-4 rounded-2xl bg-paper-raised border border-line p-4" data-testid="como-funciona">
        <h3 className="text-sm font-bold mb-2">Así funciona</h3>
        <FlujoAutomatico />
        <dl className="mt-3 space-y-2 text-sm">
          <div>
            <dt className="font-semibold inline">Atajo: </dt>
            <dd className="inline text-ink-soft">una mini-receta de tu iPhone. La app «Atajos» ya viene instalada; tú solo la agregas con un toque.</dd>
          </div>
          <div>
            <dt className="font-semibold inline">Automatización: </dt>
            <dd className="inline text-ink-soft">lo que la pone a correr sola. Aquí: cada vez que pagas con Apple Pay. Tú no haces nada más.</dd>
          </div>
        </dl>
      </div>

      <button onClick={onEmpezar} className="btn btn-primario btn-bloque mt-4 inline-flex items-center justify-center gap-2">
        Empezar (menos de 2 minutos) <Icono icono={ArrowRight} tam="md" />
      </button>
      <p className="text-xs text-ink-soft text-center mt-2">
        {esIphone
          ? 'Son 3 pasos cortos, cada uno con su dibujo. Si no quieres, no pasa nada: puedes usar el correo o tus extractos.'
          : 'Estos pasos se hacen desde tu iPhone: puedes verlos aquí y repetirlos allá. También puedes traer tus movimientos por correo o extracto.'}
      </p>
      {!esIphone && (
        <Link to="/sincronizacion" className="btn btn-suave btn-bloque mt-3 inline-flex items-center justify-center gap-2" data-testid="otro-dispositivo">
          Traer mis movimientos por correo o extracto
        </Link>
      )}
    </section>
  )
}

/* ---------- Un paso por pantalla ---------- */

function Indicador({ paso }) {
  const n = paso + 1
  return (
    <div className="mx-6 mt-4">
      <p className="text-xs font-semibold text-ink-soft" aria-live="polite">Paso {n} de {PASOS_TOTAL}</p>
      <div
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={PASOS_TOTAL}
        aria-valuenow={n}
        aria-label={`Paso ${n} de ${PASOS_TOTAL}`}
        className="mt-1.5 h-1.5 rounded-full bg-line overflow-hidden"
      >
        <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${(n / PASOS_TOTAL) * 100}%` }} />
      </div>
    </div>
  )
}

function Navegacion({ onAtras, onSiguiente, siguiente = 'Siguiente', deshabilitado = false }) {
  return (
    <div className="mx-6 mt-5 flex gap-3">
      <button onClick={onAtras} className="btn btn-secundario inline-flex items-center justify-center gap-1.5 px-4" aria-label="Atrás">
        <Icono icono={ArrowLeft} tam="md" /> Atrás
      </button>
      <button
        onClick={onSiguiente}
        disabled={deshabilitado}
        className="btn btn-primario flex-1 inline-flex items-center justify-center gap-2 disabled:opacity-50"
      >
        {siguiente} <Icono icono={ArrowRight} tam="md" />
      </button>
    </div>
  )
}

function Tarjeta({ titulo, children, dibujo }) {
  return (
    <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-5" aria-labelledby="titulo-paso">
      <h2 id="titulo-paso" className="text-lg font-bold">{titulo}</h2>
      <div className="text-sm text-ink-soft mt-2 space-y-3">{children}</div>
      {dibujo && <div className="mt-4 max-w-[280px] mx-auto">{dibujo}</div>}
    </section>
  )
}

function PasoDelFlujo({ paso, claveAtajo, onAtras, onSiguiente }) {
  return (
    <>
      <Indicador paso={paso} />
      {paso === 0 && (
        <Tarjeta titulo="Copia tu clave" dibujo={<CapturaClave />}>
          <p>Es tu llave para que el atajo te reconozca. Cópiala ahora: la vas a pegar en el siguiente paso.</p>
          <ClaveAtajo {...claveAtajo} grande />
        </Tarjeta>
      )}
      {paso === 1 && (
        <Tarjeta titulo="Instala el atajo" dibujo={<CapturaPegarClave />}>
          <p>
            Toca el botón. Se abre la app <b>Atajos</b>. Cuando te lo pida, <b>pega la clave</b> (mantén presionado y
            elige Pegar) y toca <b>Agregar atajo</b>.
          </p>
          <a
            href={ATAJO_ICLOUD_URL}
            className="btn btn-primario btn-bloque inline-flex items-center justify-center gap-2"
          >
            <Icono icono={Download} tam="md" /> Instalar el atajo
          </a>
        </Tarjeta>
      )}
      {paso === 2 && <PasoWallet />}
      <Navegacion
        onAtras={onAtras}
        onSiguiente={onSiguiente}
        siguiente={paso === 2 ? 'Ya lo activé' : 'Siguiente'}
        deshabilitado={paso === 0 && claveAtajo.cargando}
      />
    </>
  )
}

function PasoWallet() {
  return (
    <Tarjeta titulo="Actívalo en Wallet" dibujo={<CapturaAutomatizacion />}>
      <p>Falta un último ajuste en tu iPhone para que el atajo corra solo cada vez que pagas:</p>
      <ol className="list-decimal pl-5 space-y-1.5" data-testid="pasos-wallet">
        <li>En <b>Atajos</b>, toca <b>Automatización</b> (abajo) y luego <b>+</b>.</li>
        <li>Elige <b>Transacción</b> y marca tus tarjetas de Wallet.</li>
        <li>Toca <b>Siguiente</b> → <b>Ejecutar atajo</b> → «CuadraMe Apple Pay».</li>
        <li>Marca <b>Ejecutar inmediatamente</b> para que no te pregunte.</li>
      </ol>
      <a href="shortcuts://" className="text-accent font-semibold text-sm inline-flex items-center gap-1 min-h-11">
        Abrir Atajos <Icono icono={ExternalLink} tam="sm" />
      </a>
      <details className="rounded-xl border border-line p-3" data-testid="opcional-efectivo">
        <summary className="text-sm font-semibold text-ink cursor-pointer min-h-6">
          <span className="text-xs font-bold uppercase text-accent mr-1.5">Opcional</span>
          Para registrar pagos en efectivo o en cuentas sin Apple Pay
        </summary>
        <div className="mt-2 space-y-3">
          <p>
            Este segundo atajo te pregunta «¿Hiciste algún movimiento?» cada vez que cierras la app de tu banco o de
            Nequi, y tú escribes el monto. Instálalo igual que el anterior y pega la misma clave.
          </p>
          <a
            href={ATAJO_CIERRE_URL}
            className="btn btn-suave btn-bloque inline-flex items-center justify-center gap-2"
          >
            <Icono icono={Download} tam="md" /> Instalar el atajo de efectivo y otras cuentas
          </a>
          <div className="max-w-[280px]"><CapturaCierreApp /></div>
          <ol className="list-decimal pl-5 space-y-1.5">
            <li>En <b>Automatización</b> toca <b>+</b> → <b>App</b>, elige la app de tu banco y marca <b>Se cierra</b> (desmarca «Se abre»).</li>
            <li>Toca <b>Siguiente</b> → <b>Ejecutar atajo</b> → «CuadraMe Cierre» y marca <b>Ejecutar inmediatamente</b>.</li>
            <li>Repite por cada app que quieras vigilar. Si un día no hiciste nada, toca «No».</li>
          </ol>
        </div>
      </details>
      <p className="text-xs">
        Tip: si tu tarjeta de Wallet se llama distinto a tu cuenta, ponle un «alias de tarjeta» a la cuenta (Perfil →
        Ver y editar mis cuentas) y los pagos caerán en la cuenta correcta.
      </p>
    </Tarjeta>
  )
}

/* ---------- Verificación en vivo ---------- */

function Probar({ onAtras, onResultado, ultimoUso }) {
  const [estado, setEstado] = useState('inicial') // inicial | enviando | ok | error
  const [error, setError] = useState(null)

  async function probar() {
    setEstado('enviando')
    setError(null)
    try {
      // Con la sesión (no con la clave): comprueba que CuadraMe te reconoce y tiene dónde anotar.
      const r = await api.pagoDePrueba(null)
      const lista = await api.movimientosPorConfirmar()
      if (!lista.some((m) => m.id === r.id)) {
        const e = new Error('no llegó')
        e.codigo = 'no-llego'
        throw e
      }
      window.dispatchEvent(new CustomEvent('cuadrame:movimientos-cambio'))
      await onResultado()
      setEstado('ok')
    } catch (err) {
      setError(explicarErrorPrueba(err))
      setEstado('error')
    }
  }

  return (
    <>
      <Indicador paso={PASOS_TOTAL - 1} />
      <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-5" aria-labelledby="titulo-prueba">
        <h2 id="titulo-prueba" className="text-lg font-bold">Comprobemos que funciona</h2>
        <p className="text-sm text-ink-soft mt-2">
          Enviamos un pago de $1.000 «de prueba». Aparecerá en la bandeja «¿son tuyos?» y puedes descartarlo.
        </p>
        <button
          onClick={probar}
          disabled={estado === 'enviando'}
          className="btn btn-primario btn-bloque mt-4 inline-flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <Icono icono={Send} tam="md" /> {estado === 'enviando' ? 'Probando...' : estado === 'inicial' ? 'Probar ahora' : 'Probar de nuevo'}
        </button>

        {estado === 'ok' && !ultimoUso && (
          <div role="status" data-testid="prueba-ok" className="mt-4 rounded-xl bg-cuadra-soft p-4 flex flex-col items-center text-center">
            <Cuadri pose="senalando" size={76} />
            <p className="text-sm font-bold mt-2">La prueba llegó a CuadraMe</p>
            <p className="text-sm text-ink-soft mt-1">
              Tu cuenta está lista. Falta solo que tu iPhone envíe un pago: haz una compra pequeña con Apple Pay y este
              paso se marcará solo cuando llegue.
            </p>
            <div className="mt-3 text-left w-full">
              <p className="text-xs font-semibold flex items-center gap-1.5">
                <Icono icono={ListChecks} tam="sm" /> Si pagas y no llega, revisa:
              </p>
              <ul className="list-disc pl-5 mt-1 space-y-1 text-xs text-ink-soft">
                {SI_NO_LLEGA.map((s) => <li key={s.id}>{s.texto}</li>)}
              </ul>
            </div>
          </div>
        )}

        {estado === 'error' && error && (
          <div role="alert" data-testid="prueba-error" className="mt-4 rounded-xl bg-danger-soft p-4 flex flex-col items-center text-center">
            <Cuadri pose="preocupado" size={76} />
            <p className="text-sm font-bold mt-2">{error.titulo}</p>
            <p className="text-sm text-ink-soft mt-1">{error.texto}</p>
            {error.accion && (
              <Link to={error.accion.a} className="btn btn-secundario mt-3 inline-flex items-center justify-center">
                {error.accion.texto}
              </Link>
            )}
          </div>
        )}
      </section>
      <div className="mx-6 mt-5 flex">
        <button onClick={onAtras} className="btn btn-secundario inline-flex items-center justify-center gap-1.5 px-4">
          <Icono icono={ArrowLeft} tam="md" /> Volver a los pasos
        </button>
      </div>
    </>
  )
}

/* ---------- Ya funciona ---------- */

function PantallaListo({ ultimoUso, llegoAhora, onRepasar }) {
  const cuando = fechaLegible(ultimoUso)
  return (
    <section className="mx-6 mt-4" aria-label="Registro automático activo">
      <div role="status" className="rounded-2xl bg-cuadra-soft p-5 flex flex-col items-center text-center" data-testid="listo">
        <Cuadri pose="celebrando" size={92} />
        <h2 className="text-lg font-bold mt-2 flex items-center gap-2">
          <Icono icono={CheckCircle2} tam="lg" className="text-cuadra" />
          {llegoAhora ? '¡Listo! Tu primer pago de prueba llegó' : '¡Listo! Tu registro automático funciona'}
        </h2>
        <p className="text-sm text-ink-soft mt-2 max-w-xs">
          Desde ahora, cada vez que pagas con Apple Pay, CuadraMe lo anota solo y tú lo confirmas con un toque.
        </p>
        {cuando && <p className="text-xs text-ink-soft mt-2">Último pago recibido: {cuando}</p>}
      </div>
      <button onClick={onRepasar} className="btn btn-fantasma btn-bloque mt-3">
        Ver los pasos otra vez
      </button>
    </section>
  )
}

/* ---------- Elegir iPhone o Android ---------- */

function SelectorPlataforma({ valor, onCambio }) {
  const opciones = [
    { id: 'ios', titulo: 'iPhone', detalle: 'Con Atajos' },
    { id: 'android', titulo: 'Android', detalle: 'Con la app CuadraMe Captura' },
  ]
  return (
    <div className="mx-6 mt-4" role="group" aria-label="Tu celular">
      <p className="text-xs font-semibold text-ink-soft mb-1.5">¿Qué celular tienes?</p>
      <div className="grid grid-cols-2 gap-2">
        {opciones.map((o) => (
          <button
            key={o.id}
            type="button"
            aria-pressed={valor === o.id}
            onClick={() => onCambio(o.id)}
            data-testid={`plataforma-${o.id}`}
            className={`rounded-2xl border p-3 text-left min-h-[64px] ${valor === o.id ? 'bg-accent-soft border-accent' : 'bg-paper-raised border-line'}`}
          >
            <span className="block text-sm font-bold">{o.titulo}</span>
            <span className="block text-xs text-ink-soft mt-0.5">{o.detalle}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ---------- Android: app «CuadraMe Captura» ---------- */

// ¿El servidor tiene de verdad el archivo? (si no, la página de inicio responde 200 con HTML y no sirve)
function useApkDisponible() {
  const [ok, setOk] = useState(null) // null = comprobando
  useEffect(() => {
    let activo = true
    fetch(APK_URL, { method: 'HEAD' })
      .then((r) => activo && setOk(r.ok && !(r.headers.get('content-type') || '').includes('text/html')))
      .catch(() => activo && setOk(false))
    return () => { activo = false }
  }, [])
  return ok
}

function PasoAndroid({ n, titulo, Dibujo, children }) {
  return (
    <li className="rounded-2xl bg-paper-raised border border-line p-4 flex items-start gap-4">
      <div className="w-[96px] shrink-0">
        <Dibujo />
      </div>
      <div className="min-w-0 flex-1">
        <span className="inline-flex w-7 h-7 rounded-full bg-accent text-paper-raised text-sm font-bold items-center justify-center" aria-hidden="true">{n}</span>
        <h3 className="text-base font-bold mt-1">
          <span className="sr-only">Paso {n}: </span>
          {titulo}
        </h3>
        <div className="text-sm text-ink-soft mt-1 space-y-2">{children}</div>
      </div>
    </li>
  )
}

function AndroidCaptura({ claveAtajo }) {
  const apk = useApkDisponible()
  return (
    <section className="mx-6 mt-4" aria-label="Registro automático en Android" data-testid="android-captura">
      <div className="rounded-2xl bg-paper-raised border border-line p-5 flex flex-col items-center text-center">
        <Cuadri pose="senalando" size={88} />
        <h2 className="text-lg font-bold mt-2">Cada vez que pagas con tu celular, CuadraMe lo anota solo.</h2>
        <p className="text-sm text-ink-soft mt-2 max-w-xs">
          Instalas una app pequeña, «CuadraMe Captura». Lee el aviso que te llega al pagar (Google Wallet, Nequi, Nu, tu banco) y lo manda a CuadraMe.
        </p>
      </div>

      <div className="mt-4 rounded-2xl bg-paper-raised border border-line p-4">
        <h3 className="text-sm font-bold mb-2">Así funciona</h3>
        <FlujoAutomatico />
      </div>

      <h2 className="text-lg font-bold mt-6 mb-3">Instálala en 5 pasos</h2>
      <ol className="space-y-3" aria-label="Pasos para Android">
        <PasoAndroid n={1} titulo="Descarga la app" Dibujo={AndroidDescarga}>
          <p>Toca el botón. Es un archivo pequeño (APK) de CuadraMe: no pasa por ninguna tienda ni tercero.</p>
          {apk === false ? (
            <p className="rounded-xl bg-accent-soft p-3 text-sm" data-testid="apk-pronto">
              Estamos terminando de publicar la app de Android. Mientras tanto, tus pagos igual llegan por correo o extracto.
            </p>
          ) : (
            <a href={APK_URL} download className="btn btn-primario btn-bloque inline-flex items-center justify-center gap-2" data-testid="descargar-apk">
              <Icono icono={Download} tam="md" /> Descargar CuadraMe Captura
            </a>
          )}
        </PasoAndroid>
        <PasoAndroid n={2} titulo="Permite instalarla" Dibujo={AndroidPermitirInstalar}>
          <p>Android avisará que la app viene de fuera de la tienda: es normal, la hicimos nosotros. Activa el permiso, vuelve atrás y toca <b>Instalar</b>.</p>
        </PasoAndroid>
        <PasoAndroid n={3} titulo="Copia tu clave" Dibujo={AndroidPegarClave}>
          <p>Es la llave para que la app te reconozca. Cópiala y pégala dentro de la app en «Tu clave de conexión».</p>
          <ClaveAtajo {...claveAtajo} grande android />
        </PasoAndroid>
        <PasoAndroid n={4} titulo="Dale acceso a los avisos" Dibujo={AndroidAccesoNotificaciones}>
          <p>En la app toca <b>Abrir ajustes de Android</b>, busca «CuadraMe Captura» y actívala. Solo tú puedes dar este permiso.</p>
        </PasoAndroid>
        <PasoAndroid n={5} titulo="Pruébala" Dibujo={AndroidProbar}>
          <p>En la app toca <b>Probar conexión</b> y luego <b>Enviar un pago de prueba</b>. Aparece en CuadraMe como «Por confirmar» y lo puedes descartar.</p>
          <Link to="/movimientos?filtro=por-revisar" className="text-accent font-semibold text-sm inline-flex items-center gap-1 min-h-11">
            Ver lo que está por confirmar <Icono icono={ArrowRight} tam="sm" />
          </Link>
        </PasoAndroid>
      </ol>

      <details className="mt-4 rounded-2xl bg-paper-raised border border-line p-4">
        <summary className="text-sm font-semibold cursor-pointer min-h-6">¿No me llegan los pagos?</summary>
        <ul className="list-disc pl-5 mt-2 space-y-1.5 text-sm text-ink-soft">
          <li>Revisa en la app que diga «Acceso a notificaciones activo».</li>
          <li>Algunos celulares (Xiaomi, Samsung, Huawei) cierran las apps en segundo plano: en Ajustes → Batería, pon «CuadraMe Captura» en «Sin restricciones».</li>
          <li>La app solo ve los avisos que el banco manda. Si Nequi o tu banco no muestran notificación al pagar, no hay nada que leer.</li>
          <li>Si cambias de celular, repite los pasos 1 a 4 con la misma clave.</li>
        </ul>
      </details>
    </section>
  )
}
