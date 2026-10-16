import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Check, FileSpreadsheet, FileText, Loader2, X } from 'lucide-react'
import { productoDeTexto, recordarCuenta, textoOpcionCuenta } from '../lib/cuentasBanco'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import PrevioImportacion from './PrevioImportacion'
import CuadreExtracto from './CuadreExtracto'
import { lineasPorImportar } from '../lib/cuadreExtracto'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { AvisoCategorizados } from './CategorizacionAuto'
import AvisoYaConciliado from './AvisoYaConciliado'
import BarraProgreso from './BarraProgreso'
import PropuestaTarjeta from './PropuestaTarjeta'
import RecordarRegla, { RECORDAR_INICIAL } from './RecordarRegla'
import ZonaSubida from './ZonaSubida'
import { opcionesCategoria } from '../lib/importar'
import { claveComercio, huellaPeligrosa } from '../lib/comercio'
import { EMOJI_DEFECTO, estadoCategoria, resumirCategorias } from '../lib/estadoCategoria'
import { CategoriaEnBloque, ChipCategoria, ResumenCategorias } from './RevisionCategorias'
import HojaNuevaCategoria, { OPCION_NUEVA_CATEGORIA, TEXTO_NUEVA_CATEGORIA } from './HojaNuevaCategoria'
import { borrarBorrador, guardarBorrador, leerBorrador, resumenLote } from '../lib/retomar'
import {
  ETIQUETA_ARCHIVO,
  MAX_ARCHIVOS,
  agruparPorCuenta,
  clavesFaltantes,
  clavesUnicas,
  consolidar,
  gemelasNuevas,
  normalizarPdf,
  normalizarTabular,
  procesarCola,
  sugerirCuenta,
  textoDescartados,
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

const nuevoArchivo = (f, cuentas, cuentaInicial) => ({
  id: nuevoId(), file: f, nombre: f.name, tipo: tipoDeArchivo(f.name),
  cuentaId: sugerirCuenta(f.name, cuentas, cuentaInicial), password: '', estado: 'pendiente', error: '',
  banco: '', periodo: null, items: [],
})

/**
 * Subida de extractos y archivos (PDF, Excel, CSV; uno o varios): la zona única detecta el tipo
 * por la extensión y manda cada archivo a su lector. Cola (uno tras otro, un fallo no frena a
 * los demás), UNA revisión consolidada agrupada por cuenta y archivo, y UNA confirmación que
 * importa lo marcado, aplica las categorías y guarda las reglas que el usuario quiso recordar.
 *
 * `revisionInicial={{ historialId }}` abre directo la revisión de un extracto ya procesado
 * (el de un correo, un enlace o una notificación) sin volver a subir nada.
 */
const TANDA_FILAS = 100

export default function SubidaMultiple({
  archivosIniciales = [], cuentaInicial = '', revisionInicial = null, onCancelar, onImportado, onManual,
}) {
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const catsCtx = useCategorias()
  const CATEGORIAS = catsCtx?.nombres || []
  const iconoDe = catsCtx?.iconoDe || (() => EMOJI_DEFECTO)
  const [avisoBloque, setAvisoBloque] = useState('')
  const [creandoPara, setCreandoPara] = useState(null) // { clave, it }: fila que está creando una categoría nueva
  const [archivos, setArchivos] = useState(() => {
    const { aceptados } = validarSeleccion(archivosIniciales)
    return aceptados.map((f) => nuevoArchivo(f, cuentas, cuentaInicial))
  })
  const [rechazados, setRechazados] = useState(() => validarSeleccion(archivosIniciales).rechazados)
  const [progreso, setProgreso] = useState({ actual: 0, total: 0 })
  const [corriendo, setCorriendo] = useState(false)
  const [fase, setFase] = useState(revisionInicial?.historialId ? 'abriendo' : 'cola') // abriendo | cola | revision | resultado
  const [seleccion, setSeleccion] = useState(new Set())
  const [categorias, setCategorias] = useState({})
  const [aprender, setAprender] = useState({}) // clave -> { recordar, anteriores } (solo filas editadas)
  const [importando, setImportando] = useState(false)
  const [resultados, setResultados] = useState([])
  const [error, setError] = useState('')
  // Con archivos de miles de filas, pintar todas congela el celular: se muestran por tandas.
  const [filasMostradas, setFilasMostradas] = useState({}) // id de archivo -> cuántas filas se pintan
  const archivosRef = useRef(archivos)
  archivosRef.current = archivos
  const montado = useRef(true)
  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
    }
  }, [])

  const consolidado = useMemo(() => consolidar(archivos), [archivos])
  const listos = consolidado.archivos.filter((a) => a.estado === 'listo')
  const hayPendientes = archivos.some((a) => a.estado === 'pendiente')
  const nombreCuenta = (id) => cuentas.find((c) => c.id === id)?.nombre || 'Cuenta'

  // Borrador de la revisión: cada cambio (marcas, categorías, reglas) se guarda por extracto, así salir y volver no pierde nada.
  useEffect(() => {
    if (fase !== 'revision') return
    for (const a of archivosRef.current) {
      if (a.estado !== 'listo' || !a.historialId) continue
      const pref = `${a.id}:`
      const quitar = (o) => Object.fromEntries(Object.entries(o).filter(([c]) => c.startsWith(pref)).map(([c, v]) => [c.slice(pref.length), v]))
      guardarBorrador(a.historialId, {
        seleccion: [...seleccion].filter((c) => c.startsWith(pref)).map((c) => c.slice(pref.length)),
        categorias: quitar(categorias),
        aprender: quitar(aprender),
      })
    }
  }, [fase, seleccion, categorias, aprender])

  const parchar = (id, parche) => setArchivos((prev) => prev.map((a) => (a.id === id ? { ...a, ...parche } : a)))

  function empezarRevision(lista) {
    const sel = new Set(clavesFaltantes(lista))
    const cats = {}
    const apr = {}
    for (const a of lista) {
      if (a.estado !== 'listo') continue
      for (const it of a.items) cats[`${a.id}:${it.k}`] = it.categoria || 'Otros'
      // Revisión que se dejó a medias (salió a crear una categoría, cerró la app...): vuelve como estaba.
      const b = a.historialId ? leerBorrador(a.historialId) : null
      if (!b) continue
      const validas = new Set(a.items.map((it) => it.k))
      for (const it of a.items) sel.delete(`${a.id}:${it.k}`)
      for (const k of b.seleccion) if (validas.has(k)) sel.add(`${a.id}:${k}`)
      for (const [k, v] of Object.entries(b.categorias)) if (validas.has(k)) cats[`${a.id}:${k}`] = v
      for (const [k, v] of Object.entries(b.aprender)) if (validas.has(k)) apr[`${a.id}:${k}`] = v
    }
    setSeleccion(sel)
    setCategorias(cats)
    setAprender(apr)
    setFase('revision')
  }

  // Revisión de un extracto que ya se procesó en el servidor (correo, enlace, notificación).
  const historialInicial = revisionInicial?.historialId
  useEffect(() => {
    if (!historialInicial) return
    let vigente = true
    api.obtenerReviewExtracto(historialInicial)
      .then((r) => {
        if (!vigente) return
        const base = normalizarPdf(r)
        const cuentaId = r.cuenta_id || revisionInicial?.cuentaId || cuentaInicial || cuentas[0]?.id || ''
        const a = {
          id: nuevoId(), file: null, nombre: `Extracto ${base.banco}`, tipo: 'pdf', cuentaId, password: '',
          estado: 'listo', error: '', nMov: r.total_movimientos, ...base,
        }
        setArchivos([a])
        empezarRevision([a])
      })
      .catch(() => {
        if (!vigente) return
        setError('No se pudo abrir la revisión del extracto.')
        setFase('cola')
      })
    return () => {
      vigente = false
    }
    // solo al montar: la revisión inicial no cambia mientras el componente vive
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historialInicial])

  function agregar(files) {
    const { aceptados, rechazados: rech } = validarSeleccion(files, archivos.length)
    setRechazados(rech)
    setArchivos((prev) => [...prev, ...aceptados.map((f) => nuevoArchivo(f, cuentas, cuentaInicial))])
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
      throw new Error('No reconocimos las columnas de este archivo.')
    }
    return { estado: 'listo', error: '', ...n, nMov: n.items.length }
  }

  async function procesar() {
    setCorriendo(true)
    setError('')
    await procesarCola(archivosRef.current, procesarUno, { onCambio: parchar, onProgreso: setProgreso })
    if (montado.current) setCorriendo(false)
  }

  function reintentar(a) {
    parchar(a.id, { estado: 'pendiente', error: '' })
    // el estado se aplica al terminar el render; la cola lee archivosRef
    setTimeout(procesar, 0)
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

  // «¿Es el mismo gasto?»: sí -> se junta con lo que ya tenías (no se duplica); no -> queda como nuevo.
  async function decidirDudosos(a, lista, decision) {
    const ks = new Set(lista.map((i) => i.k))
    if (a.tipo === 'pdf' && a.historialId) {
      const fps = lista.map((i) => i.fp)
      await api.resolverDudosos(a.historialId, decision === 'mismo' ? fps : [], decision === 'otro' ? fps : [])
    }
    parchar(a.id, {
      items: a.items.map((it) => (ks.has(it.k) && it.estado === 'dudoso'
        ? { ...it, estado: decision === 'mismo' ? 'ya' : 'nuevo', conciliarCon: decision === 'mismo' ? it.matchId : null }
        : it)),
    })
    if (decision === 'otro') {
      setSeleccion((prev) => {
        const next = new Set(prev)
        for (const k of ks) next.add(`${a.id}:${k}`)
        return next
      })
    }
  }

  const totalJuntar = consolidado.archivos.reduce((n, a) => n + (a.estado === 'listo' && a.tipo !== 'pdf' ? a.items.filter((it) => it.conciliarCon).length : 0), 0)
  const totalMarcados = consolidado.archivos.reduce(
    (n, a) => n + (a.estado === 'listo' ? a.items.filter((it) => seleccion.has(`${a.id}:${it.k}`) && (it.estado === 'nuevo' || it.estado === 'posible')).length : 0),
    0
  )
  const totalFaltan = clavesFaltantes(consolidado.archivos).length

  // Líneas que se pueden importar (las ya registradas, repetidas o anteriores al inicio no cuentan).
  const lineasPendientes = consolidado.archivos.flatMap((a) =>
    a.estado !== 'listo' ? [] : a.items
      .filter((it) => it.estado === 'nuevo' || it.estado === 'posible')
      .map((it) => ({ clave: `${a.id}:${it.k}`, it }))
  )
  const estadoDeLinea = (clave, it) => estadoCategoria(it, categorias[clave])
  const resumenCats = resumirCategorias(lineasPendientes.map(({ clave, it }) => estadoDeLinea(clave, it)))
  const marcadas = lineasPendientes.filter(({ clave }) => seleccion.has(clave))

  function marcarPorEstado(estado) {
    setSeleccion(new Set(lineasPendientes.filter(({ clave, it }) => estadoDeLinea(clave, it) === estado).map(({ clave }) => clave)))
  }

  // Una categoría para todas las marcadas; con «recordar», una regla por comercio (la misma
  // regla de siempre: nada se guarda hasta confirmar la importación).
  function aplicarEnBloque(categoria, recordar) {
    const sinRegla = recordar
      ? marcadas.filter(({ it }) => categoria !== (it.categoria || 'Otros') && huellaPeligrosa(claveComercio(it.descripcion))).length
      : 0
    setCategorias((c) => ({ ...c, ...Object.fromEntries(marcadas.map(({ clave }) => [clave, categoria])) }))
    setAprender((prev) => {
      const next = { ...prev }
      for (const { clave, it } of marcadas) {
        if (categoria === (it.categoria || 'Otros') || !recordar) delete next[clave]
        else if (huellaPeligrosa(claveComercio(it.descripcion))) delete next[clave]
        else next[clave] = { recordar: true, anteriores: false }
      }
      return next
    })
    setAvisoBloque(
      !recordar
        ? 'Listo: la categoría se aplicó solo a esta revisión.'
        : sinRegla
          ? `Listo. Guardo la regla al importar; en ${sinRegla} no puedo (nombre muy genérico) y queda solo para este extracto.`
          : 'Listo. Guardo la regla de cada comercio cuando importes.'
    )
  }

  async function importar() {
    setImportando(true)
    setError('')
    const salida = []
    for (const a of consolidado.archivos) {
      if (a.estado !== 'listo') continue
      const marcados = a.items.filter((it) => seleccion.has(`${a.id}:${it.k}`) && (it.estado === 'nuevo' || it.estado === 'posible'))
      if (marcados.length === 0 && !(a.tipo !== 'pdf' && a.items.some((it) => it.conciliarCon))) continue
      const rec = (it) => aprender[`${a.id}:${it.k}`]
      try {
        let r
        if (a.tipo === 'pdf') {
          // El servidor importa por huella: las filas idénticas se importan juntas, se envía una vez.
          const ks = [...new Set(marcados.map((it) => it.k))]
          const cats = Object.fromEntries(ks.map((k) => [k, categorias[`${a.id}:${k}`] || 'Otros']))
          r = await api.importarFaltantes(a.historialId, ks, cats, {
            recordar: ks.filter((k) => aprender[`${a.id}:${k}`]?.recordar),
            aplicar_anteriores: ks.filter((k) => aprender[`${a.id}:${k}`]?.recordar && aprender[`${a.id}:${k}`]?.anteriores),
          })
        } else {
          const mismos = a.items.filter((it) => it.conciliarCon)
          r = await api.importarConfirmar({
            cuenta_id: a.cuentaId,
            nombre_archivo: a.nombre,
            ajustar_saldo: true,
            filas: [...mismos.map((it) => ({
              fecha: it.fecha, descripcion: it.descripcion, monto: it.monto, tipo: it.tipo, conciliar_con: it.conciliarCon,
            })), ...marcados.map((it) => ({
              fecha: it.fecha, descripcion: it.descripcion, monto: it.monto, tipo: it.tipo,
              categoria: categorias[`${a.id}:${it.k}`] || 'Otros',
              recordar: !!rec(it)?.recordar, aplicar_anteriores: !!(rec(it)?.recordar && rec(it)?.anteriores),
            }))],
          })
        }
        if (a.historialId) borrarBorrador(a.historialId) // ya se importó: el borrador no hace falta
        salida.push({ id: a.id, nombre: a.nombre, cuenta: nombreCuenta(a.cuentaId), ok: true, cuentaId: a.cuentaId, historialId: a.historialId, saldosExtracto: a.saldosExtracto, ...r })
      } catch (err) {
        salida.push({ id: a.id, nombre: a.nombre, cuenta: nombreCuenta(a.cuentaId), ok: false, error: err.message || 'No se pudo importar' })
      }
    }
    await recargarCuentas()
    if (!montado.current) return
    setResultados(salida)
    setFase('resultado')
    setImportando(false)
    onImportado?.(salida)
  }

  // ── Abriendo una revisión guardada ─────────────────────────
  if (fase === 'abriendo') {
    return (
      <p className="text-sm text-ink-soft py-6 text-center" role="status">Abriendo la revisión…</p>
    )
  }

  // ── Resultado ──────────────────────────────────────────────
  if (fase === 'resultado') {
    const totalImportados = resultados.reduce((n, r) => n + (r.importados || 0), 0)
    const totalAuto = resultados.reduce((n, r) => n + (r.categorizados_auto || 0), 0)
    const reglas = resultados.reduce((n, r) => n + (r.reglas_guardadas || 0), 0)
    return (
      <div className="mt-2" data-testid="resultado-multiple" role="status">
        <div className="text-center">
          <div className="w-14 h-14 rounded-full bg-accent-soft text-accent flex items-center justify-center mx-auto mb-3">
            <Check size={24} aria-hidden="true" />
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
        <ul className="mt-4 rounded-2xl bg-paper border border-line divide-y divide-line overflow-hidden">
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
        {resultados.filter((r) => r.ok && (r.historialId || r.saldosExtracto)).map((r) => (
          <CuadreExtracto key={`cuadre-${r.id}`} cuentaId={r.cuentaId} historialId={r.historialId} saldos={r.saldosExtracto} despues className="mt-4" />
        ))}
        <AvisoCategorizados n={totalAuto} className="mt-4" />
        <div className="flex gap-2 mt-5">
          <button onClick={onCancelar} className="flex-1 rounded-2xl border border-line py-3 text-sm font-semibold">Subir otros</button>
          <Link
            to={totalAuto > 0 ? '/movimientos?revisar=1' : '/movimientos'}
            replace
            className="flex-1 bg-ink text-paper rounded-2xl py-3 text-sm font-semibold text-center"
          >
            {totalAuto > 0 ? 'Revisar lo categorizado' : 'Ver movimientos'}
          </Link>
        </div>
      </div>
    )
  }

  // ── Revisión consolidada ───────────────────────────────────
  if (fase === 'revision') {
    const grupos = agruparPorCuenta(consolidado.archivos)
    return (
      <div className="mt-2" data-testid="revision-multiple">
        <div className="rounded-2xl bg-paper border border-line p-4 mb-3 grid grid-cols-3 gap-2 text-center">
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
            Lo que aparece en dos extractos (periodos que se solapan) se cuenta una sola vez.
          </p>
        )}

        {resumenLote(archivos) && (
          <p className="text-sm font-semibold mb-3" data-testid="resumen-lote">{resumenLote(archivos)}</p>
        )}
        <ResumenCategorias resumen={resumenCats} onMarcar={marcarPorEstado} className="mb-3" />

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

        <CategoriaEnBloque
          cantidad={marcadas.length}
          nombres={CATEGORIAS}
          iconoDe={iconoDe}
          onAplicar={aplicarEnBloque}
          aviso={avisoBloque}
          className="mb-4"
        />

        {grupos.map((g) => (
          <section key={g.cuentaId} className="mb-5" aria-label={`Cuenta ${nombreCuenta(g.cuentaId)}`}>
            <h3 className="text-sm font-semibold mb-2">{nombreCuenta(g.cuentaId)}</h3>
            {g.archivos.map((a) => {
              const dudosos = a.items.filter((it) => it.estado === 'dudoso').length
              const visibles = a.items.filter((it) => it.estado !== 'ya' && it.estado !== 'anterior' && it.estado !== 'dudoso')
              const anteriores = a.items.filter((it) => it.estado === 'anterior').length
              const ya = a.items.length - visibles.length - anteriores - dudosos
              const claves = clavesUnicas(visibles)
              return (
                <div key={a.id} className="mb-3">
                  <p className="text-xs text-ink-soft mb-1.5 truncate">
                    {a.nombre} · {a.banco} · {periodoTexto(a.periodo)}
                    {ya > 0 ? ` · ${ya} ya registrados` : ''}
                  </p>
                  <AvisoYaConciliado info={a.yaConciliado} cuenta={nombreCuenta(a.cuentaId)} className="mb-2" />
                  <PrevioImportacion items={a.items} onDecidir={(lista, d) => decidirDudosos(a, lista, d)} className="mb-2" />
                  <CuadreExtracto cuentaId={a.cuentaId} historialId={a.historialId} saldos={a.saldosExtracto} avisoCuenta={a.avisoCuenta}
                    porImportar={lineasPorImportar(a.items, seleccion, a.id)} className="mb-2" />
                  <PropuestaTarjeta propuesta={a.propuestaTarjeta} cuentaId={a.cuentaId} className="mb-2" />
                  {a.avisoCuenta && (
                    <p className="flex items-start gap-1.5 text-xs font-medium text-accent mb-2" role="status" data-testid="aviso-cuenta">
                      <AlertTriangle size={16} className="shrink-0" aria-hidden="true" />
                      <span>{a.avisoCuenta}</span>
                    </p>
                  )}
                  <AvisoCategorizados n={a.autoImportados} className="mb-2" />
                  {anteriores > 0 && (
                    <p className="rounded-2xl bg-paper-raised border border-line px-3.5 py-2.5 text-xs mb-2" role="status" data-testid="aviso-anteriores">
                      {anteriores === 1
                        ? '1 línea es anterior a tu fecha de inicio y no se importa.'
                        : `${anteriores} líneas son anteriores a tu fecha de inicio y no se importan.`}
                    </p>
                  )}
                  {a.descartados > 0 && (
                    <p className="rounded-2xl bg-accent-soft px-3.5 py-2.5 text-xs mb-2" role="status" data-testid="aviso-descartados">
                      {textoDescartados(a.descartados)}
                    </p>
                  )}
                  {a.completados?.length > 0 && (
                    <div role="status" className="rounded-2xl bg-accent-soft px-3.5 py-2.5 text-xs mb-2">
                      <p className="font-semibold">
                        Completé {a.completados.length} {a.completados.length === 1 ? 'movimiento' : 'movimientos'} con tu extracto
                      </p>
                      {a.completados.filter((c) => c.montoRegistrado != null && c.montoRegistrado !== c.monto).map((c, i) => (
                        <p key={i} className="text-danger mt-1">
                          {c.descripcion}: anotaste {formatCOP(c.montoRegistrado)} y el banco dice {formatCOP(c.monto)}. Revisa el monto.
                        </p>
                      ))}
                    </div>
                  )}
                  {visibles.length === 0 ? (
                    <p className="text-xs text-ink-soft rounded-2xl border border-line bg-paper px-4 py-3">Todo lo de este archivo ya estaba registrado.</p>
                  ) : (
                    <div className="rounded-2xl bg-paper border border-line divide-y divide-line overflow-hidden">
                      {visibles.slice(0, filasMostradas[a.id] || TANDA_FILAS).map((it, idx) => {
                        const clave = `${a.id}:${it.k}`
                        const marcado = seleccion.has(clave)
                        const repetido = it.estado === 'repetido'
                        const gemelas = gemelasNuevas(visibles, it.k)
                        return (
                          <div key={`${a.id}:${claves[idx]}`} className="px-4 py-3">
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
                                <p className="text-sm font-medium break-words line-clamp-2">{it.descripcion}</p>
                                <p className="text-xs text-danger">
                                  {it.fecha} ·{' '}
                                  {repetido ? `Ya está en ${it.repetidoDe}` : it.estado === 'posible' ? 'Posible duplicado' : 'Falta registrar'}
                                  {it.estado === 'nuevo' && gemelas > 1 ? ` · idéntico a otros ${gemelas - 1} (se importan juntos)` : ''}
                                </p>
                                {!repetido && (
                                  <ChipCategoria
                                    className="mt-1"
                                    categoria={categorias[clave] || it.categoria || 'Otros'}
                                    emoji={iconoDe(categorias[clave] || it.categoria || 'Otros')}
                                    estado={estadoDeLinea(clave, it)}
                                  />
                                )}
                              </div>
                              <p className="text-sm font-semibold shrink-0">
                                {it.tipo === 'income' ? '+' : it.tipo === 'transfer' ? '' : '-'}
                                {formatCOP(it.monto)}
                              </p>
                            </label>
                            {marcado && !repetido && (
                              <div className="ml-8 mt-2">
                                <select
                                  aria-label={`Categoría de ${it.descripcion}`}
                                  value={categorias[clave] || 'Otros'}
                                  onChange={(e) => (e.target.value === OPCION_NUEVA_CATEGORIA ? setCreandoPara({ clave, it }) : cambiarCategoria(clave, it, e.target.value))}
                                  className="w-full rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs"
                                >
                                  {opcionesCategoria(CATEGORIAS, categorias[clave]).map((c) => (
                                    <option key={c} value={c}>{iconoDe(c)} {c}</option>
                                  ))}
                                  <option value={OPCION_NUEVA_CATEGORIA}>{TEXTO_NUEVA_CATEGORIA}</option>
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
                      {visibles.length > (filasMostradas[a.id] || TANDA_FILAS) && (
                        <button
                          type="button"
                          onClick={() => setFilasMostradas((p) => ({ ...p, [a.id]: (p[a.id] || TANDA_FILAS) + TANDA_FILAS }))}
                          className="w-full min-h-[44px] text-sm font-semibold text-accent"
                        >
                          Mostrar {Math.min(TANDA_FILAS, visibles.length - (filasMostradas[a.id] || TANDA_FILAS))} más (faltan {visibles.length - (filasMostradas[a.id] || TANDA_FILAS)})
                        </button>
                      )}
                    </div>
                  )}
                  {a.sobrantes?.length > 0 && (
                    <details className="mt-2 rounded-2xl border border-line bg-paper px-3.5 py-2.5">
                      <summary className="text-xs font-semibold cursor-pointer">
                        {a.sobrantes.length} {a.sobrantes.length === 1 ? 'registrado no aparece' : 'registrados no aparecen'} en el extracto
                      </summary>
                      <ul className="mt-2 space-y-1">
                        {a.sobrantes.map((s, i) => (
                          <li key={i} className="text-xs text-ink-soft flex justify-between gap-2">
                            <span className="truncate">{s.fecha} · {s.descripcion}</span>
                            <span className="shrink-0">{formatCOP(s.monto)}</span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )
            })}
          </section>
        ))}

        {creandoPara && (
          <HojaNuevaCategoria
            onCerrar={() => setCreandoPara(null)}
            onCreada={(nombre) => cambiarCategoria(creandoPara.clave, creandoPara.it, nombre)}
          />
        )}
        {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
        <div className="flex gap-2">
          <button onClick={revisionInicial ? onCancelar : () => setFase('cola')} className="flex-1 rounded-2xl border border-line py-3 text-sm font-semibold">
            {revisionInicial ? 'Cerrar' : 'Atrás'}
          </button>
          <button
            onClick={importar}
            disabled={(totalMarcados === 0 && totalJuntar === 0) || importando}
            className="flex-1 bg-ink text-paper rounded-2xl py-3 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
          >
            <Check size={16} aria-hidden="true" /> {importando ? 'Importando...' : `Importar (${totalMarcados})`}
          </button>
        </div>
      </div>
    )
  }

  // ── Cola ───────────────────────────────────────────────────
  const pctCola = progreso.total ? Math.round(((progreso.actual - 1) / progreso.total) * 100) : 0
  return (
    <div className="mt-2" data-testid="cola-multiple">
      <div aria-live="polite" role="status" className={corriendo && progreso.total > 0 ? 'mb-3' : ''}>
        {corriendo && progreso.total > 0 && (
          <>
            <p className="text-sm font-semibold">
              Archivo {progreso.actual} de {progreso.total}
            </p>
            <BarraProgreso pct={pctCola} label="Progreso de la subida" className="h-1.5 mt-1.5 rounded-full bg-line overflow-hidden" fillClass="" />
          </>
        )}
      </div>

      <ul className="space-y-2.5 mb-4">
        {archivos.map((a) => {
          const Icono = a.tipo === 'pdf' ? FileText : FileSpreadsheet
          return (
            <li key={a.id} className="rounded-2xl bg-paper border border-line p-3.5" data-estado={a.estado}>
              <div className="flex items-start gap-3">
                <Icono size={20} className="text-accent shrink-0 mt-0.5" aria-hidden="true" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{a.nombre}</p>
                  <p className={`text-xs mt-0.5 flex items-center gap-1 ${a.estado === 'error' || a.estado === 'falta_clave' ? 'text-danger' : a.estado === 'listo' ? 'text-accent' : 'text-ink-soft'}`}>
                    {a.estado === 'procesando' && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                    {a.estado === 'error' || a.estado === 'falta_clave' ? <AlertTriangle size={16} aria-hidden="true" /> : null}
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
                    <X size={16} aria-hidden="true" />
                  </button>
                )}
              </div>

              {(a.estado === 'pendiente' || a.estado === 'falta_clave' || a.estado === 'error') && cuentas.length > 1 && (
                <label className="block mt-2.5 ml-8">
                  <span className="text-[11px] text-ink-soft">Cuenta</span>
                  <select
                    aria-label={`Cuenta de ${a.nombre}`}
                    value={a.cuentaId}
                    onChange={(e) => { recordarCuenta(cuentas.find((x) => x.id === e.target.value)?.nombre, productoDeTexto(a.nombre), e.target.value); parchar(a.id, { cuentaId: e.target.value }) }}
                    className="w-full mt-0.5 rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs"
                  >
                    {cuentas.map((c) => (
                      <option key={c.id} value={c.id}>{c.icono} {textoOpcionCuenta(c, cuentas)}</option>
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
                    className="flex-1 min-w-0 rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs outline-none focus:border-accent"
                  />
                  <button onClick={() => reintentar(a)} disabled={!a.password || corriendo} className="rounded-xl bg-accent text-paper-raised px-3 text-xs font-semibold disabled:opacity-60">
                    Reintentar
                  </button>
                </div>
              )}
              {a.estado === 'error' && (
                <div className="mt-2 ml-8 flex flex-wrap gap-x-4 gap-y-1">
                  <button onClick={() => reintentar(a)} disabled={corriendo} className="text-xs font-semibold text-accent underline disabled:opacity-60 min-h-[32px]">
                    Reintentar
                  </button>
                  {a.tipo === 'tabular' && onManual && (
                    <button onClick={onManual} className="text-xs font-semibold text-accent underline min-h-[32px]">
                      Elegir las columnas a mano
                    </button>
                  )}
                </div>
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
      {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}

      {archivos.length < MAX_ARCHIVOS && !corriendo && (
        <div className="mb-4">
          <ZonaSubida onArchivos={agregar} titulo="Agregar más archivos" ayuda={`Hasta ${MAX_ARCHIVOS} en total`} />
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={onCancelar} disabled={corriendo} className="flex-1 rounded-2xl border border-line py-3 text-sm font-semibold disabled:opacity-60">
          Cancelar
        </button>
        {hayPendientes ? (
          <button
            onClick={procesar}
            disabled={corriendo || archivos.length === 0}
            className="flex-1 bg-ink text-paper rounded-2xl py-3 text-sm font-semibold disabled:opacity-60"
          >
            {corriendo ? 'Procesando...' : `Procesar ${archivos.filter((a) => a.estado === 'pendiente').length} ${archivos.filter((a) => a.estado === 'pendiente').length === 1 ? 'archivo' : 'archivos'}`}
          </button>
        ) : (
          <button
            onClick={() => empezarRevision(consolidado.archivos)}
            disabled={corriendo || listos.length === 0}
            className="flex-1 bg-ink text-paper rounded-2xl py-3 text-sm font-semibold disabled:opacity-60"
          >
            Revisar ({listos.length} {listos.length === 1 ? 'archivo' : 'archivos'})
          </button>
        )}
      </div>
    </div>
  )
}
