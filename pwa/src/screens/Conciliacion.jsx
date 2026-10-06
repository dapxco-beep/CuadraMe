import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Check, FileSpreadsheet, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { AvisoCategorizados } from '../components/CategorizacionAuto'
import AvisoYaConciliado from '../components/AvisoYaConciliado'
import RecordarRegla, { RECORDAR_INICIAL } from '../components/RecordarRegla'
import SubidaMultiple from '../components/SubidaMultiple'
import ZonaSubida from '../components/ZonaSubida'
import { useDialogos } from '../lib/DialogosContext'
import { tipoDeArchivo } from '../lib/subidaMultiple'

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result.split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

const estadoLabel = {
  exacto: 'Ya registrado',
  aproximado: 'Ya registrado (aprox.)',
  faltante: 'Falta registrar',
  importado: 'Importado',
  completado: 'Completado con el banco',
  sobrante: 'No aparece en el extracto',
}

const estadoColor = {
  exacto: 'text-ink-soft',
  aproximado: 'text-ink-soft',
  faltante: 'text-danger',
  importado: 'text-accent',
  completado: 'text-accent',
  sobrante: 'text-danger',
}

// Las listas de la revisión, en el orden en que le sirven al usuario.
export const SECCIONES = [
  {
    id: 'completados',
    estados: ['completado'],
    titulo: 'Completados con el banco',
    ayuda: 'Los registraste con tu celular y ya los emparejamos con el extracto: ahora tienen el nombre real del banco.',
  },
  {
    id: 'faltantes',
    estados: ['faltante'],
    titulo: 'Faltan en CuadraMe',
    ayuda: 'Aparecen en el extracto pero no en tu app. Marca los que quieres importar.',
  },
  {
    id: 'sobrantes',
    estados: ['sobrante'],
    titulo: 'Registrados que no aparecen en el extracto',
    ayuda: 'Los anotaste tú, pero el banco no los muestra en este periodo. Revisa si el monto está bien o si el banco aún no los refleja.',
  },
  {
    id: 'ya',
    estados: ['exacto', 'aproximado', 'importado'],
    titulo: 'Ya registrados',
    ayuda: null,
  },
]

export function resumenCompletados(n) {
  if (!n) return null
  return `Completé ${n} ${n === 1 ? 'movimiento' : 'movimientos'} con tu extracto`
}

