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


export function CapturaNotificacion() {
  return (
    <Pantalla titulo="Dibujo: nueva automatización en Atajos con el disparador Cuando recibo una notificación, la app de tu banco y Ejecutar atajo CuadraMe Notificaciones">
      <text x="14" y="18" fontSize="10" fontWeight="700" className="fill-ink">Nueva automatización</text>
      <Fila y={26} n="1" resaltada etiqueta="Cuando recibo una notificación" />
      <Fila y={54} n="2" etiqueta="App: la de tu banco (Nequi…)" />
      <Fila y={82} n="3" etiqueta="Ejecutar atajo: CuadraMe Notif…" />
      <Fila y={108} n="4" etiqueta="Ejecutar inmediatamente" ancho={40} />
    </Pantalla>
  )
}

export function CapturaGesto() {
  return (
    <Pantalla titulo="Dibujo: en Ajustes, Accesibilidad, Tocar, Tocar atrás, el Doble toque ejecuta el atajo CuadraMe Registrar">
      <text x="14" y="18" fontSize="10" fontWeight="700" className="fill-ink">Ajustes › Accesibilidad › Tocar atrás</text>
      <Fila y={30} n="1" etiqueta="Doble toque" />
      <Fila y={58} n="2" resaltada etiqueta="Atajos › CuadraMe Registrar" />
      <Fila y={90} etiqueta="Triple toque: sin usar" ancho={20} />
    </Pantalla>
  )
}

// ---- Pantallas de iPhone (vertical) para el paso «Instalar»: dibujos propios, no capturas reales ----

function Iphone({ children, titulo }) {
  return (
    <svg viewBox="0 0 150 290" className="w-full h-auto" role="img" aria-label={titulo}>
      <rect x="2" y="2" width="146" height="286" rx="24" className="fill-paper stroke-ink-soft" strokeWidth="3" />
      <rect x="9" y="9" width="132" height="272" rx="18" className="fill-paper-raised" />
      <rect x="55" y="14" width="40" height="11" rx="5.5" className="fill-ink" />
      <text x="22" y="23" fontSize="7" fontWeight="700" className="fill-ink">9:41</text>
      <rect x="116" y="17" width="14" height="6" rx="2" className="fill-ink" />
      {children}
    </svg>
  )
}

// Marca lo que hay que tocar.
function Toque({ x, y }) {
  return (
    <g>
      <circle cx={x} cy={y} r="13" className="fill-accent" opacity="0.22" />
      <circle cx={x} cy={y} r="5" className="fill-accent" opacity="0.7" />
    </g>
  )
}

export function CapturaDescargaSafari() {
  return (
    <Iphone titulo="Dibujo: Safari pregunta si quieres descargar CuadraMe Registrar.shortcut, con los botones Cancelar y Descargar">
      <rect x="16" y="34" width="118" height="16" rx="8" className="fill-paper stroke-line" strokeWidth="1" />
      <text x="75" y="45" fontSize="6.5" textAnchor="middle" className="fill-ink-soft">cuadrame.dapx.shop</text>
      <rect x="16" y="60" width="118" height="10" rx="3" className="fill-line" opacity="0.6" />
      <rect x="16" y="76" width="90" height="10" rx="3" className="fill-line" opacity="0.6" />
      <rect x="16" y="92" width="118" height="30" rx="8" className="fill-accent" />
      <text x="75" y="111" fontSize="8" fontWeight="700" textAnchor="middle" className="fill-paper-raised">Instalar</text>
      <rect x="9" y="9" width="132" height="272" rx="18" className="fill-ink" opacity="0.28" />
      <rect x="22" y="138" width="106" height="84" rx="14" className="fill-paper-raised stroke-line" strokeWidth="1" />
      <text x="75" y="156" fontSize="7" fontWeight="700" textAnchor="middle" className="fill-ink">¿Quieres descargar</text>
      <text x="75" y="166" fontSize="6.5" fontWeight="700" textAnchor="middle" className="fill-ink">«CuadraMe Registrar</text>
      <text x="75" y="175" fontSize="6.5" fontWeight="700" textAnchor="middle" className="fill-ink">.shortcut»?</text>
      <line x1="22" y1="190" x2="128" y2="190" className="stroke-line" strokeWidth="1" />
      <line x1="75" y1="190" x2="75" y2="222" className="stroke-line" strokeWidth="1" />
      <text x="48" y="209" fontSize="8" textAnchor="middle" className="fill-accent">Cancelar</text>
      <text x="102" y="209" fontSize="8" fontWeight="700" textAnchor="middle" className="fill-accent">Descargar</text>
      <Toque x={118} y={217} />
    </Iphone>
  )
}

