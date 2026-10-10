import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Check, FileSpreadsheet, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { AvisoCategorizados } from '../components/CategorizacionAuto'
import AvisoYaConciliado from '../components/AvisoYaConciliado'
import RecordarRegla, { RECORDAR_INICIAL } from '../components/RecordarRegla'
import ZonaSubida from '../components/ZonaSubida'
import {
  CAMPOS_MAPEO,
  noImportable,
  ETIQUETA_ESTADO,
  MAX_BYTES,
  categoriasIniciales,
  construirFilas,
  efectoSaldo,
  extensionValida,
  opcionesCategoria,
  seleccionInicial,
} from '../lib/importar'

function archivoABase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

const colorEstado = {
  nuevo: 'text-accent',
  posible_duplicado: 'text-danger',
  duplicado: 'text-ink-soft',
  anterior: 'text-ink-soft',
}

// Lectura con columnas elegidas a mano (para un Excel o CSV raro). El flujo normal vive en el
// centro "Traer movimientos"; aquí `embebido` quita el encabezado y `onTerminar` cierra la hoja.
export default function ImportarArchivo({ embebido = false, cuentaInicial = '', onTerminar }) {
  const navigate = useNavigate()
  const volver = useVolver('/movimientos')
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const catsCtx = useCategorias()
  const CATEGORIAS = catsCtx?.nombres || []
  const iconoDe = catsCtx?.iconoDe || (() => '💳')
  const [cuentaId, setCuentaId] = useState(cuentaInicial || cuentas[0]?.id || '')
  const [archivo, setArchivo] = useState(null) // { nombre, base64 }
  const [analisis, setAnalisis] = useState(null) // respuesta de /importar/vista-previa
  const [mapeo, setMapeo] = useState({})
  const [opciones, setOpciones] = useState({})
  const [cambiosSinAplicar, setCambiosSinAplicar] = useState(false)
  const [seleccion, setSeleccion] = useState(new Set())
  const [categorias, setCategorias] = useState({})
  const [ajustarSaldo, setAjustarSaldo] = useState(true)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [resultado, setResultado] = useState(null)
  const [aprender, setAprender] = useState({}) // fila -> { recordar, anteriores } (solo filas editadas)

  function mostrar(r) {
    setAprender({})
    setAnalisis(r)
    setMapeo(r.mapeo)
    setOpciones(r.opciones)
    setCambiosSinAplicar(false)
    setSeleccion(seleccionInicial(r.propuesta))
    setCategorias(categoriasIniciales(r.propuesta))
  }

  async function pedirVistaPrevia(extra = {}, archivoActual = archivo) {
    setError('')
    setCargando(true)
    try {
      const r = await api.importarVistaPrevia({
        cuenta_id: cuentaId,
        nombre_archivo: archivoActual.nombre,
        archivo_base64: archivoActual.base64,
        ...extra,
      })
      mostrar(r)
    } catch (err) {
      setError(err.message || 'No se pudo leer el archivo')
    } finally {
      setCargando(false)
    }
  }

  // Un archivo: el flujo de siempre (con mapeo de columnas). Varios: cola con revisión consolidada.
  async function onArchivos(files) {
    setError('')
    if (files.length > 1) {
      setError('Para elegir las columnas a mano sube un archivo a la vez.')
      return
    }
    const file = files[0]
    if (!file) return
    if (!extensionValida(file.name)) {
      setError('Formato no soportado. Sube un archivo .csv, .xlsx o .xls.')
      return
    }
    if (file.size > MAX_BYTES) {
      setError('El archivo pesa más de 5 MB. Sube un periodo más corto.')
      return
    }
    const nuevo = { nombre: file.name, base64: await archivoABase64(file) }
    setArchivo(nuevo)
    await pedirVistaPrevia({}, nuevo)
  }

  function aplicarCambios() {
    pedirVistaPrevia({
      mapeo,
      separador_decimal: opciones.separador_decimal,
      orden_fecha: opciones.orden_fecha,
      invertir_signo: opciones.invertir_signo,
      fila_encabezado: analisis.fila_encabezado ?? -1,
    })
  }

  function cambiarMapeo(campo, valor) {
    setMapeo((m) => ({ ...m, [campo]: valor === '' ? null : Number(valor) }))
    setCambiosSinAplicar(true)
  }

  function cambiarOpcion(clave, valor) {
    setOpciones((o) => ({ ...o, [clave]: valor }))
    setCambiosSinAplicar(true)
  }

  function alternar(fila) {
    setSeleccion((prev) => {
      const next = new Set(prev)
      if (next.has(fila)) next.delete(fila)
      else next.add(fila)
      return next
    })
  }

  const filas = analisis ? construirFilas(analisis.propuesta, seleccion, categorias, aprender) : []

  function cambiarCategoria(p, categoria) {
    setCategorias((c) => ({ ...c, [p.fila]: categoria }))
    setAprender((prev) => {
      const next = { ...prev }
      if (categoria === (p.categoria || 'Otros')) delete next[p.fila]
      else next[p.fila] = next[p.fila] || RECORDAR_INICIAL // «Recordar» marcado por defecto
      return next
    })
  }
  const cuenta = cuentas.find((c) => c.id === cuentaId)

  async function importar() {
    setCargando(true)
    setError('')
    try {
      const r = await api.importarConfirmar({
        cuenta_id: cuentaId,
        nombre_archivo: archivo.nombre,
        filas,
        ajustar_saldo: ajustarSaldo,
      })
      await recargarCuentas()
      setResultado(r)
    } catch (err) {
      setError(err.message || 'No se pudo importar')
    } finally {
      setCargando(false)
    }
  }

  function reiniciar() {
    setArchivo(null)
    setAnalisis(null)
    setResultado(null)
    setError('')
  }

  return (
    <div className={embebido ? '' : 'flex-1 overflow-y-auto pb-8 screen-enter'}>
      {!embebido && (
        <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
          <button
            onClick={volver}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
            aria-label="Volver"
          >
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-semibold">Importar Excel o CSV</h1>
        </header>
      )}

      {resultado && (
        <div className="px-5 mt-6 text-center">
          <div className="w-14 h-14 rounded-full bg-accent-soft text-accent flex items-center justify-center mx-auto mb-3">
            <Check size={26} />
          </div>
          <p className="text-lg font-semibold">
            {resultado.importados} {resultado.importados === 1 ? 'movimiento importado' : 'movimientos importados'}
          </p>
          {resultado.duplicados_omitidos > 0 && (
            <p className="text-sm text-ink-soft mt-1">
              Omitimos {resultado.duplicados_omitidos} que ya estaban registrados.
            </p>
          )}
          <AvisoCategorizados n={resultado.categorizados_auto} className="mt-4 text-left" />
          <div className="flex gap-2 mt-6">
            <button onClick={reiniciar} className="flex-1 rounded-2xl border border-line py-3.5 text-sm font-semibold">
              Importar otro
            </button>
            <button
              onClick={() => (embebido ? onTerminar?.(resultado) : navigate('/movimientos', { replace: true }))}
              className="flex-1 bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold"
            >
              {embebido ? 'Listo' : 'Ver movimientos'}
            </button>
          </div>
        </div>
      )}

      {!analisis && !resultado && (
        <div className="px-5 mt-4">
          <p className="text-sm text-ink-soft mb-4">
            Sube el Excel o CSV que te da tu banco, o uno tuyo. Detectamos las columnas, tú las revisas y
            confirmas antes de guardar. No se guarda nada hasta que presiones Importar.
          </p>

          {cuentas.length > 1 && (
            <div className="mb-3">
              <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">¿A qué cuenta pertenece?</p>
              <div className="flex gap-2 overflow-x-auto no-scrollbar">
                {cuentas.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setCuentaId(c.id)}
                    className={`shrink-0 text-sm px-4 py-1.5 rounded-full border ${
                      cuentaId === c.id ? 'bg-accent text-paper-raised border-accent' : 'border-line text-ink-soft'
                    }`}
                  >
                    {c.icono} {c.nombre}
                  </button>
                ))}
              </div>
            </div>
          )}

          <ZonaSubida
            onArchivos={onArchivos}
            disabled={cargando}
            icono={FileSpreadsheet}
            titulo={cargando ? 'Leyendo archivo...' : 'Toca para elegir los archivos'}
            ayuda=".csv, .xlsx o .xls · un archivo, hasta 5 MB"
            ariaLabel="Archivo a importar"
          />

          <ul className="text-xs text-ink-soft mt-4 space-y-1 list-disc pl-4">
            <li>Entendemos montos como 1.234.567,89 o 1,234,567.89 y fechas dd/mm/aaaa.</li>
            <li>Funciona con una columna de monto con signo o con columnas separadas de débito y crédito.</li>
            <li>Si algún movimiento ya existe, te lo marcamos para que no se duplique.</li>
          </ul>

          {error && <p className="text-sm text-danger mt-4" role="alert">{error}</p>}
        </div>
      )}

      {analisis && !resultado && (
        <div className="px-5 mt-3">
          <p className="text-xs text-ink-soft mb-3">
            {archivo?.nombre} · cuenta {cuenta?.nombre} · {analisis.total_filas} filas leídas
          </p>
          <AvisoYaConciliado info={analisis.ya_conciliado} cuenta={cuenta?.nombre} className="mb-4" />

          <section className="rounded-2xl bg-paper-raised border border-line p-4 mb-4">
            <h2 className="text-sm font-semibold mb-1">1. Revisa las columnas</h2>
            <p className="text-xs text-ink-soft mb-3">Cambia lo que no esté bien. Si el banco separa débito y crédito, deja "Monto" sin usar.</p>
            <div className="grid grid-cols-1 gap-2">
              {CAMPOS_MAPEO.map((campo) => (
                <label key={campo.id} className="flex items-center gap-3">
                  <span className="text-xs font-medium w-32 shrink-0">{campo.etiqueta}</span>
                  <select
                    aria-label={campo.etiqueta}
                    value={mapeo[campo.id] ?? ''}
                    onChange={(e) => cambiarMapeo(campo.id, e.target.value)}
                    className="flex-1 min-w-0 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                  >
                    <option value="">— No usar —</option>
                    {analisis.columnas.map((c) => (
                      <option key={c.indice} value={c.indice}>
                        {c.indice + 1}. {c.nombre}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-2 mt-3">
              <label className="text-xs">
                <span className="block text-ink-soft mb-1">Decimales</span>
                <select
                  aria-label="Separador decimal"
                  value={opciones.separador_decimal || 'auto'}
                  onChange={(e) => cambiarOpcion('separador_decimal', e.target.value)}
                  className="w-full rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                >
                  <option value="auto">Automático</option>
                  <option value="coma">Coma (1.234,56)</option>
                  <option value="punto">Punto (1,234.56)</option>
                </select>
              </label>
              <label className="text-xs">
                <span className="block text-ink-soft mb-1">Fechas</span>
                <select
                  aria-label="Orden de fecha"
                  value={opciones.orden_fecha || 'dmy'}
                  onChange={(e) => cambiarOpcion('orden_fecha', e.target.value)}
                  className="w-full rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                >
                  <option value="dmy">Día/mes/año</option>
                  <option value="mdy">Mes/día/año</option>
                </select>
              </label>
            </div>
            <label className="flex items-start gap-2 mt-3 text-xs">
              <input
                type="checkbox"
                checked={!!opciones.invertir_signo}
                onChange={(e) => cambiarOpcion('invertir_signo', e.target.checked)}
                className="w-4 h-4 mt-0.5 accent-accent"
              />
              <span>Las compras vienen en positivo (típico de extractos de tarjeta de crédito): invertir el signo</span>
            </label>

            {analisis.muestra.length > 0 && (
              <div className="mt-4 overflow-x-auto rounded-xl border border-line">
                <table className="text-[11px] w-full">
                  <thead className="bg-paper">
                    <tr>
                      {analisis.columnas.map((c) => (
                        <th key={c.indice} className="text-left font-medium px-2 py-1.5 whitespace-nowrap">{c.nombre}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {analisis.muestra.map((fila, i) => (
                      <tr key={i} className="border-t border-line">
                        {analisis.columnas.map((c) => (
                          <td key={c.indice} className="px-2 py-1.5 whitespace-nowrap text-ink-soft">{fila[c.indice]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {cambiosSinAplicar && (
              <button
                onClick={aplicarCambios}
                disabled={cargando}
                className="mt-3 w-full rounded-2xl bg-accent text-paper-raised py-3 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
              >
                <RefreshCw size={16} /> {cargando ? 'Actualizando...' : 'Actualizar vista previa'}
              </button>
            )}
          </section>

          <section className="mb-4">
            <h2 className="text-sm font-semibold mb-2">2. Confirma qué se importa</h2>
            <div className="rounded-2xl bg-paper-raised border border-line p-3 mb-3 grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-lg font-bold text-accent">{analisis.resumen.nuevos}</p>
                <p className="text-xs text-ink-soft">Nuevos</p>
              </div>
              <div>
                <p className="text-lg font-bold text-danger">{analisis.resumen.posibles_duplicados}</p>
                <p className="text-xs text-ink-soft">Posibles duplicados</p>
              </div>
              <div>
                <p className="text-lg font-bold">{analisis.resumen.duplicados}</p>
                <p className="text-xs text-ink-soft">Ya registrados</p>
              </div>
            </div>

            {analisis.truncado && (
              <p className="text-xs text-danger mb-2">El archivo tiene más de 3.000 movimientos: solo se leen los primeros 3.000.</p>
            )}
            {analisis.errores.length > 0 && (
              <div className="rounded-2xl bg-accent-soft p-3.5 mb-3">
                <p className="text-xs text-ink">
                  {analisis.resumen.con_error} {analisis.resumen.con_error === 1 ? 'fila no se pudo leer' : 'filas no se pudieron leer'}{' '}
                  (por ejemplo la fila {analisis.errores[0].fila}: {analisis.errores[0].motivo.toLowerCase()}). Revisa el mapeo de columnas.
                </p>
              </div>
            )}

            {analisis.propuesta.length === 0 ? (
              <p className="text-sm text-ink-soft text-center py-6">No encontramos movimientos con este mapeo. Ajusta las columnas de arriba.</p>
            ) : (
              <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                {analisis.propuesta.map((p) => (
                  <div key={p.fila} className="px-4 py-3">
                    <label className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={seleccion.has(p.fila) && !noImportable(p)}
                        disabled={noImportable(p)}
                        onChange={() => alternar(p.fila)}
                        className="w-5 h-5 accent-accent shrink-0"
                        aria-label={`Importar ${p.descripcion}`}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{p.descripcion}</p>
                        <p className={`text-xs ${colorEstado[p.estado]}`}>
                          {p.fecha} · {ETIQUETA_ESTADO[p.estado]}
                        </p>
                      </div>
                      <p className="text-sm font-semibold shrink-0">
                        {p.tipo === 'income' ? '+' : '-'}
                        {formatCOP(p.monto)}
                      </p>
                    </label>
                    {seleccion.has(p.fila) && !noImportable(p) && (
                      <>
                        <select
                          aria-label={`Categoría de ${p.descripcion}`}
                          value={categorias[p.fila] || 'Otros'}
                          onChange={(e) => cambiarCategoria(p, e.target.value)}
                          className="mt-2 ml-8 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                          style={{ width: 'calc(100% - 2rem)' }}
                        >
                          {opcionesCategoria(CATEGORIAS, categorias[p.fila]).map((c) => (
                            <option key={c} value={c}>{iconoDe(c)} {c}</option>
                          ))}
                        </select>
                        <div className="ml-8 mt-1.5">
                          {p.razon_categoria && !aprender[p.fila] && (
                            <p className="text-[11px] text-ink-soft">Auto · {p.razon_categoria}</p>
                          )}
                          {aprender[p.fila] && (
                            <RecordarRegla
                              descripcion={p.descripcion}
                              valor={aprender[p.fila]}
                              onChange={(v) => setAprender((prev) => ({ ...prev, [p.fila]: v }))}
                            />
                          )}
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          <label className="flex items-start gap-2 text-xs mb-4">
            <input
              type="checkbox"
              checked={ajustarSaldo}
              onChange={(e) => setAjustarSaldo(e.target.checked)}
              className="w-4 h-4 mt-0.5 accent-accent"
            />
            <span>
              Ajustar el saldo de {cuenta?.nombre} con estos movimientos
              {filas.length > 0 && (
                <> ({efectoSaldo(filas) >= 0 ? '+' : '-'}{formatCOP(Math.abs(efectoSaldo(filas)))})</>
              )}
              . Desmárcalo si el saldo de la cuenta ya incluye estos movimientos.
            </span>
          </label>

          {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}

          <div className="flex gap-2">
            <button onClick={reiniciar} className="flex-1 rounded-2xl border border-line py-3.5 text-sm font-semibold">
              Cancelar
            </button>
            <button
              onClick={importar}
              disabled={filas.length === 0 || cargando || cambiosSinAplicar}
              className="flex-1 bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <Check size={16} /> {cargando ? 'Importando...' : `Importar (${filas.length})`}
            </button>
          </div>
          {cambiosSinAplicar && <p className="text-xs text-ink-soft mt-2 text-center">Actualiza la vista previa antes de importar.</p>}
        </div>
      )}
    </div>
  )
}
