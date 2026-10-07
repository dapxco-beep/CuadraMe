import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Circle, CircleCheck, LifeBuoy, Rocket, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { activarPush, estadoPermiso, pushSoportado } from '../lib/push'
import { mensajeDeError } from '../lib/mensajes'
import {
  armarPasos, detectarDispositivo, estaInstalada, guardarEstado, leerEstado, resumenProgreso, siguientePaso,
} from '../lib/primerUso'
import BarraProgreso from './BarraProgreso'
import GuiaInstalar from './GuiaInstalar'
import Icono from './Icono'
import { Boton } from './ui'

// «Primeros pasos»: lista guiada para quien llega por primera vez. NINGÚN paso se marca a mano:
// cada uno se calcula del estado real de la cuenta (cuentas creadas, app instalada, avisos
// activos, Gmail conectado, atajo usado, extracto subido) y se vuelve a revisar al volver a la app.
//   variante="inicio": tarjeta compacta (solo el paso que sigue); desaparece al completarse u ocultarla.
//   variante="perfil": lista completa, siempre disponible.

// Lee un dato sin que un fallo rompa la tarjeta: sin dato, el paso simplemente queda pendiente.
const seguro = (f) => Promise.resolve().then(f).catch(() => null)

function usePrimerUso() {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  const dispositivo = useMemo(() => detectarDispositivo(), [])
  const [datos, setDatos] = useState(null)
  const [memoria, setMemoria] = useState(() => leerEstado(uid))

  const cargar = useCallback(async () => {
    // Una sola llamada (el tablero de conexiones) trae cuentas, Gmail, atajo, avisos y extractos.
    const [con, permisoPush] = await Promise.all([seguro(() => api.conexionesEstado?.()), seguro(() => estadoPermiso())])
    // Si el tablero no responde se da por hecho el paso de cuentas: la app no llega a Inicio sin ninguna.
    const listaCuentas = con?.conciliacion?.cuentas
    setDatos({
      cuentas: Array.isArray(listaCuentas) ? listaCuentas.length : 1,
      instalada: estaInstalada(),
      permisoPush,
      pushActivo: (con?.push?.suscripciones || 0) > 0,
      gmailConectado: !!con?.gmail?.conectado,
      atajoUsado: !!con?.atajo?.ultimo_uso,
      hayExtracto: Array.isArray(con?.conciliacion?.cuentas) && con.conciliacion.cuentas.some((c) => c.extracto),
    })
  }, [])

  useEffect(() => {
    cargar()
    // Al volver a la app (de Google, de los Ajustes del celular, de Atajos) se revisa de nuevo.
    const alVolver = () => document.visibilityState !== 'hidden' && cargar()
    document.addEventListener('visibilitychange', alVolver)
    window.addEventListener('focus', alVolver)
    return () => {
      document.removeEventListener('visibilitychange', alVolver)
      window.removeEventListener('focus', alVolver)
    }
  }, [cargar])

  const cambiarMemoria = (siguiente) => {
    setMemoria(siguiente)
    guardarEstado(uid, siguiente)
  }

  const pasos = useMemo(
    () => (datos ? armarPasos({ dispositivo, datos, saltados: memoria.saltados }) : []),
    [datos, dispositivo, memoria.saltados]
  )

  return {
    cargado: !!datos,
    dispositivo,
    pasos,
    progreso: resumenProgreso(pasos),
    oculto: memoria.oculto,
    ocultar: () => cambiarMemoria({ ...memoria, oculto: true }),
    mostrar: () => cambiarMemoria({ ...memoria, oculto: false }),
    saltar: (id) => cambiarMemoria({ ...memoria, saltados: [...new Set([...memoria.saltados, id])] }),
    retomar: (id) => cambiarMemoria({ ...memoria, saltados: memoria.saltados.filter((s) => s !== id) }),
    recargar: cargar,
  }
}

