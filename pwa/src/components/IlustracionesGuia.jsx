// Dibujos (SVG, livianos y con los colores de la marca) para las guías de instalación y de registro automático.
// Cada escena es un celular con la pantalla EXACTA que verá la persona y un círculo que pulsa donde debe tocar.
// Son decorativos pero llevan descripción para lectores de pantalla. Sin imágenes externas: cargan al instante.

function Marco({ children, titulo }) {
  return (
    <svg viewBox="0 0 150 270" className="w-full h-auto" role="img" aria-label={titulo}>
      <rect x="3" y="3" width="144" height="264" rx="22" className="fill-paper stroke-ink" strokeWidth="3" />
      <rect x="55" y="8" width="40" height="6" rx="3" className="fill-ink" opacity="0.85" />
      <clipPath id="pantalla-guia">
        <rect x="8" y="20" width="134" height="242" rx="14" />
      </clipPath>
      <g clipPath="url(#pantalla-guia)">{children}</g>
    </svg>
  )
}

// Círculo que pulsa: «toca aquí».
function Toque({ x, y, r = 13 }) {
  return (
    <g>
      <circle cx={x} cy={y} r={r} className="guia-pulso fill-accent" opacity="0.35" />
      <circle cx={x} cy={y} r={r * 0.55} className="fill-accent" opacity="0.9" />
      <circle cx={x} cy={y} r={r * 0.2} className="fill-paper-raised" />
    </g>
  )
}

function Etiqueta({ x, y, w = 110, children }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height="22" rx="11" className="fill-ink" />
      <text x={x + w / 2} y={y + 14.5} fontSize="9.5" fontWeight="700" textAnchor="middle" className="fill-paper">
        {children}
      </text>
    </g>
  )
}

function Fila({ y, texto, resaltada = false, x = 16, w = 118 }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height="26" rx="8" className={resaltada ? 'fill-accent-soft stroke-accent' : 'fill-paper-raised stroke-line'} strokeWidth={resaltada ? 2 : 1.2} />
      <text x={x + 9} y={y + 17} fontSize="8.5" fontWeight={resaltada ? 800 : 500} className="fill-ink">{texto}</text>
    </g>
  )
}

function IconoCuadraMe({ x, y, s = 30 }) {
  return (
    <g>
      <rect x={x} y={y} width={s} height={s} rx={s * 0.24} className="fill-accent" />
      <rect x={x + s * 0.55} y={y + s * 0.12} width={s * 0.3} height={s * 0.3} rx={s * 0.07} className="fill-paper-raised" opacity="0.9" />
    </g>
  )
}

const BarraEstado = () => (
  <g>
    <rect x="8" y="20" width="134" height="16" className="fill-paper" />
    <text x="18" y="31" fontSize="7" fontWeight="700" className="fill-ink">9:41</text>
    <rect x="116" y="25" width="16" height="7" rx="2" className="fill-ink" opacity="0.7" />
  </g>
)

/* ─────────────── iPhone: poner la app en la pantalla de inicio ─────────────── */

export function IosSafari() {
  return (
    <Marco titulo="Dibujo: Safari con CuadraMe abierto; abajo, el botón Compartir (un cuadro con una flecha hacia arriba) resaltado">
      <BarraEstado />
      <rect x="14" y="40" width="122" height="16" rx="8" className="fill-paper-raised stroke-line" strokeWidth="1.2" />
      <text x="75" y="51" fontSize="7" textAnchor="middle" className="fill-ink-soft">cuadrame.dapx.shop</text>
      <IconoCuadraMe x={60} y={90} s={30} />
      <text x="75" y="140" fontSize="10" fontWeight="800" textAnchor="middle" className="fill-ink">CuadraMe</text>
      <rect x="30" y="152" width="90" height="8" rx="4" className="fill-line" />
      <rect x="40" y="166" width="70" height="8" rx="4" className="fill-line" />
      <rect x="8" y="222" width="134" height="40" className="fill-paper-raised" />
      <rect x="8" y="222" width="134" height="1" className="fill-line" />
      {[22, 52, 112, 130].map((cx) => <rect key={cx} x={cx - 5} y="236" width="10" height="10" rx="3" className="fill-line" />)}
      {/* botón Compartir */}
      <rect x="70" y="236" width="10" height="11" rx="2" className="fill-none stroke-accent" strokeWidth="1.6" />
      <path d="M75 232 V242 M71.5 235.5 L75 232 L78.5 235.5" className="stroke-accent fill-none" strokeWidth="1.6" strokeLinecap="round" />
      <Toque x={75} y={241} />
      <Etiqueta x={20} y={190} w={110}>Toca Compartir</Etiqueta>
    </Marco>
  )
}

