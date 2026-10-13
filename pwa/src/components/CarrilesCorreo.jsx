import { useState } from 'react'
import { BellRing, ChevronDown, FileCheck2, Loader2, RefreshCw } from 'lucide-react'
import { haceCuanto } from '../lib/sincronizarGmail'
import { BOTON_CARRIL, EJEMPLO_CARRIL, NOMBRE_CARRIL, TEXTO_CARRIL, contadoresCarril } from '../lib/carriles'

const ICONO = { movimientos: BellRing, extractos: FileCheck2 }

/**
 * Las DOS lecturas del correo, cada una en su tarjeta: «Movimientos del día a día» (notificaciones del
 * banco) y «Extractos para conciliar» (PDF del estado de cuenta). Cada una con su interruptor, su botón,
 * su última vez, sus contadores y su propio error: si una falla, la otra sigue funcionando.
 *   gmail:     GET /correos/gmail/estado (leer_movimientos / leer_extractos)
 *   carriles:  GET /sincronizacion/estado -> carriles (puede faltar: se muestra sin contadores)
 *   activos:   { movimientos, extractos } — lo que el usuario dejó encendido
 *   leyendo:   { movimientos?: {leidos,total_estimado}, extractos?: {...} } — lectura en curso
 *   resultados:{ movimientos?: 'texto', extractos?: 'texto' }   errores: { movimientos?: 'texto', ... }
 */
export default function CarrilesCorreo({ activos, carriles, leyendo = {}, resultados = {}, errores = {}, onTraer, onCambiar, guardando = {} }) {
  const [ayuda, setAyuda] = useState(false)
  const ocupado = Boolean(leyendo.movimientos || leyendo.extractos)

  return (
    <section aria-label="Qué leer de tu correo" className="mt-4" data-testid="carriles-correo">
      <div className="flex items-center justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold">Qué leer de tu correo</h3>
        <button
          type="button"
          onClick={() => setAyuda((v) => !v)}
          aria-expanded={ayuda}
          className="flex items-center gap-1 text-xs font-semibold text-accent min-h-[44px] px-1"
        >
          ¿Cuál es la diferencia?
          <ChevronDown size={16} className={`transition-transform ${ayuda ? 'rotate-180' : ''}`} aria-hidden="true" />
        </button>
      </div>

      {ayuda && (
        <div className="rounded-2xl bg-accent-soft border border-accent/30 p-3 mb-3 text-xs leading-relaxed" role="note" data-testid="ayuda-carriles">
          <p><b>{NOMBRE_CARRIL.movimientos}.</b> {EJEMPLO_CARRIL.movimientos}</p>
          <p className="mt-2"><b>{NOMBRE_CARRIL.extractos}.</b> {EJEMPLO_CARRIL.extractos}</p>
          <p className="mt-2 text-ink-soft">Puedes dejar uno solo encendido; el otro no se lee ni se guarda nada de él.</p>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {['movimientos', 'extractos'].map((carril) => {
          const Icono = ICONO[carril]
          const activo = activos[carril] !== false
          const info = carriles?.[carril]
          const ultima = haceCuanto(info?.ultima_vez)
          const lee = leyendo[carril]
          const contadores = contadoresCarril(carril, info)
          return (
            <article key={carril} className="rounded-2xl bg-paper border border-line p-4" data-testid={`carril-${carril}`} aria-label={NOMBRE_CARRIL[carril]}>
              <div className="flex items-start gap-3">
                <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                  <Icono size={20} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <h4 className="text-[15px] font-semibold leading-tight">{NOMBRE_CARRIL[carril]}</h4>
                  <p className="text-xs text-ink-soft mt-0.5">{TEXTO_CARRIL[carril]}</p>
                </div>
              </div>

              <label className="flex items-center justify-between gap-3 mt-3 min-h-[44px] text-sm font-medium">
                <span>Leer esto de mi correo</span>
                <input
                  type="checkbox"
                  role="switch"
                  checked={activo}
                  disabled={Boolean(guardando[carril])}
                  onChange={(e) => onCambiar(carril, e.target.checked)}
                  aria-label={`Leer ${NOMBRE_CARRIL[carril].toLowerCase()} de mi correo`}
                  className="w-6 h-6 accent-[var(--color-accent,#0f766e)] shrink-0"
                />
              </label>

              {activo ? (
                <>
                  <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-ink-soft" aria-label={`Conteo de ${NOMBRE_CARRIL[carril].toLowerCase()}`}>
                    {contadores.map((c) => <li key={c.clave}>{c.texto}</li>)}
                  </ul>
                  <p className="text-[11px] text-ink-soft mt-1.5" data-testid={`ultima-${carril}`}>
                    {ultima ? `Última vez ${ultima}` : 'Aún no he leído esto de tu correo'}
                  </p>
                  <button
                    type="button"
                    onClick={() => onTraer(carril)}
                    disabled={ocupado}
                    className="mt-3 w-full flex items-center justify-center gap-2 border border-line bg-paper-raised font-semibold rounded-xl min-h-[44px] text-sm disabled:opacity-60"
                  >
                    {lee ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
                    {lee ? (lee.total_estimado ? `Leyendo ${lee.leidos} de ${lee.total_estimado}` : 'Buscando...') : BOTON_CARRIL[carril]}
                  </button>
                  {resultados[carril] && !errores[carril] && !lee && (
                    <p className="text-xs font-semibold text-cuadra mt-2" role="status" data-testid={`resultado-${carril}`}>{resultados[carril]}</p>
                  )}
                  {errores[carril] && (
                    <p className="text-xs text-danger mt-2" role="alert" data-testid={`error-${carril}`}>
                      {NOMBRE_CARRIL[carril]}: {errores[carril]}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-xs text-ink-soft mt-2 rounded-xl bg-paper-raised border border-line px-3 py-2.5" data-testid={`apagado-${carril}`}>
                  Apagado: no leo ni guardo {carril === 'movimientos' ? 'notificaciones' : 'extractos'} de tu correo. Enciéndelo cuando quieras.
                </p>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
