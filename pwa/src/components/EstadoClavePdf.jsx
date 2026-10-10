import { useState } from 'react'
import { AlertTriangle, CheckCircle2, CircleHelp, KeyRound, Loader2 } from 'lucide-react'

// Clave de los PDF: estado visible y confiable. Responde a «¿la cogió o no?» sin mostrar nunca la clave:
//   · «Clave guardada ✓» (o «Sin clave guardada»)
//   · cuántos extractos protegidos abrió, cuáles no y cuáles faltan por probar, por banco
//   · «Probar la clave ahora» y el resultado explícito de la última prueba
//
// `info` es GET /correos/clave-pdf: { configurada, cantidad_claves, protegidos, abrieron, no_abrieron,
// por_probar, por_banco[], extractos[] }. Todo es opcional: sin datos solo se ve guardar/borrar.

const ICONO = { abrio: CheckCircle2, no_abrio: AlertTriangle, por_probar: CircleHelp, sin_clave: CircleHelp }
const TEXTO = {
  abrio: 'La clave abrió este extracto',
  no_abrio: 'La clave no lo abrió: revísala',
  por_probar: 'Por probar',
  sin_clave: 'Falta la clave',
}
const COLOR = { abrio: 'text-cuadra', no_abrio: 'text-danger', por_probar: 'text-ink-soft', sin_clave: 'text-ink-soft' }

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

/** Frase corta del estado general, para el título y para pruebas. */
export function textoEstadoClave(info) {
  if (!info?.configurada) return 'Sin clave guardada'
  const n = info.cantidad_claves || 1
  return n > 1 ? `Clave guardada ✓ (${n} claves)` : 'Clave guardada ✓'
}

export default function EstadoClavePdf({
  info, onGuardar, onBorrar, onProbar, probando = false, resultado = null, mensaje = '', error = '', id = 'sinc-clave',
}) {
  const [clave, setClave] = useState('')
  const configurada = Boolean(info?.configurada)
  const protegidos = info?.protegidos || 0
  const extractos = Array.isArray(info?.extractos) ? info.extractos : []
  const bancos = Array.isArray(info?.por_banco) ? info.por_banco : []
  const hayQueProbar = configurada && (protegidos - (info?.abrieron || 0) > 0 || resultado == null)

  async function guardar() {
    const v = clave.trim()
    if (!v) return
    setClave('')
    await onGuardar?.(v)
  }

  return (
    <div id={id} className="rounded-2xl bg-paper border border-line p-4 mb-3" data-testid="estado-clave-pdf">
      <div className="flex items-start justify-between gap-2 mb-1">
        <p className="flex items-center gap-1.5 text-xs font-semibold min-w-0">
          <KeyRound size={16} aria-hidden="true" className="shrink-0" /> Clave del PDF
        </p>
        <span
          className={`shrink-0 inline-flex items-center gap-1 text-[11px] font-semibold rounded-full px-2 py-0.5 ${
            configurada ? 'bg-cuadra-soft text-cuadra' : 'bg-line text-ink-soft'
          }`}
          data-testid="clave-estado"
        >
          {textoEstadoClave(info)}
        </span>
      </div>
      <p className="text-xs text-ink-soft mb-2">
        {configurada ? 'Hay una clave guardada.' : 'Normalmente es tu cédula.'} Se guarda cifrada y no se muestra de nuevo.
        Si tus bancos usan claves distintas, sepáralas con una coma.
      </p>

      {configurada && protegidos > 0 && (
        <div className="rounded-xl bg-paper-raised border border-line px-3 py-2.5 mb-3" data-testid="clave-resumen">
          <p className="text-xs font-semibold">
            {plural(protegidos, 'extracto protegido', 'extractos protegidos')}
            {` · abrió ${info.abrieron || 0}`}
            {info.no_abrieron ? ` · no abrió ${info.no_abrieron}` : ''}
            {info.por_probar ? ` · por probar ${info.por_probar}` : ''}
          </p>
          {bancos.length > 0 && (
            <ul className="mt-1.5 space-y-1">
              {bancos.map((b) => (
                <li key={b.banco} className="text-xs text-ink-soft flex justify-between gap-2">
                  <span className="truncate">{b.banco}</span>
                  <span className="shrink-0">
                    {b.abrieron ? `✓ ${b.abrieron}` : ''}
                    {b.no_abrieron ? ` ✕ ${b.no_abrieron}` : ''}
                    {b.por_probar ? ` ? ${b.por_probar}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {extractos.length > 0 && (
            <ul className="mt-2 space-y-1.5" aria-label="Resultado por extracto">
              {extractos.map((x) => {
                const Icono = ICONO[x.resultado] || CircleHelp
                return (
                  <li key={x.id} className={`flex items-start gap-1.5 text-xs ${COLOR[x.resultado] || 'text-ink-soft'}`}>
                    <Icono size={16} className="shrink-0" aria-hidden="true" />
                    <span className="min-w-0 break-words">
                      <span className="font-medium">{x.nombre}</span> · {TEXTO[x.resultado] || ''}
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <input
          type="password"
          autoComplete="off"
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          placeholder={configurada ? 'Nueva clave' : 'Clave (ej. tu cédula)'}
          aria-label="Clave del PDF"
          className="flex-1 min-w-0 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          onClick={guardar}
          disabled={!clave.trim()}
          className="px-4 min-h-[44px] rounded-xl bg-ink text-paper text-sm font-semibold disabled:opacity-50"
        >
          Guardar
        </button>
      </div>

      {configurada && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2">
          {onProbar && (
            <button
              type="button"
              onClick={() => onProbar()}
              disabled={probando}
              className="min-h-[44px] inline-flex items-center gap-1.5 text-sm font-semibold text-accent disabled:opacity-60"
            >
              {probando && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
              {probando ? 'Probando la clave…' : hayQueProbar || protegidos === 0 ? 'Probar la clave ahora' : 'Volver a probar la clave'}
            </button>
          )}
          <button onClick={onBorrar} className="text-xs text-danger min-h-[44px]">Borrar la clave guardada</button>
        </div>
      )}

      <div aria-live="polite" role="status">
        {mensaje && (
          <p
            className={`text-xs font-medium mt-2 rounded-xl px-3 py-2 ${
              resultado && resultado.no_abrieron ? 'bg-danger-soft text-danger' : 'bg-cuadra-soft text-cuadra'
            }`}
            data-testid="clave-resultado"
          >
            {mensaje}
          </p>
        )}
      </div>
      {error && <p className="text-xs text-danger mt-2" role="alert">{error}</p>}
    </div>
  )
}
