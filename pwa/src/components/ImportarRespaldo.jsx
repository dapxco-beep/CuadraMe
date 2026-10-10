import { useEffect, useRef, useState } from 'react'
import { Undo2, Upload, X } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import Hoja from './Hoja'

// Perfil -> Privacidad y datos -> «Importar mi respaldo».
// Flujo: elegir el ZIP de «Descargar mis datos» -> vista previa en lenguaje llano (no guarda nada)
// -> «Importar» -> resultado con conteos y «Deshacer última importación».
const NOMBRES = [
  ['cuentas', 'cuenta', 'cuentas'],
  ['movimientos', 'movimiento', 'movimientos'],
  ['presupuestos', 'presupuesto', 'presupuestos'],
  ['metas', 'meta', 'metas'],
  ['reglas', 'regla', 'reglas'],
]

function plural(n, uno, varios) {
  return `${n} ${n === 1 ? uno : varios}`
}

// «Se agregarían 3 cuentas y 120 movimientos. Ya tenías 2 cuentas: no se repiten.»
export function frasesRespaldo(r, condicional = true) {
  const nuevos = []
  const existentes = []
  for (const [k, uno, varios] of NOMBRES) {
    const x = r?.[k]
    if (!x) continue
    if (x.nuevos > 0) nuevos.push(plural(x.nuevos, uno, varios))
    if (x.existentes > 0) existentes.push(plural(x.existentes, uno, varios))
  }
  const lista = (a) => (a.length > 1 ? `${a.slice(0, -1).join(', ')} y ${a[a.length - 1]}` : a[0])
  const frases = []
  if (nuevos.length) frases.push(`${condicional ? 'Se agregarían' : 'Se agregaron'} ${lista(nuevos)}.`)
  else frases.push(condicional ? 'No hay nada nuevo para agregar.' : 'No había nada nuevo para agregar.')
  if (existentes.length) frases.push(`Ya tenías ${lista(existentes)}: no se repiten.`)
  const m = r?.movimientos || {}
  if (m.anteriores_al_punto_de_partida > 0)
    frases.push(
      `${plural(m.anteriores_al_punto_de_partida, 'movimiento queda', 'movimientos quedan')} por fuera, porque son anteriores a tu punto de partida.`
    )
  if (m.sin_cuenta > 0)
    frases.push(`${plural(m.sin_cuenta, 'movimiento', 'movimientos')} no se pueden importar porque su cuenta no viene en el respaldo.`)
  const raros = NOMBRES.reduce((s, [k]) => s + (r?.[k]?.invalidos || 0), 0)
  if (raros > 0) frases.push(`${plural(raros, 'registro', 'registros')} del archivo no se entendieron y se dejaron por fuera.`)
  return frases
}