export function IosCompartir() {
  return (
    <Marco titulo="Dibujo: el menú Compartir de iPhone; la opción «Añadir a pantalla de inicio» está resaltada">
      <BarraEstado />
      <rect x="8" y="36" width="134" height="226" className="fill-ink" opacity="0.28" />
      <rect x="8" y="78" width="134" height="184" rx="16" className="fill-paper" />
      <rect x="55" y="84" width="40" height="4" rx="2" className="fill-line" />
      <text x="16" y="102" fontSize="9" fontWeight="800" className="fill-ink">CuadraMe</text>
      <Fila y={110} texto="Copiar" />
      <Fila y={140} texto="Añadir a marcadores" />
      <Fila y={170} texto="Añadir a pantalla de inicio" resaltada />
      <Fila y={200} texto="Buscar en la página" />
      <Toque x={122} y={183} r={11} />
      <Etiqueta x={16} y={46} w={118}>Desliza si no la ves</Etiqueta>
    </Marco>
  )
}

export function IosAnadir() {
  return (
    <Marco titulo="Dibujo: la ventana «Añadir a pantalla de inicio» con el ícono de CuadraMe y el botón Añadir resaltado arriba a la derecha">
      <BarraEstado />
      <rect x="8" y="36" width="134" height="226" className="fill-paper-raised" />
      <text x="16" y="56" fontSize="8" className="fill-ink-soft">Cancelar</text>
      <rect x="96" y="44" width="38" height="18" rx="9" className="fill-accent" />
      <text x="115" y="56" fontSize="8" fontWeight="800" textAnchor="middle" className="fill-paper-raised">Añadir</text>
      <Toque x={115} y={53} r={12} />
      <rect x="16" y="76" width="118" height="54" rx="12" className="fill-paper stroke-line" strokeWidth="1.2" />
      <IconoCuadraMe x={24} y={87} s={32} />
      <text x="64" y="100" fontSize="9" fontWeight="800" className="fill-ink">CuadraMe</text>
      <text x="64" y="114" fontSize="6.5" className="fill-ink-soft">cuadrame.dapx.shop</text>
      <Etiqueta x={20} y={150} w={110}>Toca «Añadir»</Etiqueta>
    </Marco>
  )
}

/* ─────────────── Android: instalar desde Chrome ─────────────── */

export function AndroidChrome() {
  return (
    <Marco titulo="Dibujo: Chrome con CuadraMe abierto; arriba a la derecha, los tres puntos del menú resaltados">
      <BarraEstado />
      <rect x="12" y="40" width="100" height="16" rx="8" className="fill-paper-raised stroke-line" strokeWidth="1.2" />
      <text x="62" y="51" fontSize="7" textAnchor="middle" className="fill-ink-soft">cuadrame.dapx.shop</text>
      {[44, 50, 56].map((cy) => <circle key={cy} cx="130" cy={cy - 2} r="1.9" className="fill-ink" />)}
      <Toque x={130} y={48} r={12} />
      <IconoCuadraMe x={60} y={100} s={30} />
      <text x="75" y="150" fontSize="10" fontWeight="800" textAnchor="middle" className="fill-ink">CuadraMe</text>
      <rect x="30" y="162" width="90" height="8" rx="4" className="fill-line" />
      <Etiqueta x={20} y={196} w={110}>Toca los 3 puntos</Etiqueta>
    </Marco>
  )
}

export function AndroidMenu() {
  return (
    <Marco titulo="Dibujo: el menú de Chrome; la opción «Instalar app» (o «Añadir a la pantalla de inicio») está resaltada">
      <BarraEstado />
      <rect x="40" y="44" width="98" height="140" rx="10" className="fill-paper-raised stroke-line" strokeWidth="1.4" />
      <Fila x={46} w={86} y={50} texto="Nueva pestaña" />
      <Fila x={46} w={86} y={80} texto="Historial" />
      <Fila x={46} w={86} y={110} texto="Instalar app" resaltada />
      <Fila x={46} w={86} y={140} texto="Compartir…" />
      <Toque x={120} y={123} r={11} />
      <Etiqueta x={20} y={204} w={110}>A veces dice «Añadir…»</Etiqueta>
    </Marco>
  )
}

