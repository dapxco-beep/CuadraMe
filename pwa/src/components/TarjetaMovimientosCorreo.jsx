import { Link } from 'react-router-dom'
import { Loader2, Mail, RefreshCw } from 'lucide-react'

/**
 * «Movimientos del correo»: la sección aparte de Movimientos para los avisos de compras y transferencias que tu banco
 * manda al correo. Dice si el correo está conectado, cuántos esperan tu revisión, deja traerlos ahora y lleva a la
 * pantalla completa. (Los extractos en PDF viven en «Traer extractos»; aquí solo lo del día a día.)
 *
 *   conectado: true | false | null (aún no se sabe)   leyendo: lectura en curso   aviso: frase del último resultado
 */
export default function TarjetaMovimientosCorreo({ conectado = null, leyendo = false, aviso = '', porRevisar = 0, onTraer, className = '' }) {
  return (
    <section className={`rounded-2xl border border-line bg-paper-raised p-4 ${className}`} aria-label="Movimientos del correo" data-testid="tarjeta-correo">
      <div className="flex items-start gap-3">
        <span className="w-10 h-10 shrink-0 rounded-xl bg-accent-soft text-accent flex items-center justify-center">
          <Mail size={20} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">Movimientos del correo</h2>
          <p className="text-xs text-ink-soft mt-0.5">
            {conectado === false
              ? 'Conecta tu correo y tus compras se anotan solas.'
              : porRevisar > 0
                ? `${porRevisar} ${porRevisar === 1 ? 'aviso espera' : 'avisos esperan'} tu revisión.`
                : 'Los avisos de tu banco llegan aquí.'}
          </p>
        </div>
      </div>

      <p role="status" aria-live="polite" className="text-xs text-ink-soft mt-2 min-h-[16px]" data-testid="estado-correo">
        {leyendo ? 'Leyendo tu correo…' : aviso}
      </p>

      <div className="mt-3 flex gap-2">
        {conectado === false ? (
          <Link to="/movimientos-correo" state={{ abrir: 'conexion' }} className="flex-1 min-h-11 rounded-xl bg-ink text-paper text-sm font-semibold flex items-center justify-center">
            Conectar mi correo
          </Link>
        ) : (
          <>
            <button
              type="button"
              onClick={onTraer}
              disabled={leyendo || conectado === null}
              className="flex-1 min-h-11 rounded-xl bg-ink text-paper text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {leyendo ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
              {leyendo ? 'Leyendo…' : 'Traer del correo'}
            </button>
            <Link to="/movimientos-correo" className="min-h-11 px-4 rounded-xl border border-line text-sm font-semibold flex items-center justify-center">
              {porRevisar > 0 ? `Revisar (${porRevisar})` : 'Ver todo'}
            </Link>
          </>
        )}
      </div>
    </section>
  )
}