export default function ImportarRespaldo({ onCerrar }) {
  const { confirmar, avisar } = useDialogos()
  const entrada = useRef(null)
  const [archivo, setArchivo] = useState(null)
  const [vista, setVista] = useState(null)
  const [resultado, setResultado] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState('')
  const [hayParaDeshacer, setHayParaDeshacer] = useState(false)
  const [deshecho, setDeshecho] = useState(false)

  useEffect(() => {
    Promise.resolve()
      .then(() => api.ultimaImportacionRespaldo?.())
      .then((r) => setHayParaDeshacer(!!r?.hay))
      .catch(() => {})
  }, [])

  async function alElegir(e) {
    const f = e.target.files?.[0]
    setVista(null)
    setResultado(null)
    setError('')
    setDeshecho(false)
    setArchivo(f || null)
    if (!f) return
    setOcupado(true)
    try {
      setVista(await api.vistaPreviaRespaldo(f))
    } catch (err) {
      setError(err.message || 'No pudimos leer ese archivo. Revisa que sea el ZIP de «Descargar mis datos».')
    } finally {
      setOcupado(false)
    }
  }

  async function importar() {
    if (!archivo || ocupado) return
    setOcupado(true)
    setError('')
    try {
      const r = await api.importarRespaldo(archivo)
      setResultado(r)
      setVista(null)
      setHayParaDeshacer(true)
      setDeshecho(false)
    } catch (err) {
      setError(err.message || 'No pudimos importar tu respaldo y no se guardó nada. Intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }

  async function deshacer() {
    const ok = await confirmar(
      'Quitamos solo lo que se agregó con tu última importación. Lo que ya tenías antes no se toca.',
      { titulo: '¿Deshacer la última importación?', confirmarTexto: 'Deshacer', peligro: true }
    )
    if (!ok) return
    setOcupado(true)
    try {
      await api.deshacerImportacionRespaldo()
      setDeshecho(true)
      setResultado(null)
      setHayParaDeshacer(false)
    } catch (err) {
      avisar(err.message || 'No pudimos deshacer la importación. No se cambió nada.')
    } finally {
      setOcupado(false)
    }
  }

  const hayNuevo = vista && NOMBRES.some(([k]) => vista[k]?.nuevos > 0)

  return (
    <Hoja onCerrar={onCerrar} capa="z-[60]" titulo="Importar mi respaldo">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Upload size={20} className="text-accent" /> Importar mi respaldo
        </h2>
        <button
          onClick={onCerrar}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Cerrar"
        >
          <X size={16} />
        </button>
      </div>

      <p className="text-sm leading-relaxed">
        Recupera lo que guardaste con «Descargar mis datos». Elige el archivo ZIP; primero te mostramos qué
        pasaría, y solo se guarda cuando tú lo confirmes.
      </p>
      <p className="text-xs text-ink-soft mt-2 leading-relaxed">
        Lo que ya tienes no se repite, así que puedes importar el mismo archivo más de una vez sin miedo.
      </p>

      <input
        ref={entrada}
        type="file"
        accept=".zip,.json,application/zip,application/json"
        onChange={alElegir}
        className="sr-only"
        aria-label="Archivo de respaldo"
        data-testid="archivo-respaldo"
      />
      <button
        onClick={() => entrada.current?.click()}
        disabled={ocupado}
        className="mt-4 w-full min-h-12 rounded-xl border border-line bg-paper-raised text-sm font-medium disabled:opacity-60"
      >
        {archivo ? `Cambiar archivo (${archivo.name})` : 'Elegir mi archivo de respaldo'}
      </button>

      {ocupado && !resultado && <p className="text-sm text-ink-soft mt-3">Un momento...</p>}
      {error && (
        <p role="alert" className="text-sm text-danger mt-3">
          {error}
        </p>
      )}

      {vista && (
        <div className="mt-4 rounded-xl bg-paper-raised border border-line p-3.5" data-testid="vista-previa-respaldo">
          <p className="text-sm font-medium">Esto es lo que pasaría</p>
          {vista.correo_distinto && (
            <p className="text-xs text-ink-soft mt-1">Ojo: este respaldo fue descargado desde otra cuenta.</p>
          )}
          <ul className="text-sm mt-2 space-y-1 list-disc pl-5">
            {frasesRespaldo(vista, true).map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {resultado && (
        <div className="mt-4 rounded-xl bg-paper-raised border border-line p-3.5" role="status" data-testid="resultado-respaldo">
          <p className="text-sm font-medium">¡Listo! Tu respaldo quedó importado</p>
          <ul className="text-sm mt-2 space-y-1 list-disc pl-5">
            {frasesRespaldo(resultado, false).map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      {deshecho && (
        <p role="status" className="text-sm mt-4">
          Listo, deshicimos la importación. Todo volvió a como estaba.
        </p>
      )}

      <div className="flex gap-3 mt-4">
        <button onClick={onCerrar} className="flex-1 min-h-12 rounded-xl border border-line bg-paper-raised text-sm font-medium">
          Cerrar
        </button>
        {vista && (
          <button
            onClick={importar}
            disabled={ocupado || !hayNuevo}
            className="flex-1 min-h-12 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-40"
          >
            {ocupado ? 'Importando...' : 'Importar'}
          </button>
        )}
      </div>

      {hayParaDeshacer && !deshecho && (
        <button
          onClick={deshacer}
          disabled={ocupado}
          className="mt-3 w-full min-h-11 flex items-center justify-center gap-2 text-sm text-danger font-medium disabled:opacity-60"
        >
          <Undo2 size={16} /> Deshacer última importación
        </button>
      )}
    </Hoja>
  )
}