export function AndroidConfirmar() {
  return (
    <Marco titulo="Dibujo: ventana «Instalar app» de Chrome con el botón Instalar resaltado">
      <BarraEstado />
      <rect x="8" y="36" width="134" height="226" className="fill-ink" opacity="0.28" />
      <rect x="14" y="96" width="122" height="96" rx="16" className="fill-paper stroke-line" strokeWidth="1.2" />
      <text x="24" y="116" fontSize="9" fontWeight="800" className="fill-ink">¿Instalar app?</text>
      <IconoCuadraMe x={24} y={124} s={26} />
      <text x="58" y="141" fontSize="9" fontWeight="700" className="fill-ink">CuadraMe</text>
      <text x="76" y="180" fontSize="8" className="fill-ink-soft">Cancelar</text>
      <rect x="96" y="166" width="34" height="18" rx="9" className="fill-accent" />
      <text x="113" y="178" fontSize="8" fontWeight="800" textAnchor="middle" className="fill-paper-raised">Instalar</text>
      <Toque x={113} y={175} r={12} />
      <Etiqueta x={20} y={210} w={110}>Toca «Instalar»</Etiqueta>
    </Marco>
  )
}

/* ─────────────── Los dos: el ícono ya está en el inicio ─────────────── */

export function PantallaInicioConIcono() {
  const hueco = []
  for (let f = 0; f < 4; f++) for (let c = 0; c < 4; c++) hueco.push([20 + c * 30, 52 + f * 44])
  return (
    <Marco titulo="Dibujo: la pantalla de inicio del celular con el ícono de CuadraMe junto a las demás apps">
      <rect x="8" y="20" width="134" height="242" className="fill-accent-soft" />
      <BarraEstado />
      {hueco.map(([x, y], i) =>
        i === 5 ? <IconoCuadraMe key={i} x={x} y={y} s={24} /> : <rect key={i} x={x} y={y} width="24" height="24" rx="7" className="fill-line" />,
      )}
      <circle cx="95" cy="62" r="8" className="fill-cuadra" />
      <path d="M91 62 L94 65 L99 59" className="stroke-paper-raised fill-none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <Etiqueta x={20} y={236} w={110}>¡Listo! Ábrela de aquí</Etiqueta>
    </Marco>
  )
}

/* ─────────────── Android: app «CuadraMe Captura» (lee los avisos de pago) ─────────────── */

export function AndroidDescarga() {
  return (
    <Marco titulo="Dibujo: el navegador descargando el archivo cuadrame-captura.apk; se toca Abrir">
      <BarraEstado />
      <rect x="14" y="60" width="122" height="62" rx="12" className="fill-paper-raised stroke-line" strokeWidth="1.2" />
      <text x="24" y="80" fontSize="8" fontWeight="800" className="fill-ink">Descarga completa</text>
      <text x="24" y="94" fontSize="7" className="fill-ink-soft">cuadrame-captura.apk</text>
      <rect x="88" y="100" width="40" height="16" rx="8" className="fill-accent" />
      <text x="108" y="111" fontSize="7.5" fontWeight="800" textAnchor="middle" className="fill-paper-raised">Abrir</text>
      <Toque x={126} y={114} r={9} />
      <Etiqueta x={20} y={150} w={110}>Toca «Abrir»</Etiqueta>
    </Marco>
  )
}

export function AndroidPermitirInstalar() {
  return (
    <Marco titulo="Dibujo: Android pregunta si permitir instalar apps desde esta fuente; se activa el interruptor">
      <BarraEstado />
      <rect x="14" y="64" width="122" height="92" rx="14" className="fill-paper-raised stroke-line" strokeWidth="1.2" />
      <text x="22" y="82" fontSize="8" fontWeight="800" className="fill-ink">Por tu seguridad</text>
      <text x="22" y="96" fontSize="6.5" className="fill-ink-soft">Permitir instalar apps desde</text>
      <text x="22" y="106" fontSize="6.5" className="fill-ink-soft">este navegador</text>
      <rect x="92" y="120" width="32" height="16" rx="8" className="fill-accent" />
      <circle cx="116" cy="128" r="6" className="fill-paper-raised" />
      <Toque x={108} y={128} r={11} />
      <Etiqueta x={13} y={176} w={124}>Actívalo y vuelve atrás</Etiqueta>
    </Marco>
  )
}

export function AndroidAccesoNotificaciones() {
  return (
    <Marco titulo="Dibujo: ajustes de Android, lista «Acceso a notificaciones»; se activa CuadraMe Captura">
      <BarraEstado />
      <text x="16" y="56" fontSize="9" fontWeight="800" className="fill-ink">Acceso a notificaciones</text>
      <Fila y={68} texto="Otra app" />
      <Fila y={100} texto="CuadraMe Captura" resaltada />
      <rect x="108" y="106" width="24" height="14" rx="7" className="fill-accent" />
      <circle cx="125" cy="113" r="5" className="fill-paper-raised" />
      <Toque x={124} y={124} r={8} />
      <Fila y={132} texto="Otra app" />
      <Etiqueta x={20} y={176} w={110}>Actívala y acepta</Etiqueta>
    </Marco>
  )
}

/* ─────────────── Cómo funciona, en 4 pasos (para explicar el registro automático) ─────────────── */

