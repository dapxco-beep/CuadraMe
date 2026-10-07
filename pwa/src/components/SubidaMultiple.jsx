import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Check, FileSpreadsheet, FileText, Loader2, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { AvisoCategorizados } from './CategorizacionAuto'
import AvisoYaConciliado from './AvisoYaConciliado'
import RecordarRegla, { RECORDAR_INICIAL } from './RecordarRegla'
import ZonaSubida from './ZonaSubida'
import { opcionesCategoria } from '../lib/importar'
import {
  ETIQUETA_ARCHIVO,
  MAX_ARCHIVOS,
  agruparPorCuenta,
  clavesFaltantes,
  consolidar,
  normalizarPdf,
  normalizarTabular,
  procesarCola,
  sugerirCuenta,
  tipoDeArchivo,
  validarSeleccion,
} from '../lib/subidaMultiple'

function aBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

let contador = 0
const nuevoId = () => `arch-${Date.now()}-${(contador += 1)}`

// El servidor devuelve para un PDF ilegible un mensaje técnico con texto del PDF: aquí se
// reduce a algo que el usuario entienda.
function errorLegible(msg) {
  if (!msg) return 'No se pudo procesar el archivo.'
  if (msg.startsWith('No se pudieron extraer movimientos')) {
    return 'No encontramos movimientos en este PDF. Si es una foto o un escaneo, descarga el extracto digital desde tu banco.'
  }
  return msg
}

function periodoTexto(p) {
  if (!p) return 'periodo no detectado'
  return p.desde === p.hasta ? p.desde : `${p.desde} a ${p.hasta}`
}

/**
 * Varios extractos a la vez: cola (uno tras otro, un fallo no frena a los demás),
 * revisión consolidada sin duplicados entre archivos y UNA confirmación que importa
 * lo marcado, aplica las categorías y guarda las reglas que el usuario quiso recordar.
 */
