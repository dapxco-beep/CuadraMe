import { CheckCircle2, ChevronRight, FileCheck2, FileClock, KeyRound, Mail, RefreshCw, Tag, Wallet, Scale, CopyCheck, AlertTriangle, CalendarDays, CheckCheck } from 'lucide-react'
import BarraProgreso from './BarraProgreso'

// La tarjeta única de «Traer movimientos»: UN estado grande y calmado, UNA acción principal, y un solo
// botón secundario «Buscar ahora» con su progreso en línea. Todo lo demás vive detrás de «Ver todo».
// Es presentacional: la pantalla decide qué hace cada botón.

const ICONO = {
  conectar: Mail,
  punto_partida: CalendarDays,
  falta_clave: KeyRound,
  sin_cuenta: Wallet,
  a_medias: FileClock,
  extractos_por_conciliar: FileCheck2,
  correos_por_revisar: Mail,
  movimientos_por_confirmar: CheckCheck,
  movimientos_por_categorizar: Tag,
  cuadre_no_cuadra: Scale,
  posibles_duplicados: CopyCheck,
  extractos_sin_leer: AlertTriangle,
}

export default function PasoGuiado({
  estado, // { alDia, titulo }
  progreso = null, // { n, de, pct }
  paso = null, // el paso principal
  siguientes = [], // lo que viene después (pasos)
  recien = false, // acaba de resolverse un paso
  onPaso,
  buscando = '', // texto de lo que se está leyendo; vacío = quieto
  pctBusqueda = 0,
  onBuscar,
  puedeBuscar = true,
  ultima = '',
  resumen = '',
  error = '',
  onVerTodo,
  sugerencia = null, // un paso opcional que se ofrece cuando todo está al día
  onSugerencia,
  conectado = true,
}) {
  const Icono = (paso && ICONO[paso.id]) || CheckCheck
  const ocupado = Boolean(buscando)
  return (
    <section className="rounded-3xl bg-paper-raised ring-1 ring-line/60 shadow-[0_1px_3px_rgba(34,31,25,0.04)] p-5" aria-label="Qué sigue" data-testid="paso-guiado">
      {progreso && progreso.de > 1 && (
        <div className="mb-4" data-testid="progreso-pasos">
          <p className="text-xs font-semibold text-ink-soft">Paso {progreso.n} de {progreso.de}</p>
          <BarraProgreso pct={progreso.pct} label={`Paso ${progreso.n} de ${progreso.de}`} texto={`Paso ${progreso.n} de ${progreso.de}`} className="h-1 rounded-full bg-line overflow-hidden mt-1.5" fillClass="" />
        </div>
      )}

      {recien && (
        <p className="text-sm font-semibold text-cuadra flex items-center gap-1.5 mb-2" role="status" data-testid="paso-listo">
          <CheckCircle2 size={16} aria-hidden="true" />
          {paso ? 'Listo ✓ — siguiente:' : 'Listo ✓'}
        </p>
      )}

      {estado.alDia ? (
        <>
          <div className="flex items-center gap-3.5">
            <span className="w-12 h-12 rounded-full bg-cuadra-soft text-cuadra flex items-center justify-center shrink-0">
              <CheckCircle2 size={24} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h2 className="text-2xl font-bold leading-tight" data-testid="todo-al-dia">Todo al día</h2>
              <p className="text-sm text-ink-soft mt-0.5" data-testid="resumen-tareas">
                {!conectado ? 'Gmail sin conectar: conéctalo y traigo tus movimientos solo' : ultima ? `Miré tu correo ${ultima}` : 'No hay nada que hacer ahora'}
              </p>
            </div>
          </div>
          {sugerencia && (
            <button
              type="button"
              onClick={() => onSugerencia?.(sugerencia)}
              data-testid={`tarea-${sugerencia.id}`}
              className="mt-4 w-full flex items-center justify-between gap-2 rounded-2xl bg-paper px-4 min-h-[52px] text-left text-sm font-semibold"
            >
              <span>{sugerencia.titulo} <span className="font-normal text-ink-soft">(si quieres)</span></span>
              <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
            </button>
          )}
        </>
      ) : (
        <>
          <h2 className="text-sm font-semibold text-ink-soft" data-testid="resumen-tareas">{estado.titulo}</h2>
          {paso && (
            <div className="mt-3 flex items-start gap-3.5">
              <span className="w-11 h-11 rounded-2xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                <Icono size={24} strokeWidth={1.75} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="text-xl font-bold leading-snug" data-testid="paso-titulo">{paso.titulo}</p>
                {paso.detalle && <p className="text-sm text-ink-soft mt-1">{paso.detalle}</p>}
              </div>
            </div>
          )}
          {paso && (
            <button
              type="button"
              onClick={() => onPaso(paso)}
              data-testid={`tarea-${paso.id}`}
              className="mt-4 w-full flex items-center justify-center gap-2 bg-ink text-paper font-semibold rounded-2xl min-h-[52px] text-[15px] active:scale-[0.99] motion-reduce:active:scale-100"
            >
              {paso.boton} <ChevronRight size={16} aria-hidden="true" />
            </button>
          )}
          {siguientes.length > 0 && (
            <p className="mt-3 text-xs text-ink-soft text-center" data-testid="despues">
              Después: {siguientes[0].titulo.charAt(0).toLowerCase() + siguientes[0].titulo.slice(1)}{siguientes.length > 1 ? ` y ${siguientes.length - 1} más` : ''}
            </p>
          )}
        </>
      )}

      <div className="mt-4 pt-3 border-t border-line/50" aria-live="polite" role="status">
        {ocupado ? (
          <div data-testid="buscando">
            <BarraProgreso pct={pctBusqueda} label="Progreso de la búsqueda" className="h-1.5 rounded-full bg-line overflow-hidden" fillClass="" />
            <p className="text-xs text-ink-soft mt-1.5 flex items-center gap-1.5">
              <RefreshCw size={16} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> {buscando}
            </p>
          </div>
        ) : (
          <>
            {error && <p className="text-xs text-danger mb-2" role="alert">{error}</p>}
            {resumen && !error && <p className="text-xs text-ink-soft mb-2" data-testid="resumen-busqueda">{resumen}</p>}
            <div className="flex items-center justify-between gap-3">
              {paso?.id === 'conectar' ? <span /> : <button
                type="button"
                onClick={onBuscar}
                data-testid="buscar-ahora"
                className="flex items-center gap-1.5 text-sm font-semibold text-accent min-h-[44px] pr-2"
              >
                {puedeBuscar ? <><RefreshCw size={16} aria-hidden="true" /> Buscar ahora</> : <><Mail size={16} aria-hidden="true" /> Conectar Gmail</>}
              </button>}
              <button type="button" onClick={onVerTodo} data-testid="ver-todo" className="flex items-center gap-1 text-sm font-semibold text-ink-soft min-h-[44px] pl-2">
                Ver todo <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
            {!estado.alDia && ultima && <p className="text-[11px] text-ink-soft">Miré tu correo {ultima}</p>}
          </>
        )}
      </div>
    </section>
  )
}