export function FlujoAutomatico() {
  const nodos = [
    { x: 42, t: 'Pagas', s: 'con tu celular' },
    { x: 126, t: 'Tu celular', s: 'avisa a CuadraMe' },
    { x: 210, t: 'Se anota', s: 'solo' },
    { x: 294, t: 'Tú', s: 'confirmas' },
  ]
  return (
    <svg viewBox="0 0 336 120" className="w-full h-auto" role="img" aria-label="Cómo funciona: pagas con tu celular, el celular avisa a CuadraMe, el movimiento se anota solo y tú lo confirmas con un toque">
      {[0, 1, 2].map((i) => (
        <path key={i} d={`M${nodos[i].x + 26} 42 H${nodos[i + 1].x - 26}`} className="stroke-accent" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="2 6" />
      ))}
      {/* 1. tarjeta */}
      <rect x="22" y="28" width="40" height="28" rx="6" className="fill-ink" />
      <rect x="22" y="35" width="40" height="6" className="fill-accent" />
      <rect x="28" y="46" width="14" height="4" rx="2" className="fill-paper" opacity="0.8" />
      {/* 2. celular con campana */}
      <rect x="114" y="22" width="24" height="40" rx="6" className="fill-paper-raised stroke-ink" strokeWidth="2" />
      <circle cx="126" cy="38" r="6" className="fill-accent" />
      <rect x="123" y="52" width="6" height="3" rx="1.5" className="fill-line" />
      {/* 3. ícono CuadraMe */}
      <rect x="194" y="26" width="32" height="32" rx="8" className="fill-accent" />
      <rect x="211" y="30" width="10" height="10" rx="2.5" className="fill-paper-raised" opacity="0.9" />
      {/* 4. check */}
      <circle cx="294" cy="42" r="18" className="fill-cuadra" />
      <path d="M285 42 L291 48 L303 35" className="stroke-paper-raised fill-none" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      {nodos.map((n) => (
        <g key={n.t}>
          <text x={n.x} y="84" fontSize="11" fontWeight="800" textAnchor="middle" className="fill-ink">{n.t}</text>
          <text x={n.x} y="98" fontSize="9" textAnchor="middle" className="fill-ink-soft">{n.s}</text>
        </g>
      ))}
    </svg>
  )
}

/* Android: dentro de la app «CuadraMe Captura» */

export function AndroidPegarClave() {
  return (
    <Marco titulo="Dibujo: la app CuadraMe Captura con el campo «Clave de CuadraMe» lleno y el botón Guardar clave">
      <BarraEstado />
      <text x="16" y="56" fontSize="10" fontWeight="800" className="fill-ink">CuadraMe Captura</text>
      <text x="16" y="78" fontSize="8" fontWeight="700" className="fill-ink">1. Tu clave de conexión</text>
      <rect x="16" y="86" width="118" height="22" rx="7" className="fill-paper-raised stroke-accent" strokeWidth="1.6" />
      <text x="24" y="100" fontSize="9" className="fill-ink">••••••••••••</text>
      <rect x="16" y="118" width="118" height="24" rx="12" className="fill-accent" />
      <text x="75" y="133" fontSize="8.5" fontWeight="800" textAnchor="middle" className="fill-paper-raised">Guardar clave</text>
      <Toque x={124} y={142} r={8} />
      <Etiqueta x={13} y={170} w={124}>Pégala y guarda</Etiqueta>
    </Marco>
  )
}

export function AndroidProbar() {
  return (
    <Marco titulo="Dibujo: la app CuadraMe Captura; al tocar Probar conexión dice Conectado y cuántas cuentas ve">
      <BarraEstado />
      <text x="16" y="56" fontSize="10" fontWeight="800" className="fill-ink">CuadraMe Captura</text>
      <rect x="16" y="68" width="118" height="24" rx="12" className="fill-accent" />
      <text x="75" y="83" fontSize="8.5" fontWeight="800" textAnchor="middle" className="fill-paper-raised">Probar conexión</text>
      <rect x="16" y="100" width="118" height="24" rx="12" className="fill-paper-raised stroke-accent" strokeWidth="1.4" />
      <text x="75" y="115" fontSize="8" fontWeight="700" textAnchor="middle" className="fill-accent">Enviar un pago de prueba</text>
      <text x="16" y="146" fontSize="8" fontWeight="800" className="fill-cuadra">Conectado ✓</text>
      <text x="16" y="158" fontSize="6.8" className="fill-ink-soft">CuadraMe ve 3 cuentas tuyas.</text>
      <Toque x={124} y={92} r={8} />
      <Etiqueta x={13} y={190} w={124}>Debe decir Conectado</Etiqueta>
    </Marco>
  )
}