function AvisoPrivacidadGmail() {
  return (
    <div className="mt-2 rounded-2xl bg-accent-soft p-3" data-testid="privacidad-gmail">
      <p className="t-cuerpo font-semibold flex items-center gap-1.5">
        <Icono icono={ShieldCheck} tam="sm" className="text-accent" /> Qué leemos y qué no
      </p>
      <ul className="t-apoyo mt-1.5 space-y-1 list-disc pl-4">
        <li>Solo los correos de tu banco: avisos de compras, transferencias y extractos.</li>
        <li>No leemos tus correos personales ni de trabajo.</li>
        <li>No enviamos, borramos ni cambiamos ningún correo.</li>
        <li>Puedes quitar el permiso cuando quieras.</li>
      </ul>
      <Link to="/ayuda?p=gmail-seguro" className="inline-flex items-center min-h-11 text-xs font-semibold text-accent">
        Leer más en la ayuda
      </Link>
    </div>
  )
}

function FilaPaso({ paso, destacado, onGuia, onSaltar, onRetomar, onActivar, activando, error, conBoton = true }) {
  const { hecho, saltado } = paso
  // Activar los avisos se hace aquí mismo cuando el navegador lo permite; si no, se va a Perfil.
  const activaAqui = paso.activable && pushSoportado()
  return (
    <li
      className="py-3"
      data-paso={paso.id}
      data-estado={hecho ? 'hecho' : saltado ? 'saltado' : 'pendiente'}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 ${hecho ? 'text-accent' : 'text-ink-soft'}`}>
          <Icono icono={hecho ? CircleCheck : Circle} tam="md" />
        </span>
        <div className="min-w-0 flex-1">
          <p className={`t-cuerpo font-semibold ${hecho ? 'text-ink-soft' : ''}`}>
            {paso.titulo}
            <span className="sr-only">{hecho ? ' (hecho)' : saltado ? ' (lo dejaste para después)' : ' (pendiente)'}</span>
          </p>
          {!hecho && <p className="t-apoyo mt-0.5">{paso.apoyo}</p>}
          {hecho && <p className="t-apoyo mt-0.5">Hecho</p>}
          {!hecho && paso.privacidad && <AvisoPrivacidadGmail />}
          {error && (
            <p role="alert" className="t-apoyo text-danger mt-1">
              {error}
            </p>
          )}
          {!hecho && conBoton && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {paso.guia ? (
                <Boton tam="sm" variante={destacado ? 'primario' : 'secundario'} onClick={onGuia}>
                  {paso.accion}
                </Boton>
              ) : activaAqui ? (
                <Boton tam="sm" variante={destacado ? 'primario' : 'secundario'} onClick={onActivar} cargando={activando}>
                  {paso.accion}
                </Boton>
              ) : (
                <Boton tam="sm" variante={destacado ? 'primario' : 'secundario'} to={paso.ruta}>
                  {paso.accion}
                </Boton>
              )}
              {paso.id !== 'cuentas' &&
                (saltado ? (
                  <button type="button" onClick={onRetomar} className="min-h-11 px-2 text-xs font-semibold text-accent">
                    Retomar
                  </button>
                ) : (
                  <button type="button" onClick={onSaltar} className="min-h-11 px-2 text-xs font-medium text-ink-soft">
                    Más tarde
                  </button>
                ))}
            </div>
          )}
        </div>
      </div>
    </li>
  )
}

export default function AsistentePrimerUso({ variante = 'inicio' }) {
  const p = usePrimerUso()
  const [verTodos, setVerTodos] = useState(false)
  const [guia, setGuia] = useState(false)
  const [activando, setActivando] = useState(false)
  const [errorPaso, setErrorPaso] = useState({})

  async function activarAvisos() {
    setActivando(true)
    setErrorPaso((e) => ({ ...e, notificaciones: '' }))
    try {
      await activarPush()
      await p.recargar()
    } catch (err) {
      const texto = /permiso/i.test(err?.message || '')
        ? 'Tu celular no dejó activar los avisos. Permítelos para CuadraMe en los Ajustes del celular.'
        : mensajeDeError(err, 'No pudimos activar los avisos. Intenta de nuevo.')
      setErrorPaso((e) => ({ ...e, notificaciones: texto }))
    } finally {
      setActivando(false)
    }
  }

  if (!p.cargado) return null
  const { progreso, pasos } = p
  const enInicio = variante === 'inicio'
  // En Inicio: solo mientras falte algo y no se haya ocultado. En Perfil siempre.
  if (enInicio && (progreso.completo || p.oculto)) return null

  const siguiente = siguientePaso(pasos)
  const visibles = enInicio && !verTodos ? pasos.filter((x) => x.id === siguiente?.id) : pasos
  const titulo = progreso.completo ? 'Todo listo' : 'Primeros pasos'
  const resumen = `${progreso.resueltos} de ${progreso.total}`

  return (
    <section
      aria-label="Primeros pasos"
      data-testid={`primeros-pasos-${variante}`}
      className={enInicio ? 'mx-6 mt-3 tarjeta p-4' : 'mx-6 mt-6'}
    >
      <div className="flex items-center gap-2">
        <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
          <Icono icono={Rocket} tam="md" />
        </span>
        <h2 className={`flex-1 min-w-0 ${enInicio ? 't-h2' : 'text-[15px] font-semibold'}`}>{titulo}</h2>
        <span className="t-apoyo shrink-0" data-testid="progreso-pasos">
          {resumen}
        </span>
      </div>
      <BarraProgreso pct={progreso.pct} label="Avance de los primeros pasos" texto={`${resumen} pasos`} className="h-2 rounded-full bg-line overflow-hidden mt-3" />

      {progreso.completo && !enInicio && (
        <p className="t-apoyo mt-2">Ya hiciste todo lo importante. Aquí quedan los pasos por si quieres repasarlos.</p>
      )}
      {!enInicio && p.oculto && !progreso.completo && (
        <p className="t-apoyo mt-2">
          Los ocultaste de Inicio.{' '}
          <button type="button" onClick={p.mostrar} className="font-semibold text-accent min-h-11">
            Volver a mostrarlos en Inicio
          </button>
        </p>
      )}

      <ul className="divide-y divide-line mt-1" aria-label="Lista de pasos">
        {visibles.map((paso) => (
          <FilaPaso
            key={paso.id}
            paso={paso}
            destacado={paso.id === siguiente?.id}
            onGuia={() => setGuia(true)}
            onSaltar={() => p.saltar(paso.id)}
            onRetomar={() => p.retomar(paso.id)}
            onActivar={activarAvisos}
            activando={activando}
            error={errorPaso[paso.id]}
          />
        ))}
      </ul>

      {enInicio && (
        <div className="flex items-center justify-between gap-2 mt-1">
          <button
            type="button"
            aria-expanded={verTodos}
            onClick={() => setVerTodos((v) => !v)}
            className="min-h-11 flex items-center gap-1 text-xs font-semibold text-accent"
          >
            {verTodos ? 'Ver solo el siguiente' : 'Ver todos los pasos'}
            <Icono icono={ChevronDown} tam="sm" className={verTodos ? 'rotate-180' : ''} />
          </button>
          <div className="flex items-center gap-1">
            <Link to="/ayuda" className="min-h-11 px-2 flex items-center gap-1 text-xs font-medium text-ink-soft">
              <Icono icono={LifeBuoy} tam="sm" /> Ayuda
            </Link>
            <button type="button" onClick={p.ocultar} className="min-h-11 px-2 text-xs font-medium text-ink-soft">
              Ocultar por ahora
            </button>
          </div>
        </div>
      )}

      {guia && <GuiaInstalar dispositivo={p.dispositivo} onCerrar={() => setGuia(false)} />}
    </section>
  )
}