export function CapturaAbrirDescarga() {
  return (
    <Iphone titulo="Dibujo: en Safari, el botón de descargas muestra el archivo CuadraMe Registrar.shortcut, que se toca para abrirlo">
      <rect x="16" y="34" width="118" height="16" rx="8" className="fill-paper stroke-line" strokeWidth="1" />
      <text x="70" y="45" fontSize="6.5" textAnchor="middle" className="fill-ink-soft">cuadrame.dapx.shop</text>
      <circle cx="124" cy="42" r="7" className="fill-accent" />
      <path d="M124 38 v6 m-3 -2.5 l3 3 l3 -3" className="stroke-paper-raised" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <Toque x={124} y={42} />
      <rect x="40" y="56" width="98" height="64" rx="12" className="fill-paper stroke-line" strokeWidth="1" />
      <text x="48" y="70" fontSize="7" fontWeight="700" className="fill-ink">Descargas</text>
      <rect x="46" y="78" width="86" height="30" rx="8" className="fill-accent-soft stroke-accent" strokeWidth="1.2" />
      <rect x="51" y="84" width="16" height="18" rx="4" className="fill-accent" />
      <text x="73" y="93" fontSize="6" fontWeight="700" className="fill-ink">CuadraMe Registrar</text>
      <text x="73" y="102" fontSize="5.5" className="fill-ink-soft">.shortcut · 26 KB</text>
      <Toque x={124} y={104} />
      <rect x="16" y="140" width="118" height="8" rx="3" className="fill-line" opacity="0.5" />
      <rect x="16" y="154" width="90" height="8" rx="3" className="fill-line" opacity="0.5" />
    </Iphone>
  )
}

export function CapturaAgregarAtajo() {
  return (
    <Iphone titulo="Dibujo: la app Atajos muestra CuadraMe Registrar, pide pegar tu clave y tiene el botón Agregar atajo">
      <text x="75" y="46" fontSize="7" fontWeight="700" textAnchor="middle" className="fill-ink">Agregar atajo</text>
      <rect x="55" y="56" width="40" height="40" rx="10" className="fill-accent" />
      <path d="M69 68 l10 8 l-10 8 z" className="fill-paper-raised" />
      <text x="75" y="112" fontSize="9" fontWeight="700" textAnchor="middle" className="fill-ink">CuadraMe Registrar</text>
      <text x="75" y="124" fontSize="6.5" textAnchor="middle" className="fill-ink-soft">Registra tus pagos solo</text>
      <text x="18" y="146" fontSize="6.5" className="fill-ink-soft">Pega tu clave de CuadraMe</text>
      <rect x="16" y="150" width="118" height="22" rx="7" className="fill-paper stroke-accent" strokeWidth="1.3" />
      <text x="23" y="164" fontSize="7.5" className="fill-ink">cdm_a1b2c3d4…</text>
      <rect x="16" y="212" width="118" height="26" rx="13" className="fill-accent" />
      <text x="75" y="229" fontSize="9" fontWeight="700" textAnchor="middle" className="fill-paper-raised">Agregar atajo</text>
      <Toque x={118} y={231} />
      <text x="75" y="256" fontSize="6.5" textAnchor="middle" className="fill-accent">Cancelar</text>
    </Iphone>
  )
}
