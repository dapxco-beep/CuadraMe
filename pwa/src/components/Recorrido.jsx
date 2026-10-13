import { createPortal } from 'react-dom'
import { useEffect, useId, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { m, useReducedMotion } from 'framer-motion'
import { ArrowLeft, ArrowRight, ChevronDown, Sparkles, X } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import {
  acotar, guardarRecorrido, PASOS_RECORRIDO, porcentajeRecorrido, TOTAL_PASOS,
} from '../lib/recorrido'
import BarraProgreso from './BarraProgreso'
import Icono from './Icono'
import IlustracionRecorrido from './IlustracionesRecorrido'
import Cuadri from '../brand/Cuadri'
import { conNombre, FRASES, POSE_RECORRIDO, useMostrarCuadri } from '../lib/cuadri'
import { useNombreParaSaludar } from '../lib/nombre'
import { Boton } from './ui'

const FOCUSABLES = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'

/**
 * Recorrido guiado a pantalla completa: una tarjeta por área (ilustración + 1–2 frases) que se
 * desliza con el dedo, las flechas del teclado o los botones. «Probar ahora» lleva a esa pantalla
 * y deja guardado el paso para retomarlo luego desde Perfil o Ayuda.
 *
 *  - Teclado: ← → cambian de paso, Escape lo cierra (queda guardado), Tab no se sale del recorrido.
 *  - Lector de pantalla: es un diálogo; el foco pasa al título de cada paso y el avance se anuncia.
 *  - «Reducir movimiento»: sin deslizamientos, solo un cambio sin animación.
 *  onCerrar(motivo): 'terminado' | 'saltado' | 'luego' | 'probar'
 */
export default function Recorrido({ desde = 0, onCerrar }) {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  const navegar = useNavigate()
  const nombre = useNombreParaSaludar()
  const reducir = useReducedMotion()
  const [conCuadri] = useMostrarCuadri()
  const idTitulo = useId()
  const [indice, setIndice] = useState(() => acotar(desde))
  const [direccion, setDireccion] = useState(1)
  const [verEjemplo, setVerEjemplo] = useState(false)
  const raiz = useRef(null)
  const titulo = useRef(null)
  const previo = useRef(null)

  const paso = PASOS_RECORRIDO[indice]
  const esUltimo = indice === TOTAL_PASOS - 1

  // Foco: entra al abrir, vuelve a donde estaba al cerrar
  useEffect(() => {
    previo.current = document.activeElement
    return () => previo.current?.focus?.()
  }, [])

  // Cada paso: recuerda el avance y lleva el foco al título (así el lector lo anuncia)
  useEffect(() => {
    guardarRecorrido(uid, { paso: indice, empezado: true, pendiente: false })
    setVerEjemplo(false)
    titulo.current?.focus({ preventScroll: true })
  }, [indice, uid])

  function ir(n) {
    const nuevo = acotar(n)
    setDireccion(nuevo >= indice ? 1 : -1)
    setIndice(nuevo)
  }

  function cerrar(motivo) {
    if (motivo === 'terminado') guardarRecorrido(uid, { terminado: true, saltado: false, pendiente: false, empezado: true, paso: indice })
    else if (motivo === 'saltado') guardarRecorrido(uid, { saltado: true, pendiente: false, empezado: true })
    else guardarRecorrido(uid, { paso: indice, pendiente: false, empezado: true })
    onCerrar?.(motivo)
  }

  function probarAhora() {
    cerrar('probar')
    navegar(paso.ruta)
  }

  function alTeclear(e) {
    if (e.key === 'Escape') {
      e.preventDefault()
      cerrar('luego')
    } else if (e.key === 'ArrowRight' && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) {
      if (!esUltimo) ir(indice + 1)
    } else if (e.key === 'ArrowLeft' && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) {
      if (indice > 0) ir(indice - 1)
    } else if (e.key === 'Tab') {
      const dentro = [...(raiz.current?.querySelectorAll(FOCUSABLES) || [])].filter((el) => el.offsetParent !== null || el === document.activeElement)
      if (!dentro.length) return
      const primero = dentro[0]
      const ultimo = dentro[dentro.length - 1]
      if (e.shiftKey && (document.activeElement === primero || document.activeElement === titulo.current)) {
        e.preventDefault()
        ultimo.focus()
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault()
        primero.focus()
      }
    }
  }

  const entrada = reducir ? { opacity: 1 } : { opacity: 1, x: 0 }
  const inicio = reducir ? { opacity: 1 } : { opacity: 0, x: 48 * direccion }

  return createPortal(
    <div
      ref={raiz}
      role="dialog"
      aria-modal="true"
      aria-labelledby={idTitulo}
      data-testid="recorrido"
      onKeyDown={alTeclear}
      className="fixed inset-0 z-[70] bg-paper text-ink flex flex-col"
      style={{ paddingTop: 'env(safe-area-inset-top)', paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <header className="px-5 pt-3 pb-2 flex items-center gap-3 w-full max-w-xl mx-auto">
        <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
          <Icono icono={Sparkles} tam="md" />
        </span>
        <p className="flex-1 min-w-0 t-apoyo" data-testid="recorrido-avance">
          Paso {indice + 1} de {TOTAL_PASOS} · {paso.area}
        </p>
        <button
          type="button"
          onClick={() => cerrar('saltado')}
          className="min-h-11 px-2 flex items-center gap-1 text-sm font-medium text-ink-soft"
        >
          <Icono icono={X} tam="sm" /> Saltar recorrido
        </button>
      </header>
      <div className="px-5 w-full max-w-xl mx-auto">
        <BarraProgreso pct={porcentajeRecorrido(indice)} label="Avance del recorrido" texto={`Paso ${indice + 1} de ${TOTAL_PASOS}`} className="h-1.5 rounded-full bg-line overflow-hidden" />
      </div>

      <main className="flex-1 overflow-y-auto overflow-x-hidden">
        <m.div
          key={indice}
          initial={inicio}
          animate={entrada}
          transition={reducir ? { duration: 0 } : { duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          drag={reducir ? false : 'x'}
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.18}
          onDragEnd={(_, info) => {
            if (info.offset.x < -70 && !esUltimo) ir(indice + 1)
            else if (info.offset.x > 70 && indice > 0) ir(indice - 1)
          }}
          className="w-full max-w-xl mx-auto px-5 py-4 md:py-8"
        >
          <div className="max-w-md mx-auto">
            <IlustracionRecorrido id={paso.id} />
          </div>
          {conCuadri && FRASES.recorrido[paso.id] && (
            // Cuadri guía: saluda al inicio, señala la zona de cada paso y celebra al final.
            <div className="flex items-end gap-2 mt-3" data-testid="recorrido-cuadri">
              <Cuadri pose={POSE_RECORRIDO[paso.id] || 'feliz'} size={72} />
              <p className="globo-cuadri px-3 py-2 text-[13px] text-ink mb-2">{conNombre(FRASES.recorrido[paso.id], nombre)}</p>
            </div>
          )}
          <h2 id={idTitulo} ref={titulo} tabIndex={-1} className="t-h1 mt-3 outline-none">
            {paso.titulo}
          </h2>
          <p className="t-cuerpo mt-2 text-[15px] leading-relaxed">{paso.texto}</p>
          {paso.detalle && (
            <div className="mt-3">
              <button
                type="button"
                aria-expanded={verEjemplo}
                onClick={() => setVerEjemplo((v) => !v)}
                className="min-h-11 flex items-center gap-1 text-sm font-semibold text-accent"
              >
                {paso.id === 'cuentas' ? 'Ver un ejemplo' : 'Ver más detalle'}
                <Icono icono={ChevronDown} tam="sm" className={verEjemplo ? 'rotate-180' : ''} />
              </button>
              {verEjemplo && <p className="t-cuerpo rounded-2xl bg-accent-soft p-3 mt-1">{paso.detalle}</p>}
            </div>
          )}
        </m.div>
      </main>

      <footer className="px-5 pt-2 pb-4 w-full max-w-xl mx-auto">
        <ol className="flex items-center justify-center mb-2" aria-label="Pasos del recorrido">
          {PASOS_RECORRIDO.map((p, i) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => ir(i)}
                aria-label={`Ir al paso ${i + 1}: ${p.area}`}
                aria-current={i === indice ? 'step' : undefined}
                className="w-6 h-11 flex items-center justify-center"
              >
                <span className={`block rounded-full transition-all ${i === indice ? 'w-4 h-2 bg-accent' : i < indice ? 'w-2 h-2 bg-accent/50' : 'w-2 h-2 bg-line'}`} />
              </button>
            </li>
          ))}
        </ol>
        {esUltimo ? (
          <Boton bloque onClick={() => cerrar('terminado')}>Terminar y empezar</Boton>
        ) : (
          <Boton bloque onClick={() => ir(indice + 1)} aria-label={`Siguiente: ${PASOS_RECORRIDO[indice + 1].area}`}>
            Siguiente <Icono icono={ArrowRight} tam="sm" />
          </Boton>
        )}
        <div className="grid grid-cols-2 gap-2 mt-2">
          <Boton variante="fantasma" disabled={indice === 0} onClick={() => ir(indice - 1)}>
            <Icono icono={ArrowLeft} tam="sm" /> Atrás
          </Boton>
          <Boton variante="secundario" onClick={probarAhora}>Probar ahora</Boton>
        </div>
        <p className="t-apoyo text-center mt-2">Puedes retomarlo cuando quieras desde Perfil o Ayuda.</p>
      </footer>
    </div>,
    document.body
  )
}
