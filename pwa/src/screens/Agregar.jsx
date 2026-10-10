import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { Calendar, Camera, Image as ImagenIcono, Info, Sparkles, Users, X } from 'lucide-react'
import Icono from '../components/Icono'
import { api } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { encolarMovimiento } from '../lib/colaOffline'
import { prepararImagen } from '../lib/imagen'
import { formatCOP, formatMoneda } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import SugerenciaIngreso from '../components/SugerenciaIngreso'
import { useCategorias } from '../lib/CategoriasContext'
import TarjetaCuenta from '../components/TarjetaCuenta'

function hoyISO() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

function calcularFrecuentes(movimientos) {
  const vistos = new Map()
  for (const m of movimientos) {
    if (m.tipo === 'transfer') continue // las transferencias no son un gasto que se repita
    const clave = m.descripcion.trim().toLowerCase()
    if (!vistos.has(clave)) {
      vistos.set(clave, { descripcion: m.descripcion, categoria: m.categoria, tipo: m.tipo, monto: m.monto, veces: 0 })
    }
    vistos.get(clave).veces += 1
  }
  return [...vistos.values()].sort((a, b) => b.veces - a.veces).slice(0, 30)
}

// Solo los del tipo de la pestaña activa: en "Gasto" no salen ingresos (ni al revés).
export function frecuentesDelTipo(frecuentes, tipo) {
  return frecuentes.filter((f) => f.tipo === tipo).slice(0, 6)
}

