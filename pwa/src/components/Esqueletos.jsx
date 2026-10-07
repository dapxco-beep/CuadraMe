// Esqueletos de carga con la forma de cada pantalla (reemplazan los «Cargando…» de texto).
// Reglas:
//  - Misma altura que el contenido real → sin saltos de layout (CLS) cuando llegan los datos.
//  - role="status" + aria-busy: un solo aviso accesible por esqueleto, no uno por barra.
//  - El brillo (.skeleton) se apaga con prefers-reduced-motion (ver index.css): queda un bloque quieto.

const junta = (...c) => c.filter(Boolean).join(' ')

function Contenedor({ etiqueta = 'Cargando', className, children, ...resto }) {
  return (
    <div role="status" aria-busy="true" aria-label={etiqueta} className={className} {...resto}>
      {children}
    </div>
  )
}

export function Bloque({ className, style }) {
  return <div aria-hidden="true" className={junta('skeleton', className)} style={style} />
}

// Líneas de texto; la última más corta, como un párrafo real
export function EsqueletoTexto({ lineas = 3, className, etiqueta }) {
  return (
    <Contenedor etiqueta={etiqueta} className={junta('space-y-2', className)}>
      {Array.from({ length: lineas }, (_, i) => (
        <Bloque key={i} className="h-3.5" style={{ width: i === lineas - 1 && lineas > 1 ? '60%' : '100%' }} />
      ))}
    </Contenedor>
  )
}

// Tarjeta grande (héroe, resumen): alto fijo
export function EsqueletoTarjeta({ alto = 160, className, etiqueta }) {
  return (
    <Contenedor etiqueta={etiqueta} className={className}>
      <Bloque className="w-full" style={{ height: alto, borderRadius: '18px 30px 18px 18px' }} />
    </Contenedor>
  )
}

// Una fila de lista: ícono circular + dos líneas + monto (misma altura que una fila real, 64 px)
export function EsqueletoFila({ className }) {
  return (
    <div aria-hidden="true" className={junta('flex items-center gap-3 px-4 h-16', className)}>
      <Bloque className="w-10 h-10 rounded-full! shrink-0" />
      <div className="flex-1 space-y-2">
        <Bloque className="h-3.5 w-2/3" />
        <Bloque className="h-3 w-1/3" />
      </div>
      <Bloque className="h-4 w-16" />
    </div>
  )
}

export function EsqueletoLista({ filas = 5, className, etiqueta }) {
  return (
    <Contenedor etiqueta={etiqueta} className={junta('tarjeta-lista', className)}>
      {Array.from({ length: filas }, (_, i) => (
        <EsqueletoFila key={i} />
      ))}
    </Contenedor>
  )
}

// Gráfica: área con barras de distinta altura para sugerir la forma
const ALTURAS = [40, 62, 48, 80, 58, 90, 70]
export function EsqueletoGrafica({ alto = 160, className, etiqueta }) {
  return (
    <Contenedor etiqueta={etiqueta} className={junta('tarjeta', className)}>
      <div aria-hidden="true" className="flex items-end gap-2" style={{ height: alto }}>
        {ALTURAS.map((h, i) => (
          <Bloque key={i} className="flex-1" style={{ height: `${h}%`, borderRadius: '8px 8px 4px 4px' }} />
        ))}
      </div>
    </Contenedor>
  )
}

// Pantalla completa: encabezado + tarjeta protagonista + lista. `variante` ajusta la mezcla.
export function EsqueletoPantalla({ variante = 'lista', etiqueta = 'Cargando', className }) {
  return (
    <div className={junta('flex-1 overflow-y-auto pb-6 screen-enter', className)} role="status" aria-busy="true" aria-label={etiqueta}>
      <div aria-hidden="true" className="px-6 pantalla-top pb-3 flex items-center gap-3">
        <Bloque className="w-8 h-8 rounded-full!" />
        <Bloque className="h-5 w-40" />
      </div>
      <div aria-hidden="true" className="px-6 space-y-4">
        {variante !== 'texto' && <Bloque className="w-full" style={{ height: 150, borderRadius: '18px 30px 18px 18px' }} />}
        {variante === 'grafica' && <Bloque className="w-full" style={{ height: 160, borderRadius: 18 }} />}
        {variante === 'texto' ? (
          <div className="space-y-2">
            {[100, 92, 96, 70].map((w, i) => (
              <Bloque key={i} className="h-3.5" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : (
          <div className="tarjeta-lista">
            {Array.from({ length: 4 }, (_, i) => (
              <EsqueletoFila key={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
