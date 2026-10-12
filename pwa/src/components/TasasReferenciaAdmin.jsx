import { useEffect, useState } from 'react'
import { AlertTriangle, Pencil, Plus, Sprout, X } from 'lucide-react'
import { api } from '../lib/api'
import { fechaCorta, formatTasa, leerTasa } from '../lib/rendimientos'
import Hoja from './Hoja'
import Icono from './Icono'
import { Boton, CampoTexto, Tarjeta } from './ui'

const TIPOS = [
  ['ahorro_vista', 'Ahorro a la vista (cajita o bolsillo)'],
  ['saldo_principal', 'Saldo principal'],
  ['cdt', 'CDT'],
]
const hoyISO = () => new Date().toLocaleDateString('en-CA')

/** Panel de administración: tasas de referencia de «Tu plata trabajando» (editables, fechadas; aviso si pasan de 45 días). */
export default function TasasReferenciaAdmin() {
  const [tasas, setTasas] = useState(null)
  const [editando, setEditando] = useState(null) // fila o {} (nueva)
  const cargar = () =>
    Promise.resolve()
      .then(() => api.tasasReferenciaAdmin?.())
      .then((r) => setTasas(r?.tasas || []))
      .catch(() => setTasas([]))
  useEffect(() => {
    cargar()
  }, [])
  if (!tasas) return null
  const viejas = tasas.filter((t) => t.activa && t.tasa_ea != null && t.desactualizada)
  return (
    <section className="mx-5 mt-4" aria-labelledby="tasas-titulo" data-testid="tasas-admin">
      <div className="flex items-center justify-between">
        <h2 id="tasas-titulo" className="t-kicker text-ink-soft flex items-center gap-1.5">
          <Icono icono={Sprout} tam="sm" /> Tasas de referencia
        </h2>
        <button type="button" onClick={() => setEditando({})} className="text-sm text-accent font-medium min-h-11 inline-flex items-center gap-1">
          <Icono icono={Plus} tam="sm" /> Agregar
        </button>
      </div>
      {viejas.length > 0 && (
        <Tarjeta className="px-4 py-3 bg-danger-soft mb-2" role="alert" data-testid="tasas-viejas">
          {viejas.map((t) => (
            <p key={t.id} className="text-sm">
              <Icono icono={AlertTriangle} tam="sm" className="inline mr-1 text-danger" />
              <b>{t.entidad} · {t.producto}</b> lleva {t.dias_sin_actualizar} días sin actualizarse. Verifícala y vuelve a guardarla.
            </p>
          ))}
        </Tarjeta>
      )}
      <Tarjeta variante="lista">
        <ul className="divide-y divide-line">
          {tasas.map((t) => (
            <li key={t.id} className="flex items-center gap-3 px-4 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{t.entidad} · {t.producto}{t.activa ? '' : ' (oculta)'}</p>
                <p className="text-xs text-ink-soft">
                  {t.tasa_ea == null ? 'Sin cifra' : `${formatTasa(t.tasa_ea)} E.A.`} · vigente desde {fechaCorta(t.vigente_desde)}
                </p>
              </div>
              <button type="button" onClick={() => setEditando(t)} className="w-11 h-11 flex items-center justify-center text-ink-soft" aria-label={`Editar ${t.entidad} ${t.producto}`}>
                <Icono icono={Pencil} tam="sm" />
              </button>
            </li>
          ))}
        </ul>
      </Tarjeta>
      {editando && <FormTasa tasa={editando} onCerrar={() => setEditando(null)} onGuardada={() => { setEditando(null); cargar() }} />}
    </section>
  )
}

function FormTasa({ tasa, onCerrar, onGuardada }) {
  const [f, setF] = useState({
    entidad: tasa.entidad || '',
    producto: tasa.producto || '',
    tipo: tasa.tipo || 'ahorro_vista',
    tasa_ea: tasa.tasa_ea == null ? '' : String(tasa.tasa_ea).replace('.', ','),
    vigente_desde: tasa.vigente_desde || hoyISO(),
    fuente_url: tasa.fuente_url || '',
    nota: tasa.nota || '',
    activa: tasa.activa !== false,
  })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  async function guardar() {
    const t = leerTasa(f.tasa_ea)
    if (!f.entidad.trim() || !f.producto.trim()) return setError('Escribe la entidad y el producto.')
    if (Number.isNaN(t)) return setError('La tasa debe ser un número entre 0 y 100.')
    try {
      await api.guardarTasaReferencia(tasa.id, {
        entidad: f.entidad.trim(), producto: f.producto.trim(), tipo: f.tipo, tasa_ea: t,
        vigente_desde: f.vigente_desde || hoyISO(), fuente_url: f.fuente_url.trim() || null,
        nota: f.nota.trim() || null, activa: f.activa,
      })
      onGuardada()
    } catch (err) {
      setError(err.message || 'No pudimos guardar la tasa.')
    }
  }

  return (
    <Hoja onCerrar={onCerrar} ariaLabel="Editar tasa de referencia" historial={false}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">{tasa.id ? 'Editar tasa' : 'Nueva tasa'}</h2>
        <button type="button" onClick={onCerrar} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <Icono icono={X} tam="sm" />
        </button>
      </div>
      <div className="space-y-3">
        <CampoTexto etiqueta="Entidad" value={f.entidad} onChange={set('entidad')} maxLength={80} />
        <CampoTexto etiqueta="Producto" value={f.producto} onChange={set('producto')} maxLength={80} />
        <label className="block">
          <span className="campo-etiqueta">Tipo</span>
          <select value={f.tipo} onChange={set('tipo')} className="campo-entrada">
            {TIPOS.map(([id, t]) => <option key={id} value={id}>{t}</option>)}
          </select>
        </label>
        <CampoTexto etiqueta="Tasa E.A. (%) — vacío si no hay cifra verificada" value={f.tasa_ea} onChange={set('tasa_ea')} inputMode="decimal" />
        <CampoTexto etiqueta="Vigente desde" type="date" value={f.vigente_desde} onChange={set('vigente_desde')} />
        <CampoTexto etiqueta="Fuente (enlace)" value={f.fuente_url} onChange={set('fuente_url')} maxLength={300} />
        <CampoTexto etiqueta="Nota" value={f.nota} onChange={set('nota')} maxLength={300} />
        <label className="flex items-center gap-2 text-sm min-h-11">
          <input type="checkbox" checked={f.activa} onChange={(e) => setF((x) => ({ ...x, activa: e.target.checked }))} /> Visible para las personas
        </label>
      </div>
      {error && <p role="alert" className="text-sm text-danger mt-3">{error}</p>}
      <div className="mt-4">
        <Boton bloque onClick={guardar}>Guardar</Boton>
      </div>
    </Hoja>
  )
}
