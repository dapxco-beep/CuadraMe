import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, FileUp, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'

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
}

const estadoColor = {
  exacto: 'text-ink-soft',
  aproximado: 'text-ink-soft',
  faltante: 'text-danger',
  importado: 'text-accent',
}

export default function Conciliacion() {
  const navigate = useNavigate()
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
  }

  async function onFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
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
      e.target.value = ''
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
  }

  async function importar() {
    if (!resultado?.historial_id || seleccionados.size === 0) return
    setImportando(true)
    try {
      const r = await api.importarFaltantes(resultado.historial_id, [...seleccionados], categorias)
      await recargarCuentas()
      if (r.sin_categoria_clara > 0) {
        avisar(
          `Listo. ${r.sin_categoria_clara} de ${r.importados} movimientos quedaron en "Otros" porque no reconocimos de qué se trataban — puedes recategorizarlos desde Movimientos.`,
          'ok'
        )
      }
      navigate('/')
    } catch (err) {
      setError(err.message || 'No se pudo importar')
    } finally {
      setImportando(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pt-14 pb-2 flex items-center gap-3">
        <button
          onClick={() => navigate('/perfil')}
          className="w-9 h-9 rounded-full bg-paper-raised border border-line flex items-center justify-center"
         aria-label="Volver">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-xl font-semibold">Conciliar extracto</h1>
      </header>

      {!resultado && (
        <div className="px-5 mt-4">
          <p className="text-sm text-ink-soft mb-4">
            Sube el PDF de tu extracto bancario y compáralo con tus movimientos registrados. Detectamos automáticamente lo que falta por registrar.
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

          <label className="w-full flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line bg-paper-raised py-10 cursor-pointer">
            <FileUp size={28} className="text-accent" />
            <span className="text-sm font-medium">
              {procesando ? 'Procesando...' : 'Toca para subir el PDF'}
            </span>
            <input type="file" accept="application/pdf" onChange={onFile} disabled={procesando} className="hidden" />
          </label>

          {error && <p className="text-sm text-danger mt-4">{error}</p>}
        </div>
      )}

      {resultado && (
        <div className="px-5 mt-4">
          <div className="rounded-2xl bg-paper-raised border border-line p-4 mb-4 grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-lg font-bold text-accent">{resultado.exactos + resultado.aproximados}</p>
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

          {resultado.descartados > 0 && (
            <div className="rounded-2xl bg-accent-soft p-3.5 mb-4">
              <p className="text-xs text-ink">
                Además del listado, {resultado.descartados}{' '}
                {resultado.descartados === 1 ? 'línea del PDF no se pudo leer con certeza' : 'líneas del PDF no se pudieron leer con certeza'}{' '}
                (montos ambiguos) y no aparecen aquí — revisa tu extracto original si crees que falta algo.
              </p>
            </div>
          )}

          <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden mb-4">
            {resultado.review.map((m) => (
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
                    </p>
                  </div>
                  <p className="text-sm font-semibold shrink-0">
                    {m.tipo === 'income' ? '+' : m.tipo === 'transfer' ? '' : '-'}
                    {formatCOP(m.monto)}
                  </p>
                </label>
                {m.estado === 'faltante' && seleccionados.has(m.fingerprint) && (
                  <select
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
              </div>
            ))}
          </div>

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
