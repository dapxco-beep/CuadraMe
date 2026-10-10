// «Capturas» dibujadas con SVG (livianas, con los colores de la marca) para el asistente del
// registro automático. Decorativas pero con descripción para lectores de pantalla.

function Pantalla({ children, titulo }) {
  return (
    <svg viewBox="0 0 220 130" className="w-full h-auto" role="img" aria-label={titulo}>
      <rect x="1" y="1" width="218" height="128" rx="14" className="fill-paper stroke-line" strokeWidth="2" />
      {children}
    </svg>
  )
}

function Fila({ y, ancho = 110, resaltada = false, etiqueta, n }) {
  return (
    <g>
      <rect x="30" y={y} width="176" height="22" rx="8" className={resaltada ? 'fill-accent-soft stroke-accent' : 'fill-paper-raised stroke-line'} strokeWidth="1.5" />
      <text x="38" y={y + 15} fontSize="9" fontWeight={resaltada ? 700 : 500} className="fill-ink">{etiqueta}</text>
      <rect x="150" y={y + 8} width={Math.min(ancho, 50)} height="6" rx="3" className={resaltada ? 'fill-accent' : 'fill-line'} />
      {n && (
        <g>
          <circle cx="16" cy={y + 11} r="8" className="fill-accent" />
          <text x="16" y={y + 14.5} fontSize="9" fontWeight="700" textAnchor="middle" className="fill-paper-raised">{n}</text>
        </g>
      )}
    </g>
  )
}

export function CapturaClave() {
  return (
    <Pantalla titulo="Dibujo: el botón grande «Copiar mi clave» en CuadraMe">
      <text x="14" y="24" fontSize="10" fontWeight="700" className="fill-ink">Tu clave</text>
      <rect x="14" y="34" width="192" height="24" rx="8" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <text x="22" y="50" fontSize="9" className="fill-ink-soft">cdm_a1b2c3d4…</text>
      <rect x="14" y="68" width="192" height="30" rx="12" className="fill-accent" />
      <text x="110" y="87" fontSize="11" textAnchor="middle" fontWeight="700" className="fill-paper-raised">Copiar mi clave</text>
      <text x="14" y="116" fontSize="8" className="fill-ink-soft">Cópiala y pégala en el atajo.</text>
    </Pantalla>
  )
}

// Lo que verá la persona al instalar el atajo: iOS pregunta por la clave y ella la pega.
export function CapturaPegarClave() {
  return (
    <Pantalla titulo="Dibujo: al instalar el atajo, iOS pregunta «Pega tu clave de Cuádrame»; mantén presionado y elige Pegar">
      <text x="14" y="22" fontSize="10" fontWeight="700" className="fill-ink">CuadraMe Apple Pay</text>
      <text x="14" y="42" fontSize="8" className="fill-ink-soft">Pega tu clave de Cuádrame</text>
      <rect x="14" y="48" width="192" height="24" rx="8" className="fill-paper-raised stroke-accent" strokeWidth="1.5" />
      <text x="22" y="64" fontSize="9" className="fill-ink">cdm_a1b2c3…</text>
      <rect x="120" y="76" width="54" height="20" rx="8" className="fill-ink" />
      <text x="147" y="89" fontSize="8" fontWeight="700" textAnchor="middle" className="fill-paper">Pegar</text>
      <rect x="14" y="102" width="192" height="20" rx="8" className="fill-accent" />
      <text x="110" y="115" fontSize="9" fontWeight="700" textAnchor="middle" className="fill-paper-raised">Agregar atajo</text>
    </Pantalla>
  )
}

export function CapturaAutomatizacion() {
  return (
    <Pantalla titulo="Dibujo: nueva automatización en Atajos con el disparador Transacción, tus tarjetas y Ejecutar inmediatamente">
      <text x="14" y="18" fontSize="10" fontWeight="700" className="fill-ink">Nueva automatización</text>
      <Fila y={26} n="1" resaltada etiqueta="Transacción" />
      <Fila y={54} n="2" etiqueta="Tus tarjetas de Wallet" />
      <Fila y={82} n="3" etiqueta="Ejecutar atajo: CuadraMe" />
      <Fila y={108} n="4" etiqueta="Ejecutar inmediatamente" ancho={40} />
    </Pantalla>
  )
}

export function CapturaCierreApp() {
  return (
    <Pantalla titulo="Dibujo: automatización con el disparador App, marcando Se cierra">
      <text x="14" y="18" fontSize="10" fontWeight="700" className="fill-ink">Nueva automatización</text>
      <Fila y={30} n="1" resaltada etiqueta="App: la de tu banco" />
      <Fila y={62} n="2" etiqueta="Se cierra" />
      <Fila y={94} n="3" etiqueta="Ejecutar atajo: CuadraMe Cierre" />
    </Pantalla>
  )
}