export default function Conciliacion() {
  const navigate = useNavigate()
  const volver = useVolver('/perfil')
  const location = useLocation()
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const { nombres: CATEGORIAS } = useCategorias()
  const { avisar } = useDialogos()
  const [cuentaId, setCuentaId] = useState(cuentas[0]?.id || '')
  const [password, setPassword] = useState('')
  const [procesando, setProcesando] = useState(false)
  const [error, setError] = useState('')
  const [resultado, setResultado] = useState(null)
  const [seleccionados, setSeleccionados] = useState(new Set())
  const [categorias, setCategorias] = useState({}) // fingerprint -> categoría elegida
  const [importando, setImportando] = useState(false)
  const [sugeridas, setSugeridas] = useState({}) // fingerprint -> categoría que propuso la app
  const [aprender, setAprender] = useState({}) // fingerprint -> { recordar, anteriores } (solo filas editadas)
  const [multiples, setMultiples] = useState(null) // File[] cuando se suben varios archivos a la vez

  // Si llegamos desde "Extractos encontrados" (Correos), el PDF ya se procesó en
  // el servidor: solo hay que abrir su revisión.
  const historialInicial = location.state?.historialId
  useEffect(() => {
    if (!historialInicial) return
    api.obtenerReviewExtracto(historialInicial).then(mostrarResultado).catch(() => setError('No se pudo abrir la revisión del extracto'))
  }, [historialInicial])

  function mostrarResultado(r) {
    setResultado(r)
    setSeleccionados(new Set(r.review.filter((m) => m.estado === 'faltante').map((m) => m.fingerprint)))
    const inicial = {}
    r.review.forEach((m) => {
      if (m.estado === 'faltante') inicial[m.fingerprint] = m.categoria_sugerida || 'Otros'
    })
    setCategorias(inicial)
    setSugeridas(inicial)
    setAprender({})
  }

  // Un solo PDF: el flujo de siempre. Varios archivos (o un Excel/CSV): cola con revisión consolidada.
  async function onArchivos(files) {
    setError('')
    if (files.length > 1 || tipoDeArchivo(files[0]?.name) !== 'pdf') {
      setMultiples(files)
      return
    }
    const file = files[0]
    setResultado(null)
    setProcesando(true)
    try {
      const base64 = await fileToBase64(file)
      const r = await api.procesarExtracto(base64, cuentaId, password)
      if (!r.ok) {
        setError(r.error || 'No se pudo procesar el extracto')
      } else {
        mostrarResultado(r)
      }
    } catch (err) {
      setError(err.message || 'Error al procesar el PDF')
    } finally {
      setProcesando(false)
    }
  }

  function toggle(fp) {
    setSeleccionados((prev) => {
      const next = new Set(prev)
      if (next.has(fp)) next.delete(fp)
      else next.add(fp)
      return next
    })
  }

  function cambiarCategoria(fp, categoria) {
    setCategorias((prev) => ({ ...prev, [fp]: categoria }))
    // Si el usuario corrigió lo que sugirió la app, se ofrece recordarlo (marcado por defecto).
    setAprender((prev) => {
      const next = { ...prev }
      if (categoria === (sugeridas[fp] || 'Otros')) delete next[fp]
      else next[fp] = next[fp] || RECORDAR_INICIAL
      return next
    })
  }

  async function importar() {
    if (!resultado?.historial_id || seleccionados.size === 0) return
    setImportando(true)
    try {
      const marcadas = [...seleccionados].filter((fp) => aprender[fp]?.recordar)
      const r = await api.importarFaltantes(
        resultado.historial_id,
        [...seleccionados],
        categorias,
        marcadas.length
          ? { recordar: marcadas, aplicar_anteriores: marcadas.filter((fp) => aprender[fp]?.anteriores) }
          : undefined
      )
      await recargarCuentas()
      if (r.reglas_guardadas > 0) avisar(`Aprendí ${r.reglas_guardadas} ${r.reglas_guardadas === 1 ? 'comercio' : 'comercios'}: la próxima vez ya sabré qué son`, 'ok')
      if (r.sin_categoria_clara > 0) {
        avisar(
          `Listo. ${r.sin_categoria_clara} de ${r.importados} movimientos quedaron en "Otros" porque no reconocimos de qué se trataban — puedes recategorizarlos desde Movimientos.`,
          'ok'
        )
      }
      if (r.categorizados_auto > 0 || r.sin_categoria_clara > 0) {
        // Lleva a la vista "Por revisar" para que confirme lo que categorizó la app.
        if (r.categorizados_auto > 0) avisar(`Categoricé ${r.categorizados_auto} movimientos: revísalos`, 'ok')
        navigate('/movimientos?revisar=1', { replace: true })
      } else {
        navigate('/', { replace: true })
      }
    } catch (err) {
      setError(err.message || 'No se pudo importar')
    } finally {
      setImportando(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button
          onClick={volver}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
         aria-label="Volver">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-xl font-semibold">Conciliar extracto</h1>
      </header>

      {!resultado && multiples && (
        <SubidaMultiple archivosIniciales={multiples} cuentaInicial={cuentaId} onCancelar={() => setMultiples(null)} />
      )}

      {!resultado && !multiples && (
        <div className="px-5 mt-4">
          <p className="text-sm text-ink-soft mb-4">
            Sube el PDF de tu extracto bancario (o varios a la vez, también Excel o CSV) y compáralo con tus movimientos registrados.
            Detectamos automáticamente lo que falta por registrar.
          </p>

          {cuentas.length > 1 && (
            <div className="mb-3">
              <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Cuenta</p>
              <div className="flex gap-2 overflow-x-auto no-scrollbar">
                {cuentas.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setCuentaId(c.id)}
                    className={`shrink-0 text-sm px-4 py-1.5 rounded-full border ${
                      cuentaId === c.id ? 'bg-accent text-white border-accent' : 'border-line text-ink-soft'
                    }`}
                  >
                    {c.icono} {c.nombre}
                  </button>
                ))}
              </div>
            </div>
          )}

          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Clave del PDF (si tiene)"
            className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
          />

          <ZonaSubida
            onArchivos={onArchivos}
            disabled={procesando}
            titulo={procesando ? 'Procesando...' : 'Toca para subir tus extractos'}
            ariaLabel="Extractos a conciliar"
          />

          {error && <p className="text-sm text-danger mt-4">{error}</p>}

          <Link
            to="/importar"
            className="mt-4 flex items-center gap-3 rounded-2xl border border-line bg-paper-raised px-4 py-3.5"
          >
            <FileSpreadsheet size={20} className="text-accent shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">¿Tienes un Excel o CSV?</p>
              <p className="text-xs text-ink-soft mt-0.5">Impórtalo, revisa las columnas y confirma lo que se guarda</p>
            </div>
          </Link>
        </div>
      )}

      {resultado && (
        <div className="px-5 mt-4">
          {resumenCompletados(resultado.completados) && (
            <div role="status" className="rounded-2xl bg-accent-soft p-3.5 mb-4 flex items-center gap-2.5">
              <Check size={18} className="text-accent shrink-0" />
              <p className="text-sm font-semibold text-ink">{resumenCompletados(resultado.completados)}</p>
            </div>
          )}

          <div className="rounded-2xl bg-paper-raised border border-line p-4 mb-4 grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-lg font-bold text-accent">{resultado.exactos + resultado.aproximados + (resultado.completados || 0)}</p>
              <p className="text-xs text-ink-soft">Ya registrados</p>
            </div>
            <div>
              <p className="text-lg font-bold text-danger">{resultado.faltantes}</p>
              <p className="text-xs text-ink-soft">Faltantes</p>
            </div>
            <div>
              <p className="text-lg font-bold">{resultado.total_movimientos}</p>
              <p className="text-xs text-ink-soft">Total</p>
            </div>
          </div>

          <AvisoYaConciliado info={resultado.ya_conciliado} cuenta={cuentas.find((c) => c.id === cuentaId)?.nombre} className="mb-4" />
          <AvisoCategorizados n={resultado.auto_importados} className="mb-4" />

          {resultado.descartados > 0 && (
            <div className="rounded-2xl bg-accent-soft p-3.5 mb-4">
              <p className="text-xs text-ink">
                Además del listado, {resultado.descartados}{' '}
                {resultado.descartados === 1 ? 'línea del PDF no se pudo leer con certeza' : 'líneas del PDF no se pudieron leer con certeza'}{' '}
                (montos ambiguos) y no aparecen aquí — revisa tu extracto original si crees que falta algo.
              </p>
            </div>
          )}

          {SECCIONES.map((sec) => {
            const items = resultado.review.filter((m) => sec.estados.includes(m.estado))
            if (items.length === 0) return null
            return (
          <section key={sec.id} aria-label={sec.titulo} className="mb-4">
            <h2 className="text-sm font-semibold">{sec.titulo} ({items.length})</h2>
            {sec.ayuda && <p className="text-xs text-ink-soft mt-0.5 mb-2">{sec.ayuda}</p>}
          <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden mt-2">
            {items.map((m) => (
              <div key={m.fingerprint} className="px-4 py-3.5">
                <label className="flex items-center gap-3">
                  {m.estado === 'faltante' && (
                    <input
                      type="checkbox"
                      checked={seleccionados.has(m.fingerprint)}
                      onChange={() => toggle(m.fingerprint)}
                      className="w-5 h-5 accent-accent shrink-0"
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{m.descripcion}</p>
                    <p className={`text-xs ${estadoColor[m.estado]}`}>
                      {m.fecha} · {estadoLabel[m.estado]}
                      {m.estado === 'completado' && m.categoria_sugerida ? ` · ${m.categoria_sugerida}` : ''}
                    </p>
                    {m.estado === 'completado' && m.descripcion_registrada && m.descripcion_registrada !== m.descripcion && (
                      <p className="text-xs text-ink-soft truncate">Tú anotaste: {m.descripcion_registrada}</p>
                    )}
                    {m.estado === 'completado' && m.monto_registrado != null && m.monto_registrado !== m.monto && (
                      <p className="text-xs text-danger">
                        Anotaste {formatCOP(m.monto_registrado)} y el banco dice {formatCOP(m.monto)}: revisa el monto
                      </p>
                    )}
                  </div>
                  <p className="text-sm font-semibold shrink-0">
                    {m.tipo === 'income' ? '+' : m.tipo === 'transfer' ? '' : '-'}
                    {formatCOP(m.monto)}
                  </p>
                </label>
                {m.estado === 'faltante' && seleccionados.has(m.fingerprint) && (
                  <select
                    aria-label={`Categoría de ${m.descripcion}`}
                    value={categorias[m.fingerprint] || 'Otros'}
                    onChange={(e) => cambiarCategoria(m.fingerprint, e.target.value)}
                    className={`w-full mt-2.5 ml-8 rounded-xl border px-3 py-2 text-xs ${
                      categorias[m.fingerprint] === 'Otros' || !categorias[m.fingerprint]
                        ? 'border-line bg-paper text-ink-soft'
                        : 'border-accent bg-accent-soft text-ink'
                    }`}
                    style={{ width: 'calc(100% - 2rem)' }}
                  >
                    {CATEGORIAS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                )}
                {m.estado === 'faltante' && seleccionados.has(m.fingerprint) && (
                  <div className="ml-8 mt-1.5">
                    {m.razon_categoria && !aprender[m.fingerprint] && (
                      <p className="text-[11px] text-ink-soft">Auto · {m.razon_categoria}</p>
                    )}
                    {aprender[m.fingerprint] && (
                      <RecordarRegla
                        descripcion={m.descripcion}
                        valor={aprender[m.fingerprint]}
                        onChange={(v) => setAprender((p) => ({ ...p, [m.fingerprint]: v }))}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          </section>
            )
          })}

          {error && <p className="text-sm text-danger mb-3">{error}</p>}

          <div className="flex gap-2">
            <button
              onClick={() => setResultado(null)}
              className="flex-1 rounded-2xl border border-line py-3.5 text-sm font-semibold flex items-center justify-center gap-2"
            >
              <X size={16} /> Cancelar
            </button>
            <button
              onClick={importar}
              disabled={seleccionados.size === 0 || importando}
              className="flex-1 bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <Check size={16} /> {importando ? 'Importando...' : `Importar (${seleccionados.size})`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