export default function SubidaMultiple({ archivosIniciales = [], cuentaInicial = '', onCancelar }) {
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const { nombres: CATEGORIAS } = useCategorias()
  const [archivos, setArchivos] = useState(() => {
    const { aceptados } = validarSeleccion(archivosIniciales)
    return aceptados.map((f) => ({
      id: nuevoId(), file: f, nombre: f.name, tipo: tipoDeArchivo(f.name),
      cuentaId: sugerirCuenta(f.name, cuentas, cuentaInicial), password: '', estado: 'pendiente', error: '',
      banco: '', periodo: null, items: [],
    }))
  })
  const [rechazados, setRechazados] = useState(() => validarSeleccion(archivosIniciales).rechazados)
  const [progreso, setProgreso] = useState({ actual: 0, total: 0 })
  const [corriendo, setCorriendo] = useState(false)
  const [fase, setFase] = useState('cola') // cola | revision | resultado
  const [seleccion, setSeleccion] = useState(new Set())
  const [categorias, setCategorias] = useState({})
  const [aprender, setAprender] = useState({}) // clave -> { recordar, anteriores } (solo filas editadas)
  const [importando, setImportando] = useState(false)
  const [resultados, setResultados] = useState([])
  const [error, setError] = useState('')
  const archivosRef = useRef(archivos)
  archivosRef.current = archivos

  const consolidado = useMemo(() => consolidar(archivos), [archivos])
  const listos = consolidado.archivos.filter((a) => a.estado === 'listo')
  const hayPendientes = archivos.some((a) => a.estado === 'pendiente')
  const nombreCuenta = (id) => cuentas.find((c) => c.id === id)?.nombre || 'Cuenta'

  const parchar = (id, parche) => setArchivos((prev) => prev.map((a) => (a.id === id ? { ...a, ...parche } : a)))

  function agregar(files) {
    const { aceptados, rechazados: rech } = validarSeleccion(files, archivos.length)
    setRechazados(rech)
    setArchivos((prev) => [
      ...prev,
      ...aceptados.map((f) => ({
        id: nuevoId(), file: f, nombre: f.name, tipo: tipoDeArchivo(f.name),
        cuentaId: sugerirCuenta(f.name, cuentas, cuentaInicial), password: '', estado: 'pendiente', error: '',
        banco: '', periodo: null, items: [],
      })),
    ])
  }

  function quitar(id) {
    setArchivos((prev) => prev.filter((a) => a.id !== id))
  }

  async function procesarUno(a) {
    const base64 = await aBase64(a.file)
    if (a.tipo === 'pdf') {
      const r = await api.procesarExtracto(base64, a.cuentaId, a.password)
      if (!r.ok) {
        if (r.requiere_clave) return { estado: 'falta_clave', error: r.error }
        throw new Error(errorLegible(r.error))
      }
      return { estado: 'listo', error: '', ...normalizarPdf(r), nMov: r.total_movimientos }
    }
    const r = await api.importarVistaPrevia({ cuenta_id: a.cuentaId, nombre_archivo: a.nombre, archivo_base64: base64 })
    const n = normalizarTabular(r)
    if (n.items.length === 0) {
      throw new Error('No reconocimos las columnas de este archivo. Impórtalo solo desde "Importar Excel o CSV" para elegirlas a mano.')
    }
    return { estado: 'listo', error: '', ...n, nMov: n.items.length }
  }

  async function procesar() {
    setCorriendo(true)
    setError('')
    await procesarCola(archivosRef.current, procesarUno, { onCambio: parchar, onProgreso: setProgreso })
    setCorriendo(false)
  }

  function reintentar(a) {
    parchar(a.id, { estado: 'pendiente', error: '' })
    // el estado se aplica al terminar el render; la cola lee archivosRef
    setTimeout(procesar, 0)
  }

  function irARevision() {
    const claves = clavesFaltantes(consolidado.archivos)
    setSeleccion(new Set(claves))
    const cats = {}
    for (const a of consolidado.archivos) {
      if (a.estado !== 'listo') continue
      for (const it of a.items) cats[`${a.id}:${it.k}`] = it.categoria || 'Otros'
    }
    setCategorias(cats)
    setAprender({})
    setFase('revision')
  }

  function alternar(clave) {
    setSeleccion((prev) => {
      const next = new Set(prev)
      if (next.has(clave)) next.delete(clave)
      else next.add(clave)
      return next
    })
  }

  function cambiarCategoria(clave, it, categoria) {
    setCategorias((c) => ({ ...c, [clave]: categoria }))
    setAprender((prev) => {
      const next = { ...prev }
      if (categoria === (it.categoria || 'Otros')) delete next[clave]
      else next[clave] = next[clave] || RECORDAR_INICIAL // «Recordar» marcado por defecto
      return next
    })
  }

  const totalMarcados = consolidado.archivos.reduce(
    (n, a) => n + (a.estado === 'listo' ? a.items.filter((it) => seleccion.has(`${a.id}:${it.k}`) && (it.estado === 'nuevo' || it.estado === 'posible')).length : 0),
    0
  )
  const totalFaltan = clavesFaltantes(consolidado.archivos).length

  async function importar() {
    setImportando(true)
    setError('')
    const salida = []
    for (const a of consolidado.archivos) {
      if (a.estado !== 'listo') continue
      const marcados = a.items.filter((it) => seleccion.has(`${a.id}:${it.k}`) && (it.estado === 'nuevo' || it.estado === 'posible'))
      if (marcados.length === 0) continue
      const rec = (it) => aprender[`${a.id}:${it.k}`]
      try {
        let r
        if (a.tipo === 'pdf') {
          const cats = Object.fromEntries(marcados.map((it) => [it.k, categorias[`${a.id}:${it.k}`] || 'Otros']))
          r = await api.importarFaltantes(a.historialId, marcados.map((it) => it.k), cats, {
            recordar: marcados.filter((it) => rec(it)?.recordar).map((it) => it.k),
            aplicar_anteriores: marcados.filter((it) => rec(it)?.recordar && rec(it)?.anteriores).map((it) => it.k),
          })
        } else {
          r = await api.importarConfirmar({
            cuenta_id: a.cuentaId,
            nombre_archivo: a.nombre,
            ajustar_saldo: true,
            filas: marcados.map((it) => ({
              fecha: it.fecha, descripcion: it.descripcion, monto: it.monto, tipo: it.tipo,
              categoria: categorias[`${a.id}:${it.k}`] || 'Otros',
              recordar: !!rec(it)?.recordar, aplicar_anteriores: !!(rec(it)?.recordar && rec(it)?.anteriores),
            })),
          })
        }
        salida.push({ id: a.id, nombre: a.nombre, cuenta: nombreCuenta(a.cuentaId), ok: true, ...r })
      } catch (err) {
        salida.push({ id: a.id, nombre: a.nombre, cuenta: nombreCuenta(a.cuentaId), ok: false, error: err.message || 'No se pudo importar' })
      }
    }
    await recargarCuentas()
    setResultados(salida)
    setFase('resultado')
    setImportando(false)
  }

  // ── Resultado ──────────────────────────────────────────────
  if (fase === 'resultado') {
    const totalImportados = resultados.reduce((n, r) => n + (r.importados || 0), 0)
    const totalAuto = resultados.reduce((n, r) => n + (r.categorizados_auto || 0), 0)
    const reglas = resultados.reduce((n, r) => n + (r.reglas_guardadas || 0), 0)
    return (
      <div className="px-5 mt-4" data-testid="resultado-multiple">
        <div className="text-center">
          <div className="w-14 h-14 rounded-full bg-accent-soft text-accent flex items-center justify-center mx-auto mb-3">
            <Check size={24} />
          </div>
          <p className="text-lg font-semibold">
            {totalImportados} {totalImportados === 1 ? 'movimiento importado' : 'movimientos importados'}
          </p>
          {reglas > 0 && (
            <p className="text-sm text-ink-soft mt-1">
              Aprendí {reglas} {reglas === 1 ? 'comercio' : 'comercios'} nuevos para la próxima.
            </p>
          )}
        </div>
        <ul className="mt-4 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
          {resultados.map((r) => (
            <li key={r.id} className="px-4 py-3">
              <p className="text-sm font-medium truncate">{r.nombre}</p>
              {r.ok ? (
                <p className="text-xs text-ink-soft">
                  {r.cuenta} · {r.importados} importados
                  {r.duplicados_omitidos > 0 ? ` · ${r.duplicados_omitidos} ya estaban` : ''}
                </p>
              ) : (
                <p className="text-xs text-danger" role="alert">{r.cuenta} · {r.error}</p>
              )}
            </li>
          ))}
        </ul>
        <AvisoCategorizados n={totalAuto} className="mt-4" />
        <div className="flex gap-2 mt-6">
          <button onClick={onCancelar} className="flex-1 rounded-2xl border border-line py-3.5 text-sm font-semibold">Subir otros</button>
          <Link to="/movimientos" replace className="flex-1 bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold text-center">
            Ver movimientos
          </Link>
        </div>
      </div>
    )
  }

  // ── Revisión consolidada ───────────────────────────────────
  if (fase === 'revision') {
    const grupos = agruparPorCuenta(consolidado.archivos)
    return (
      <div className="px-5 mt-4" data-testid="revision-multiple">
        <div className="rounded-2xl bg-paper-raised border border-line p-4 mb-3 grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-lg font-bold">{listos.length}</p>
            <p className="text-xs text-ink-soft">Archivos</p>
          </div>
          <div>
            <p className="text-lg font-bold text-danger">{totalFaltan}</p>
            <p className="text-xs text-ink-soft">Faltan</p>
          </div>
          <div>
            <p className="text-lg font-bold text-ink-soft">{consolidado.repetidos}</p>
            <p className="text-xs text-ink-soft">Repetidos entre archivos</p>
          </div>
        </div>
        {consolidado.repetidos > 0 && (
          <p className="text-xs text-ink-soft mb-3">
            Los movimientos que aparecen en dos extractos (periodos que se solapan) se cuentan una sola vez.
          </p>
        )}

        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setSeleccion(new Set(clavesFaltantes(consolidado.archivos)))}
            className="flex-1 rounded-2xl border border-line py-2.5 text-xs font-semibold"
          >
            Seleccionar todo lo que falta ({totalFaltan})
          </button>
          <button onClick={() => setSeleccion(new Set())} className="flex-1 rounded-2xl border border-line py-2.5 text-xs font-semibold">
            Quitar selección
          </button>
        </div>

        {grupos.map((g) => (
          <section key={g.cuentaId} className="mb-5" aria-label={`Cuenta ${nombreCuenta(g.cuentaId)}`}>
            <h2 className="text-sm font-semibold mb-2">{nombreCuenta(g.cuentaId)}</h2>
            {g.archivos.map((a) => {
              const visibles = a.items.filter((it) => it.estado !== 'ya')
              const ya = a.items.length - visibles.length
              return (
                <div key={a.id} className="mb-3">
                  <p className="text-xs text-ink-soft mb-1.5 truncate">
                    {a.nombre} · {a.banco} · {periodoTexto(a.periodo)}
                    {ya > 0 ? ` · ${ya} ya registrados` : ''}
                  </p>
                  {visibles.length === 0 ? (
                    <p className="text-xs text-ink-soft rounded-2xl border border-line bg-paper-raised px-4 py-3">Todo lo de este archivo ya estaba registrado.</p>
                  ) : (
                    <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                      {visibles.map((it) => {
                        const clave = `${a.id}:${it.k}`
                        const marcado = seleccion.has(clave)
                        const repetido = it.estado === 'repetido'
                        return (
                          <div key={clave} className="px-4 py-3">
                            <label className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                checked={marcado && !repetido}
                                disabled={repetido}
                                onChange={() => alternar(clave)}
                                className="w-5 h-5 accent-accent shrink-0"
                                aria-label={`Importar ${it.descripcion}`}
                              />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{it.descripcion}</p>
                                <p className={`text-xs ${repetido ? 'text-ink-soft' : it.estado === 'posible' ? 'text-danger' : 'text-danger'}`}>
                                  {it.fecha} ·{' '}
                                  {repetido ? `Ya está en ${it.repetidoDe}` : it.estado === 'posible' ? 'Posible duplicado' : 'Falta registrar'}
                                </p>
                              </div>
                              <p className="text-sm font-semibold shrink-0">
                                {it.tipo === 'income' ? '+' : '-'}
                                {formatCOP(it.monto)}
                              </p>
                            </label>
                            {marcado && !repetido && (
                              <div className="ml-8 mt-2">
                                <select
                                  aria-label={`Categoría de ${it.descripcion}`}
                                  value={categorias[clave] || 'Otros'}
                                  onChange={(e) => cambiarCategoria(clave, it, e.target.value)}
                                  className="w-full rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                                >
                                  {opcionesCategoria(CATEGORIAS, categorias[clave]).map((c) => (
                                    <option key={c} value={c}>{c}</option>
                                  ))}
                                </select>
                                {it.razon && !aprender[clave] && <p className="text-[11px] text-ink-soft mt-1">Auto · {it.razon}</p>}
                                {aprender[clave] && (
                                  <RecordarRegla
                                    className="mt-2"
                                    descripcion={it.descripcion}
                                    valor={aprender[clave]}
                                    onChange={(v) => setAprender((p) => ({ ...p, [clave]: v }))}
                                  />
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </section>
        ))}

        {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
        <div className="flex gap-2">
          <button onClick={() => setFase('cola')} className="flex-1 rounded-2xl border border-line py-3.5 text-sm font-semibold">Atrás</button>
          <button
            onClick={importar}
            disabled={totalMarcados === 0 || importando}
            className="flex-1 bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
          >
            <Check size={16} /> {importando ? 'Importando...' : `Importar (${totalMarcados})`}
          </button>
        </div>
      </div>
    )
  }

  // ── Cola ───────────────────────────────────────────────────
  return (
    <div className="px-5 mt-4" data-testid="cola-multiple">
      {corriendo && progreso.total > 0 && (
        <p className="text-sm font-semibold mb-3" role="status">
          Archivo {progreso.actual} de {progreso.total}
        </p>
      )}

      <ul className="space-y-2.5 mb-4">
        {archivos.map((a) => {
          const Icono = a.tipo === 'pdf' ? FileText : FileSpreadsheet
          return (
            <li key={a.id} className="rounded-2xl bg-paper-raised border border-line p-3.5" data-estado={a.estado}>
              <div className="flex items-start gap-3">
                <Icono size={20} className="text-accent shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{a.nombre}</p>
                  <p className={`text-xs mt-0.5 flex items-center gap-1 ${a.estado === 'error' || a.estado === 'falta_clave' ? 'text-danger' : a.estado === 'listo' ? 'text-accent' : 'text-ink-soft'}`}>
                    {a.estado === 'procesando' && <Loader2 size={16} className="animate-spin" />}
                    {a.estado === 'error' || a.estado === 'falta_clave' ? <AlertTriangle size={16} /> : null}
                    {ETIQUETA_ARCHIVO[a.estado]}
                  </p>
                  {a.estado === 'listo' && (
                    <p className="text-xs text-ink-soft mt-0.5">
                      {a.banco} · {periodoTexto(a.periodo)} · {a.nMov} {a.nMov === 1 ? 'movimiento' : 'movimientos'}
                    </p>
                  )}
                  {a.estado === 'listo' && <AvisoYaConciliado info={a.yaConciliado} cuenta={nombreCuenta(a.cuentaId)} className="mt-2" />}
                  {(a.estado === 'error' || a.estado === 'falta_clave') && a.error && (
                    <p className="text-xs text-danger mt-1" role="alert">{a.error}</p>
                  )}
                </div>
                {a.estado !== 'procesando' && (
                  <button onClick={() => quitar(a.id)} aria-label={`Quitar ${a.nombre}`} className="w-11 h-11 -mr-1 flex items-center justify-center text-ink-soft shrink-0">
                    <X size={16} />
                  </button>
                )}
              </div>

              {(a.estado === 'pendiente' || a.estado === 'falta_clave' || a.estado === 'error') && cuentas.length > 1 && (
                <label className="block mt-2.5 ml-8">
                  <span className="text-[11px] text-ink-soft">Cuenta</span>
                  <select
                    aria-label={`Cuenta de ${a.nombre}`}
                    value={a.cuentaId}
                    onChange={(e) => parchar(a.id, { cuentaId: e.target.value })}
                    className="w-full mt-0.5 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                  >
                    {cuentas.map((c) => (
                      <option key={c.id} value={c.id}>{c.icono} {c.nombre}</option>
                    ))}
                  </select>
                </label>
              )}

              {a.estado === 'falta_clave' && (
                <div className="flex gap-2 mt-2.5 ml-8">
                  <input
                    value={a.password}
                    onChange={(e) => parchar(a.id, { password: e.target.value })}
                    placeholder="Clave del PDF"
                    aria-label={`Clave de ${a.nombre}`}
                    className="flex-1 min-w-0 rounded-xl border border-line bg-paper px-3 py-2 text-xs outline-none focus:border-accent"
                  />
                  <button onClick={() => reintentar(a)} disabled={!a.password || corriendo} className="rounded-xl bg-accent text-white px-3 text-xs font-semibold disabled:opacity-60">
                    Reintentar
                  </button>
                </div>
              )}
              {a.estado === 'error' && (
                <button onClick={() => reintentar(a)} disabled={corriendo} className="mt-2 ml-8 text-xs font-semibold text-accent underline disabled:opacity-60">
                  Reintentar
                </button>
              )}
            </li>
          )
        })}
      </ul>

      {rechazados.length > 0 && (
        <ul className="mb-4 space-y-1" role="alert">
          {rechazados.map((r, i) => (
            <li key={i} className="text-xs text-danger">{r.nombre}: {r.motivo}</li>
          ))}
        </ul>
      )}

      {archivos.length < MAX_ARCHIVOS && !corriendo && (
        <div className="mb-4">
          <ZonaSubida onArchivos={agregar} titulo="Agregar más archivos" ayuda={`Hasta ${MAX_ARCHIVOS} en total`} />
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={onCancelar} disabled={corriendo} className="flex-1 rounded-2xl border border-line py-3.5 text-sm font-semibold disabled:opacity-60">
          Cancelar
        </button>
        {hayPendientes ? (
          <button
            onClick={procesar}
            disabled={corriendo || archivos.length === 0}
            className="flex-1 bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold disabled:opacity-60"
          >
            {corriendo ? 'Procesando...' : `Procesar ${archivos.filter((a) => a.estado === 'pendiente').length} ${archivos.filter((a) => a.estado === 'pendiente').length === 1 ? 'archivo' : 'archivos'}`}
          </button>
        ) : (
          <button
            onClick={irARevision}
            disabled={corriendo || listos.length === 0}
            className="flex-1 bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold disabled:opacity-60"
          >
            Revisar ({listos.length} {listos.length === 1 ? 'archivo' : 'archivos'})
          </button>
        )}
      </div>
    </div>
  )
}
