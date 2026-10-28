import { useEffect, useState } from 'react'
import { Boton } from '../components/ui'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Download, FileText, Info, Printer } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOPFijo as formatCOP } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'
import TarjetaRenta from '../components/TarjetaRenta'
import TarjetaGmfMes from '../components/TarjetaGmfMes'
import ImpuestosInformativo from '../components/ImpuestosInformativo'
import { usePais } from '../lib/pais'
import EnlacesRelacionados from '../components/EnlacesRelacionados'

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

function etiquetaMes(clave) {
  const [anio, mes] = clave.split('-')
  return `${MESES[Number(mes) - 1]} ${anio}`
}

export default function Impuestos() {
  const volver = useVolver('/perfil')
  const { tiene, cargado } = usePais()
  // La renta DIAN, el 4x1000 y los deducibles son solo de Colombia; en otro país se muestra el recordatorio.
  const soloInformativo = !tiene('renta_dian')
  const { avisar } = useDialogos()
  const anioActual = new Date().getFullYear()
  const [anio, setAnio] = useState(anioActual)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [abierto, setAbierto] = useState(null) // movimiento_id con el editor de soporte abierto
  const [soporte, setSoporte] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function cargar(a = anio) {
    if (soloInformativo || !cargado) return
    setError('')
    try {
      setDatos(await api.impuestosResumen(a))
    } catch (err) {
      setError(err.message || 'No se pudo cargar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  useEffect(() => {
    setDatos(null)
    cargar(anio)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anio, soloInformativo, cargado])

  async function cambiarCuentaExenta(id) {
    try {
      await api.impuestosAjustes(id)
      await cargar()
    } catch (err) {
      avisar(err.message || 'No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  async function marcar(item, estado) {
    setGuardando(true)
    try {
      await api.impuestosMarcar(item.movimiento_id, {
        categoria_fiscal: item.categoria_fiscal,
        soporte: abierto === item.movimiento_id ? soporte : item.soporte || '',
        estado,
      })
      setAbierto(null)
      await cargar()
    } catch (err) {
      avisar(err.message || 'No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setGuardando(false)
    }
  }

  async function quitar(item) {
    try {
      await api.impuestosQuitarMarca(item.movimiento_id)
      await cargar()
    } catch (err) {
      avisar(err.message || 'No se pudo quitar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  async function descargar() {
    try {
      await api.impuestosExcel(anio)
    } catch {
      avisar('No se pudo exportar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  const gmf = datos?.gmf
  const ded = datos?.deducibles
  const maxMes = gmf ? Math.max(1, ...gmf.meses.map((m) => m.gmf_estimado)) : 1

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3 no-print">
        <button
          onClick={volver}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-semibold flex-1">Impuestos</h1>
        <select
          aria-label="Año"
          value={anio}
          onChange={(e) => setAnio(Number(e.target.value))}
          className="rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm"
        >
          {[anioActual, anioActual - 1, anioActual - 2].map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </header>
      <h1 className="hidden print-only text-xl font-semibold px-5">CuadraMe — apoyo para la declaración de renta {anio}</h1>

      {!cargado ? null : soloInformativo ? (
        <ImpuestosInformativo />
      ) : (
        <>

      <div className="px-5 mt-3">
        <div className="rounded-2xl bg-accent-soft p-3.5 flex gap-2.5" role="note">
          <Info size={16} className="text-accent shrink-0 mt-0.5" />
          <p className="text-xs text-ink">
            {datos?.aviso ||
              'Información de apoyo, no asesoría tributaria. Los valores son estimaciones; confirma siempre con tu contador y con la normativa vigente de la DIAN.'}
          </p>
        </div>
      </div>

      <TarjetaRenta />
      <TarjetaGmfMes />

      {error && <p className="px-5 mt-4 text-sm text-danger">{error}</p>}
      {!datos && !error && <p className="px-5 mt-6 text-sm text-ink-soft">Calculando...</p>}

      {datos && (
        <>
          <section className="px-5 mt-5">
            <h2 className="text-[15px] font-semibold mb-1">4x1000 (GMF)</h2>
            <p className="text-xs text-ink-soft mb-3">Es un impuesto de 4 pesos por cada 1.000 que sacas de tu cuenta. Aquí ves cuánto llevas, calculado con lo que sale de tus cuentas de ahorro.</p>
            <div className="rounded-2xl bg-paper-raised border border-line p-4">
              <p className="text-xs text-ink-soft">Estimado {anio}</p>
              <p className="text-2xl font-bold">{formatCOP(gmf.total_estimado)}</p>
              <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                <div>
                  <p className="text-ink-soft">Promedio mensual</p>
                  <p className="font-semibold text-sm">{formatCOP(gmf.promedio_mensual)}</p>
                </div>
                <div>
                  <p className="text-ink-soft">Ya anotado como impuesto</p>
                  <p className="font-semibold text-sm">{formatCOP(gmf.total_registrado)}</p>
                </div>
              </div>

              {gmf.meses.length > 0 && (
                <ul className="mt-4 space-y-1.5" aria-label="4x1000 por mes">
                  {gmf.meses.map((m) => (
                    <li key={m.mes} className="flex items-center gap-2 text-xs">
                      <span className="w-16 shrink-0 text-ink-soft">{etiquetaMes(m.mes)}</span>
                      <span
                        className="flex-1 h-2 rounded-full bg-line overflow-hidden"
                        role="progressbar"
                        aria-label={`4x1000 de ${etiquetaMes(m.mes)}`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={Math.round((m.gmf_estimado / maxMes) * 100)}
                      >
                        <span className="block h-full w-full bg-accent barra-fill" style={{ transform: `scaleX(${m.gmf_estimado / maxMes})` }} />
                      </span>
                      <span className="w-20 text-right font-medium">{formatCOP(m.gmf_estimado)}</span>
                    </li>
                  ))}
                </ul>
              )}

              <label className="block mt-4 text-xs no-print">
                <span className="block text-ink-soft mb-1">Mi cuenta libre de este impuesto (la ley deja una por persona, hasta {gmf.tope_exento_mensual.toLocaleString('es-CO')} COP al mes)</span>
                <select
                  aria-label="Cuenta exenta del 4x1000"
                  value={datos.cuenta_exenta_gmf_id || ''}
                  onChange={(e) => cambiarCuentaExenta(e.target.value)}
                  className="w-full rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                >
                  <option value="">Ninguna elegida</option>
                  {datos.cuentas_ahorro.map((c) => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
              </label>
              <p className="text-[11px] text-ink-soft mt-3">{gmf.nota}</p>
            </div>
          </section>

          <section className="px-5 mt-6">
            <h2 className="text-[15px] font-semibold mb-1">Gastos que podrían bajar tu impuesto de renta</h2>
            <p className="text-xs text-ink-soft mb-3">
              Los buscamos por su nombre o categoría. Que aparezcan aquí no es garantía: confírmalos, anota dónde está la factura y revísalos con tu contador.
            </p>

            <div className="rounded-2xl bg-paper-raised border border-line p-4 mb-3 grid grid-cols-2 gap-3 text-center">
              <div>
                <p className="text-lg font-bold text-accent">{formatCOP(ded.total_confirmado)}</p>
                <p className="text-xs text-ink-soft">Confirmado por ti</p>
              </div>
              <div>
                <p className="text-lg font-bold">{formatCOP(ded.total_sugerido)}</p>
                <p className="text-xs text-ink-soft">Sugerido, sin revisar</p>
              </div>
            </div>

            {ded.items.length === 0 ? (
              <p className="text-sm text-ink-soft text-center py-6">No encontramos gastos para revisar en {anio}.</p>
            ) : (
              ded.por_categoria.map((cat) => (
                <div key={cat.categoria_fiscal} className="mb-4">
                  <div className="flex items-baseline justify-between mb-1.5">
                    <p className="text-sm font-semibold">{cat.etiqueta}</p>
                    <p className="text-xs text-ink-soft">{cat.cantidad} · {formatCOP(cat.confirmado + cat.sugerido)}</p>
                  </div>
                  <p className="text-[11px] text-ink-soft mb-2">{cat.ayuda}</p>
                  <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                    {ded.items
                      .filter((i) => i.categoria_fiscal === cat.categoria_fiscal)
                      .map((i) => (
                        <div key={i.movimiento_id} className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{i.descripcion}</p>
                              <p className="text-xs text-ink-soft">
                                {i.fecha} ·{' '}
                                <span className={i.estado === 'confirmado' ? 'text-accent font-medium' : ''}>
                                  {i.estado === 'confirmado' ? 'Confirmado' : 'Sugerido'}
                                </span>
                                {i.soporte ? ` · Factura: ${i.soporte}` : ''}
                              </p>
                            </div>
                            <p className="text-sm font-semibold shrink-0">{formatCOP(i.monto)}</p>
                          </div>

                          {abierto === i.movimiento_id ? (
                            <div className="mt-2.5 no-print">
                              <input
                                aria-label="Dónde está la factura"
                                value={soporte}
                                onChange={(e) => setSoporte(e.target.value)}
                                maxLength={300}
                                placeholder="Dónde está la factura (ej. en el correo, en Drive)"
                                className="w-full rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                              />
                              <div className="flex gap-2 mt-2">
                                <button
                                  onClick={() => marcar(i, 'confirmada')}
                                  disabled={guardando}
                                  className="flex-1 bg-ink text-paper rounded-xl py-2 text-xs font-semibold disabled:opacity-60"
                                >
                                  Guardar este gasto
                                </button>
                                <button onClick={() => setAbierto(null)} className="rounded-xl border border-line px-3 py-2 text-xs">
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex gap-2 mt-2.5 no-print">
                              <Boton tam="sm" variante="suave" onClick={() => { setAbierto(i.movimiento_id); setSoporte(i.soporte || '') }}>
                                {i.estado === 'confirmado' ? 'Editar dónde está la factura' : 'Confirmar'}
                              </Boton>
                              {i.estado === 'confirmado' ? (
                                <Boton tam="sm" variante="secundario" onClick={() => quitar(i)}>
                                  Quitar marca
                                </Boton>
                              ) : (
                                <Boton tam="sm" variante="secundario" onClick={() => marcar(i, 'descartada')}>
                                  No aplica
                                </Boton>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                  </div>
                </div>
              ))
            )}
          </section>

          <section className="px-5 mt-6 no-print">
            <h2 className="text-[15px] font-semibold mb-3">Llévalo a tu declaración</h2>
            <div className="flex gap-2">
              <button
                onClick={descargar}
                className="flex-1 rounded-2xl border border-line bg-paper-raised py-3.5 text-sm font-semibold flex items-center justify-center gap-2"
              >
                <Download size={16} /> Excel
              </button>
              <button
                onClick={() => window.print()}
                className="flex-1 rounded-2xl border border-line bg-paper-raised py-3.5 text-sm font-semibold flex items-center justify-center gap-2"
              >
                <Printer size={16} /> Guardar PDF
              </button>
            </div>
            <p className="text-[11px] text-ink-soft mt-2 flex items-start gap-1.5">
              <FileText size={16} className="shrink-0 mt-0.5" />
              Para el PDF, elige "Guardar como PDF" en la ventana de impresión de tu dispositivo.
            </p>
          </section>
          <EnlacesRelacionados enlaces={[
            { a: '/movimientos', texto: 'Mis movimientos', apoyo: 'Busca el gasto y revisa su categoría' },
            { a: '/cierre-mes', texto: 'Cierre de mes' },
            { a: '/ayuda', texto: 'Ayuda' },
          ]} />
        </>
      )}
        </>
      )}
    </div>
  )
}
