import { useState } from 'react'
import { ChevronDown, Loader2, RefreshCw } from 'lucide-react'
import { haceCuanto } from '../lib/sincronizarGmail'
import { BOTON_CARRIL, EJEMPLO_CARRIL, NOMBRE_CARRIL, TEXTO_CARRIL, contadoresCarril } from '../lib/carriles'

/**
 * Los DOS usos del correo, cada uno con su pieza:
 *   - LecturaCarril: el estado de UN uso dentro de su sección («Movimientos» o «Extractos»): contadores,
 *     última vez, botón de leer, resultado y error propios. Si uno falla, el otro sigue funcionando.
 *   - InterruptoresLectura: los dos interruptores («Leer notificaciones», «Leer extractos») y la ayudita
 *     «¿cuál es la diferencia?», que viven juntos en la sección «Conexión de Gmail».
 *
 *   gmail:     GET /correos/gmail/estado (leer_movimientos / leer_extractos)
 *   info:      GET /sincronizacion/estado -> carriles[carril] (puede faltar: se muestra sin contadores)
 *   leyendo:   { movimientos?: {leidos,total_estimado}, extractos?: {...} } — lectura en curso
 */
export function LecturaCarril({ carril, activo = true, info, leyendo = {}, resultado = '', error = '', onTraer, onEncender, children }) {
  const ultima = haceCuanto(info?.ultima_vez)
  const lee = leyendo[carril]
  const ocupado = Boolean(leyendo.movimientos || leyendo.extractos)
  const contadores = contadoresCarril(carril, info)
  return (
    <div className="rounded-2xl bg-paper border border-line p-4" data-testid={`carril-${carril}`} aria-label={`Lectura de ${NOMBRE_CARRIL[carril].toLowerCase()} del correo`}>
      <p className="text-xs text-ink-soft">{TEXTO_CARRIL[carril]}</p>
      {activo ? (
        <>
          <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-ink-soft" aria-label={`Conteo de ${NOMBRE_CARRIL[carril].toLowerCase()}`}>
            {contadores.map((c) => <li key={c.clave}>{c.texto}</li>)}
          </ul>
          <p className="text-[11px] text-ink-soft mt-1.5" data-testid={`ultima-${carril}`}>
            {ultima ? `Última vez ${ultima}` : 'Aún no he leído esto de tu correo'}
          </p>
          {children}
          <button
            type="button"
            onClick={() => onTraer(carril)}
            disabled={ocupado}
            className="mt-3 w-full flex items-center justify-center gap-2 border border-line bg-paper-raised font-semibold rounded-xl min-h-[44px] text-sm disabled:opacity-60"
          >
            {lee ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
            {lee ? (lee.total_estimado ? `Leyendo ${lee.leidos} de ${lee.total_estimado}` : 'Buscando...') : BOTON_CARRIL[carril]}
          </button>
          {resultado && !error && !lee && (
            <p className="text-xs font-semibold text-cuadra mt-2" role="status" data-testid={`resultado-${carril}`}>{resultado}</p>
          )}
          {error && (
            <p className="text-xs text-danger mt-2" role="alert" data-testid={`error-${carril}`}>
              {NOMBRE_CARRIL[carril]}: {error}
            </p>
          )}
        </>
      ) : (
        <div className="mt-2 rounded-xl bg-paper-raised border border-line px-3 py-2.5" data-testid={`apagado-${carril}`}>
          <p className="text-xs text-ink-soft">
            Apagado: no leo ni guardo {carril === 'movimientos' ? 'notificaciones' : 'extractos'} de tu correo.
          </p>
          {onEncender && (
            <button type="button" onClick={onEncender} className="mt-1 text-xs font-semibold text-accent min-h-[44px]">
              Encenderlo en «Conexión de Gmail»
            </button>
          )}
        </div>
      )}
    </div>
  )
}

const ETIQUETA_INTERRUPTOR = { movimientos: 'Leer notificaciones', extractos: 'Leer extractos' }
const AYUDA_INTERRUPTOR = {
  movimientos: 'Los avisos de compras y transferencias de tu banco.',
  extractos: 'El PDF mensual del banco, para confirmar y cuadrar el mes.',
}

export function InterruptoresLectura({ activos, errores = {}, onCambiar, guardando = {} }) {
  const [ayuda, setAyuda] = useState(false)
  return (
    <section aria-label="Qué leer de tu correo" className="mt-4" data-testid="carriles-correo">
      <div className="flex items-center justify-between gap-2 mb-1">
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
        <div className="rounded-2xl bg-accent-soft border border-accent/30 p-3 mb-2 text-xs leading-relaxed" role="note" data-testid="ayuda-carriles">
          <p><b>{NOMBRE_CARRIL.movimientos}.</b> {EJEMPLO_CARRIL.movimientos}</p>
          <p className="mt-2"><b>{NOMBRE_CARRIL.extractos}.</b> {EJEMPLO_CARRIL.extractos}</p>
          <p className="mt-2 text-ink-soft">Puedes dejar uno solo encendido; el otro no se lee ni se guarda nada de él.</p>
        </div>
      )}

      <ul className="rounded-2xl bg-paper border border-line divide-y divide-line">
        {['movimientos', 'extractos'].map((carril) => (
          <li key={carril} data-testid={`interruptor-${carril}`}>
            <label className="flex items-center justify-between gap-3 px-4 py-2 min-h-[56px] text-sm font-medium">
              <span className="min-w-0">
                {ETIQUETA_INTERRUPTOR[carril]}
                <span className="block text-xs font-normal text-ink-soft">{AYUDA_INTERRUPTOR[carril]}</span>
              </span>
              <input
                type="checkbox"
                role="switch"
                checked={activos[carril] !== false}
                disabled={Boolean(guardando[carril])}
                onChange={(e) => onCambiar(carril, e.target.checked)}
                aria-label={`${ETIQUETA_INTERRUPTOR[carril]} de mi correo`}
                className="w-6 h-6 accent-[var(--color-accent,#0f766e)] shrink-0"
              />
            </label>
            {errores[carril] && (
              <p className="text-xs text-danger px-4 pb-2" role="alert">{NOMBRE_CARRIL[carril]}: {errores[carril]}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