export default function Agregar() {
  const navigate = useNavigate()
  // Cerrar o guardar vuelve a donde estaba el usuario (o a Inicio si entró directo, p. ej. desde el atajo);
  // así "atrás" nunca reabre el formulario ya guardado.
  const volver = useVolver('/')
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const auth = useAuth()
  const { nombres: categoriasRapidas } = useCategorias()
  const [cuentaElegidaId, setCuentaId] = useState('')
  const [cuentaDestinoId, setCuentaDestinoId] = useState('')
  const [monto, setMonto] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [tipo, setTipo] = useState('expense')
  const [sugerirIngreso, setSugerirIngreso] = useState(null) // { monto, cuentaId } tras registrar un ingreso
  const [categoria, setCategoria] = useState('')
  const [categoriaAutoDetectada, setCategoriaAutoDetectada] = useState(false)
  const [frecuentes, setFrecuentes] = useState([])
  const [fecha, setFecha] = useState(hoyISO())
  const [mostrarFecha, setMostrarFecha] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [posibleDuplicado, setPosibleDuplicado] = useState(null) // mensaje del servidor si ya lo tiene por otro canal
  const carruselRef = useRef(null)
  const montoRef = useRef(null)
  const [params] = useSearchParams()
  // "Registrar gasto" desde la pregunta de Inicio abre aquí con el cursor en el monto
  // (teclado numérico listo), para registrar en un par de toques.
  useEffect(() => {
    if (params.get('foco') === 'monto') montoRef.current?.focus()
  }, [params])
  const [escaneando, setEscaneando] = useState(false)
  const [factura, setFactura] = useState(null) // datos extra leídos de la foto (solo informativos)
  const [errorFactura, setErrorFactura] = useState('')

  // Si el usuario aún no eligió cuenta se usa la primera: se deriva al renderizar
  // en vez de copiarla a un estado con un efecto (evita un render extra).
  const cuentaId = cuentaElegidaId || cuentas[0]?.id || ''
  const cuentaActual = cuentas.find((c) => c.id === cuentaId)
  const esTransferencia = tipo === 'transfer'
  const destinosPosibles = cuentas.filter((c) => c.id !== cuentaId)
  const destinoId = destinosPosibles.some((c) => c.id === cuentaDestinoId)
    ? cuentaDestinoId
    : destinosPosibles[0]?.id || ''

  function seleccionarCuenta(id) {
    setCuentaId(id)
    const idx = cuentas.findIndex((c) => c.id === id)
    const el = carruselRef.current
    if (el && idx >= 0) {
      const tarjeta = el.children[idx]
      tarjeta?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
    }
  }

  useEffect(() => {
    api.movimientos(60).then((movs) => setFrecuentes(calcularFrecuentes(movs))).catch(() => {})
  }, [])

  async function onDescripcionBlur() {
    if (!descripcion.trim() || categoria) return
    try {
      const r = await api.clasificar({ descripcion })
      if (r.categoria !== 'Otros') {
        setCategoria(r.categoria)
        setCategoriaAutoDetectada(true)
      }
    } catch {}
  }

  function usarFrecuente(f) {
    setDescripcion(f.descripcion)
    setCategoria(f.categoria)
    setCategoriaAutoDetectada(false)
    setTipo(f.tipo)
    setMonto(String(Math.round(f.monto)))
  }

  // La foto solo RELLENA el formulario: el usuario revisa y toca "Guardar" él mismo.
  async function leerFactura(e) {
    const archivo = e.target.files?.[0]
    e.target.value = '' // permite volver a elegir la misma foto
    if (!archivo) return
    setErrorFactura('')
    setFactura(null)
    setEscaneando(true)
    try {
      const { base64, mime } = await prepararImagen(archivo)
      const r = await api.escanearFactura(base64, mime)
      setTipo('expense')
      setMonto(String(Math.round(r.total)))
      if (r.comercio) setDescripcion(r.comercio)
      if (r.fecha) setFecha(r.fecha)
      if (r.categoria && r.categoria !== 'Otros') {
        setCategoria(r.categoria)
        setCategoriaAutoDetectada(true)
      }
      setFactura(r)
    } catch (err) {
      setErrorFactura(err.message || 'No pudimos leer la factura')
    } finally {
      setEscaneando(false)
    }
  }

  function dividirGasto() {
    setError('')
    if (!monto || Number(monto) <= 0) return setError('Ingresa un monto válido para dividir')
    navigate('/dividir', {
      state: { monto: Number(monto), descripcion: descripcion.trim(), categoria: categoria || undefined, cuentaId, fecha },
    })
  }

  async function guardar(confirmarNuevo = false) {
    setError('')
    setPosibleDuplicado(null)
    if (!cuentaId) return setError('Crea una cuenta primero')
    if (!monto || Number(monto) <= 0) return setError('Ingresa un monto válido')
    if (!esTransferencia && !descripcion.trim()) return setError('Ingresa una descripción')
    if (esTransferencia && !destinoId) return setError('Necesitas al menos dos cuentas para transferir')

    setGuardando(true)
    try {
      if (esTransferencia) {
        await api.crearTransferencia({
          cuenta_origen_id: cuentaId,
          cuenta_destino_id: destinoId,
          monto: Number(monto),
          fecha: fecha ? `${fecha}T12:00:00` : undefined,
        })
        await recargarCuentas()
        volver()
        return
      }
      await api.crearMovimiento({
        cuenta_id: cuentaId,
        descripcion: descripcion.trim(),
        monto: Number(monto),
        tipo,
        categoria: categoria || undefined,
        fecha: fecha ? `${fecha}T12:00:00` : undefined,
        ...(confirmarNuevo ? { confirmar_nuevo: true } : {}),
      })
      await recargarCuentas()
      // Un ingreso abre la sugerencia de reparto (fijos, ahorro, gasto libre); el
      // usuario la acepta o la descarta, y de ahí vuelve al inicio.
      if (tipo === 'income') {
        setSugerirIngreso({ monto: Number(monto), cuentaId })
        return
      }
      volver()
    } catch (err) {
      // Sin señal: el movimiento nuevo se guarda en el celular y sale solo cuando vuelve la red.
      // (Transferencias y ediciones no: esas piden conexión para no pisar cambios.)
      if (err.sinConexion && !esTransferencia && auth?.usuario?.id) {
        const guardado = encolarMovimiento(auth.usuario.id, {
          cuenta_id: cuentaId,
          descripcion: descripcion.trim(),
          monto: Number(monto),
          tipo,
          categoria: categoria || undefined,
          fecha: fecha ? `${fecha}T12:00:00` : undefined,
          ...(confirmarNuevo ? { confirmar_nuevo: true } : {}),
        })
        if (guardado) {
          window.dispatchEvent(new CustomEvent('cuadrame:cola-cambio'))
          window.dispatchEvent(
            new CustomEvent('cuadrame:aviso', {
              detail: { mensaje: 'Sin conexión: guardamos tu movimiento en el celular y lo enviamos cuando vuelva la señal.', tipo: 'info' },
            })
          )
          volver()
          return
        }
      }
      // Ya lo tienes por otro canal (atajo, correo, extracto): se pregunta en vez de duplicarlo.
      if (err.status === 409 && err.detalle?.codigo === 'posible_duplicado') {
        setPosibleDuplicado(err.detalle.mensaje || err.message)
      } else {
        setError(err.message || 'No se pudo guardar')
      }
    } finally {
      setGuardando(false)
    }
  }

  if (sugerirIngreso) {
    return (
      <SugerenciaIngreso
        monto={sugerirIngreso.monto}
        cuentaId={sugerirIngreso.cuentaId}
        onClose={volver}
        onAplicado={recargarCuentas}
      />
    )
  }

  return (
    <div className="flex-1 flex flex-col pb-6">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Nuevo movimiento</h1>
        <button
          onClick={volver}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Cerrar"
        >
          <X size={20} />
        </button>
      </header>

      <div className="px-5 flex gap-2 mt-2">
        {[
          { id: 'expense', label: 'Gasto' },
          { id: 'income', label: 'Ingreso' },
          ...(cuentas.length > 1 ? [{ id: 'transfer', label: 'Transferir' }] : []),
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTipo(t.id)}
            aria-pressed={tipo === t.id}
            className={`flex-1 rounded-2xl py-2.5 text-sm font-semibold border ${
              tipo === t.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
            }`}
          >
            {t.label}
          </button>
        ))}
        <button
          onClick={() => setMostrarFecha((v) => !v)}
          className={`shrink-0 w-11 rounded-2xl border flex items-center justify-center ${
            fecha !== hoyISO() ? 'bg-accent-soft border-accent text-accent' : 'border-line text-ink-soft'
          }`}
          aria-label="Cambiar fecha"
        >
          <Calendar size={16} />
        </button>
      </div>

      {!esTransferencia && (
        <div className="px-5 mt-2 flex gap-2">
          <label
            className={`flex-1 rounded-2xl border border-line bg-paper-raised py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 ${
              escaneando ? 'opacity-60 pointer-events-none' : 'cursor-pointer'
            }`}
          >
            <Camera size={16} /> Foto de factura
            <input type="file" accept="image/*" capture="environment" className="hidden" aria-label="Tomar foto de factura" onChange={leerFactura} />
          </label>
          <label
            className={`shrink-0 w-11 rounded-2xl border border-line bg-paper-raised flex items-center justify-center ${
              escaneando ? 'opacity-60 pointer-events-none' : 'cursor-pointer'
            }`}
            title="Elegir de la galería"
          >
            <ImagenIcono size={16} />
            <input type="file" accept="image/*" className="hidden" aria-label="Elegir factura de la galería" onChange={leerFactura} />
          </label>
          {tipo === 'expense' && (
            <button
              onClick={dividirGasto}
              className="flex-1 rounded-2xl border border-line bg-paper-raised py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5"
            >
              <Users size={16} /> Dividir
            </button>
          )}
        </div>
      )}

      {escaneando && (
        <p role="status" className="px-5 mt-2 text-xs text-accent flex items-center gap-1.5">
          <Sparkles size={16} className="animate-pulse" /> Leyendo tu factura...
        </p>
      )}
      {errorFactura && (
        <p role="alert" className="px-5 mt-2 text-xs text-danger">
          {errorFactura}
        </p>
      )}
      {factura && (
        <div role="status" className="mx-5 mt-2 rounded-2xl bg-accent-soft border border-accent/40 px-4 py-2.5 text-xs text-accent">
          <p className="font-semibold">Revisa los datos antes de guardar</p>
          <p className="mt-0.5">
            La IA puede equivocarse.
            {factura.impuestos != null && ` IVA/impuestos: ${formatMoneda(factura.impuestos, factura.moneda)}.`}
            {factura.propina != null && ` Propina: ${formatMoneda(factura.propina, factura.moneda)}.`}
            {cuentaActual && factura.moneda !== (cuentaActual.moneda || 'COP') &&
              ` La factura está en ${factura.moneda} y tu cuenta en ${cuentaActual.moneda}: ajusta el monto.`}
          </p>
        </div>
      )}

      {mostrarFecha && (
        <div className="px-5 mt-2">
          <input
            type="date"
            value={fecha}
            max={hoyISO()}
            onChange={(e) => setFecha(e.target.value)}
            className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-2.5 text-sm outline-none focus:border-accent"
          />
        </div>
      )}

      <div className="flex flex-col items-center justify-center px-8 py-8">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-semibold text-ink-soft">$</span>
          <input
            value={monto}
            onChange={(e) => setMonto(e.target.value.replace(/\D/g, ''))}
            placeholder="0"
            inputMode="numeric"
            ref={montoRef}
            aria-label="Monto"
            className="bg-transparent outline-none text-6xl font-semibold text-center w-full tabular-nums placeholder:text-ink-soft/40"
          />
        </div>
        <p className="text-sm text-ink-soft mt-2">{cuentaActual?.moneda || 'COP'}</p>
      </div>

      {!esTransferencia && (
      <div className="px-5 mb-4">
        <input
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          onBlur={onDescripcionBlur}
          placeholder="¿En qué fue? (ej. Éxito, Uber, Netflix)"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />
        {categoriaAutoDetectada && categoria && (
          <div className="flex items-center gap-1.5 mt-2 text-xs text-accent">
            <Sparkles size={16} />
            <span>Detectamos: {categoria}</span>
          </div>
        )}
      </div>
      )}

      {!esTransferencia && frecuentesDelTipo(frecuentes, tipo).length > 0 && !descripcion && (
        <div className="px-5 mb-4">
          <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Frecuentes</p>
          <div className="flex gap-2 overflow-x-auto no-scrollbar">
            {frecuentesDelTipo(frecuentes, tipo).map((f) => (
              <button
                key={f.descripcion}
                onClick={() => usarFrecuente(f)}
                className="shrink-0 rounded-2xl border border-line bg-paper-raised px-3.5 py-2.5 text-left"
              >
                <p className="text-xs font-semibold max-w-[110px] truncate">{f.descripcion}</p>
                <p className="text-[11px] text-ink-soft mt-0.5">{formatCOP(f.monto)}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {cuentas.length > 1 && (
        <div className="mb-4">
          <p className="px-5 text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">
            {esTransferencia ? 'Desde' : 'Cuenta'}
          </p>
          <div ref={carruselRef} className="flex gap-3 overflow-x-auto no-scrollbar px-5 pb-1 snap-x snap-mandatory">
            {cuentas.map((c) => (
              <button
                key={c.id}
                onClick={() => seleccionarCuenta(c.id)}
                className="shrink-0 w-40 snap-center transition-transform"
                style={{ transform: cuentaId === c.id ? 'scale(1)' : 'scale(0.92)', opacity: cuentaId === c.id ? 1 : 0.6 }}
              >
                <TarjetaCuenta cuenta={c} />
              </button>
            ))}
          </div>
        </div>
      )}

      {esTransferencia && (
        <div className="px-5 mb-5">
          <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Hacia</p>
          <div className="grid grid-cols-2 gap-2">
            {destinosPosibles.map((c) => (
              <button
                key={c.id}
                onClick={() => setCuentaDestinoId(c.id)}
                aria-pressed={destinoId === c.id}
                className={`rounded-2xl border py-3 px-3 text-left ${
                  destinoId === c.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
                }`}
              >
                <p className="text-sm font-medium truncate">{c.nombre}</p>
                <p className="text-[11px] text-ink-soft mt-0.5">{formatMoneda(c.saldo, c.moneda)}</p>
              </button>
            ))}
          </div>
          {destinosPosibles.find((c) => c.id === destinoId)?.tipo === 'credito' && (
            <p role="note" data-testid="aviso-pago-tarjeta" className="mt-2 rounded-xl bg-accent-soft text-ink p-3 text-xs flex gap-2">
              <Icono icono={Info} tam="sm" className="text-accent mt-0.5" />
              <span>
                <b>Esto no es un gasto nuevo, es pagar lo que ya compraste.</b> Tu deuda en la tarjeta baja y el gasto ya
                lo contaste cuando hiciste la compra. Si pagas el total del extracto antes de la fecha límite, no pagas intereses.
              </span>
            </p>
          )}
          {cuentaActual && destinosPosibles.find((c) => c.id === destinoId)?.moneda !== cuentaActual.moneda && (
            <p className="text-xs text-danger mt-2">Las cuentas tienen monedas distintas; aún no se pueden transferir entre sí.</p>
          )}
        </div>
      )}

      {!esTransferencia && (
      <div className="px-5 mb-5">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Categoría</p>
        <div className="grid grid-cols-3 gap-2">
          {categoriasRapidas.map((c) => (
            <button
              key={c}
              onClick={() => {
                setCategoria(c)
                setCategoriaAutoDetectada(false)
              }}
              className={`rounded-2xl border py-3 text-sm font-medium ${
                categoria === c ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>
      )}

      {error && <p className="px-5 text-sm text-danger mb-3">{error}</p>}

      {posibleDuplicado && (
        <div className="mx-5 mb-4 rounded-2xl border border-accent bg-accent-soft p-4" role="alert" data-testid="posible-duplicado">
          <p className="text-sm font-semibold">Parece que ya lo tienes</p>
          <p className="text-sm mt-1">{posibleDuplicado}</p>
          <div className="flex flex-col gap-2 mt-3">
            <button
              onClick={volver}
              className="rounded-xl bg-ink text-paper py-2.5 min-h-[44px] text-sm font-semibold"
            >
              Es el mismo, no lo agregues
            </button>
            <button
              onClick={() => guardar(true)}
              disabled={guardando}
              className="rounded-xl border border-line bg-paper-raised py-2.5 min-h-[44px] text-sm font-semibold disabled:opacity-60"
            >
              Es otro gasto igual, agrégalo
            </button>
          </div>
        </div>
      )}

      <div className="px-5">
        <button
          onClick={() => guardar()}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] active:scale-[0.98] transition-transform disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : esTransferencia ? 'Hacer transferencia' : 'Guardar movimiento'}
        </button>
        <button onClick={() => navigate('/amigos')} className="w-full text-center text-sm text-accent font-medium mt-4">
          Cuentas con amigos
        </button>
      </div>
    </div>
  )
}
