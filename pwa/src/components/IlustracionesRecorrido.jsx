import { motion, useReducedMotion } from 'framer-motion'

// Ilustraciones del recorrido: SVG sencillos con los colores de la marca (se adaptan al modo oscuro
// porque usan las clases de color del tema). Son decorativas (`aria-hidden`): el texto del paso dice
// lo mismo, así que un lector de pantalla no se pierde nada. Las "mini-demos" mueven una barra o un
// monto al aparecer y se quedan quietas con «reducir movimiento».

function Marco({ children }) {
  return (
    <svg viewBox="0 0 320 180" className="w-full h-auto" aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="318" height="178" rx="18" className="fill-paper stroke-line" strokeWidth="2" />
      {children}
    </svg>
  )
}

const Texto = ({ x, y, t, tam = 10, peso = 400, ancla = 'start', clase = 'fill-ink' }) => (
  <text x={x} y={y} fontSize={tam} fontWeight={peso} textAnchor={ancla} className={clase}>{t}</text>
)

const Ficha = ({ x, y, ancho, alto = 18, t, tono = 'suave' }) => (
  <g>
    <rect x={x} y={y} width={ancho} height={alto} rx={alto / 2} className={tono === 'fuerte' ? 'fill-accent' : 'fill-accent-soft'} />
    <text x={x + ancho / 2} y={y + alto / 2 + 3.5} fontSize="9" fontWeight="700" textAnchor="middle" className={tono === 'fuerte' ? 'fill-paper-raised' : 'fill-accent'}>{t}</text>
  </g>
)

// Barra que se llena al aparecer (mini-demo)
function Barra({ x, y, ancho, pct, clase = 'fill-accent', alto = 10 }) {
  const reducir = useReducedMotion()
  return (
    <g>
      <rect x={x} y={y} width={ancho} height={alto} rx={alto / 2} className="fill-line" />
      <motion.rect
        x={x} y={y} height={alto} rx={alto / 2} className={clase}
        initial={{ width: reducir ? ancho * pct : 0 }}
        animate={{ width: ancho * pct }}
        transition={reducir ? { duration: 0 } : { duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
      />
    </g>
  )
}

function Inicio() {
  return (
    <Marco>
      <rect x="20" y="18" width="280" height="86" rx="16" className="fill-accent" />
      <Texto x={36} y={42} t="Saldo actual" tam={10} clase="fill-paper-raised" />
      <Texto x={36} y={74} t="$1.250.000" tam={26} peso={800} clase="fill-paper-raised" />
      <Texto x={36} y={94} t="En pesos · actualizado hoy" tam={9} clase="fill-paper-raised" />
      <rect x="20" y="118" width="136" height="48" rx="12" className="fill-accent-soft stroke-accent" strokeWidth="2" />
      <Texto x={32} y={137} t="Disponible hoy" tam={9} clase="fill-ink-soft" />
      <Texto x={32} y={157} t="$950.000" tam={16} peso={800} clase="fill-accent" />
      <rect x="164" y="118" width="136" height="48" rx="12" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Texto x={176} y={137} t="Debes en tarjetas" tam={9} clase="fill-ink-soft" />
      <Texto x={176} y={157} t="−$300.000" tam={16} peso={800} clase="fill-danger" />
    </Marco>
  )
}

function Cuentas() {
  return (
    <Marco>
      <rect x="14" y="16" width="144" height="148" rx="14" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Ficha x={24} y={26} ancho={92} t="DÉBITO / AHORROS" />
      <Texto x={24} y={64} t="Nu · Ahorros" tam={11} peso={700} />
      <Texto x={24} y={90} t="$500.000" tam={20} peso={800} clase="fill-accent" />
      <Texto x={24} y={112} t="Es plata que ya tienes." tam={8.5} clase="fill-ink-soft" />
      <Texto x={24} y={125} t="Pagar baja tu saldo." tam={8.5} clase="fill-ink-soft" />
      <rect x="164" y="16" width="144" height="148" rx="14" className="fill-paper-raised stroke-accent" strokeWidth="2" />
      <Ficha x={174} y={26} ancho={112} t="TARJETA DE CRÉDITO" tono="fuerte" />
      <Texto x={174} y={64} t="Nu · Tarjeta" tam={11} peso={700} />
      <Texto x={174} y={86} t="Debes −$300.000" tam={13} peso={800} clase="fill-danger" />
      <Barra x={174} y={96} ancho={124} pct={0.15} clase="fill-danger" alto={8} />
      <Texto x={174} y={119} t="Cupo $2.000.000" tam={9} clase="fill-ink-soft" />
      <Texto x={174} y={132} t="Te quedan $1.700.000" tam={9} clase="fill-ink-soft" />
      <Texto x={174} y={152} t="Corte día 15 · Pago día 30" tam={9} peso={700} clase="fill-ink" />
    </Marco>
  )
}

function Traer() {
  const fichas = [
    { x: 14, y: 14, t: 'Correo', s: 'Sin escribir nada', c: 'M18 38 h26 v-12 l-13 8 l-13 -8 z' },
    { x: 166, y: 14, t: 'Extracto PDF', s: 'Lo más exacto', c: '' },
    { x: 14, y: 98, t: 'Excel', s: 'Historial viejo', c: '' },
    { x: 166, y: 98, t: 'Atajo Apple Pay', s: 'Solo iPhone · al instante', c: '' },
  ]
  return (
    <Marco>
      {fichas.map((f, i) => (
        <g key={f.t}>
          <rect x={f.x} y={f.y} width="140" height="68" rx="14" className={i === 0 ? 'fill-accent-soft stroke-accent' : 'fill-paper-raised stroke-line'} strokeWidth="1.5" />
          <circle cx={f.x + 24} cy={f.y + 24} r="13" className={i === 0 ? 'fill-accent' : 'fill-accent-soft'} />
          <Texto x={f.x + 24} y={f.y + 29} t={['@', 'PDF', 'xls', 'iOS'][i]} tam={9} peso={800} ancla="middle" clase={i === 0 ? 'fill-paper-raised' : 'fill-accent'} />
          <Texto x={f.x + 46} y={f.y + 28} t={f.t} tam={11} peso={700} />
          <Texto x={f.x + 12} y={f.y + 54} t={f.s} tam={9} clase="fill-ink-soft" />
        </g>
      ))}
    </Marco>
  )
}

function Movimientos() {
  return (
    <Marco>
      <rect x="14" y="14" width="292" height="46" rx="12" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Texto x={26} y={34} t="Éxito · hoy" tam={10} peso={700} />
      <Texto x={294} y={34} t="−$45.000" tam={11} peso={800} ancla="end" />
      <Ficha x={26} y={40} ancho={58} t="Comida" tono="fuerte" />
      <Ficha x={90} y={40} ancho={74} t="Transporte" />
      <Ficha x={170} y={40} ancho={42} t="Casa" />
      <rect x="14" y="70" width="292" height="46" rx="12" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Texto x={26} y={90} t="Netflix · ayer" tam={10} peso={700} />
      <Texto x={294} y={90} t="−$33.000" tam={11} peso={800} ancla="end" />
      <Ficha x={26} y={96} ancho={70} t="Ocio" tono="fuerte" />
      <Texto x={110} y={109} t="← desliza para categorizar" tam={8.5} clase="fill-ink-soft" />
      <rect x="14" y="126" width="292" height="42" rx="12" className="fill-accent-soft stroke-accent" strokeWidth="1.5" strokeDasharray="5 3" />
      <Texto x={26} y={144} t="Nequi → Bancolombia" tam={10} peso={700} />
      <Texto x={294} y={144} t="$100.000" tam={11} peso={800} ancla="end" clase="fill-accent" />
      <Texto x={26} y={160} t="Traslado entre mis cuentas: no es gasto" tam={8.5} clase="fill-ink-soft" />
    </Marco>
  )
}

function Presupuesto() {
  const filas = [
    { t: 'Comida', pct: 0.7, v: '$420.000 de $600.000', c: 'fill-accent' },
    { t: 'Transporte', pct: 0.4, v: '$80.000 de $200.000', c: 'fill-accent' },
    { t: 'Ocio', pct: 0.95, v: '$190.000 de $200.000', c: 'fill-danger' },
  ]
  return (
    <Marco>
      {filas.map((f, i) => (
        <g key={f.t}>
          <Texto x={22} y={36 + i * 50} t={f.t} tam={11} peso={700} />
          <Texto x={298} y={36 + i * 50} t={f.v} tam={9} ancla="end" clase="fill-ink-soft" />
          <Barra x={22} y={44 + i * 50} ancho={276} pct={f.pct} clase={f.c} alto={12} />
        </g>
      ))}
      <Texto x={22} y={172} t="Ocio casi llega al límite: te avisamos antes." tam={8.5} clase="fill-ink-soft" />
    </Marco>
  )
}

function Metas() {
  return (
    <Marco>
      <rect x="14" y="14" width="292" height="78" rx="14" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Texto x={26} y={36} t="Meta: viaje a San Andrés" tam={11} peso={700} />
      <Texto x={294} y={36} t="40%" tam={11} peso={800} ancla="end" clase="fill-accent" />
      <Barra x={26} y={46} ancho={268} pct={0.4} alto={12} />
      <Texto x={26} y={78} t="$1.200.000 de $3.000.000 · faltan 6 meses" tam={9} clase="fill-ink-soft" />
      <rect x="14" y="102" width="292" height="66" rx="14" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Texto x={26} y={124} t="Deuda: tarjeta Nu" tam={11} peso={700} />
      <Texto x={294} y={124} t="−$300.000" tam={11} peso={800} ancla="end" clase="fill-danger" />
      <Texto x={26} y={144} t="Paga primero la que cobra más intereses" tam={9} clase="fill-ink-soft" />
      <Texto x={26} y={158} t="y ahorra en intereses." tam={9} clase="fill-ink-soft" />
    </Marco>
  )
}

function Informes() {
  const r = 38
  const c = 2 * Math.PI * r
  const trozos = [
    { p: 0.45, cl: 'stroke-accent' },
    { p: 0.3, cl: 'stroke-accent-2' },
    { p: 0.25, cl: 'stroke-line' },
  ]
  let acumulado = 0
  return (
    <Marco>
      <g transform="translate(90 92) rotate(-90)">
        {trozos.map((t) => {
          const el = (
            <circle key={t.cl} r={r} fill="none" strokeWidth="22" className={t.cl}
              strokeDasharray={`${t.p * c} ${c}`} strokeDashoffset={-acumulado * c} />
          )
          acumulado += t.p
          return el
        })}
      </g>
      <Texto x={90} y={96} t="Mayo" tam={11} peso={800} ancla="middle" />
      {[
        ['Comida', '45%', 'fill-accent'],
        ['Transporte', '30%', 'fill-accent-2'],
        ['Otros', '25%', 'fill-line'],
      ].map(([t, p, cl], i) => (
        <g key={t}>
          <circle cx="170" cy={64 + i * 28} r="6" className={cl} />
          <Texto x={184} y={68 + i * 28} t={t} tam={11} peso={600} />
          <Texto x={298} y={68 + i * 28} t={p} tam={11} peso={800} ancla="end" />
        </g>
      ))}
    </Marco>
  )
}

function Asistente() {
  return (
    <Marco>
      <rect x="70" y="16" width="238" height="40" rx="14" className="fill-accent" />
      <Texto x={84} y={40} t="¿Cuánto gasté en domicilios?" tam={10.5} peso={600} clase="fill-paper-raised" />
      <rect x="12" y="68" width="250" height="62" rx="14" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Texto x={26} y={90} t="Este mes gastaste $186.000" tam={10.5} peso={700} />
      <Texto x={26} y={106} t="en domicilios, un 12% más que" tam={10} clase="fill-ink-soft" />
      <Texto x={26} y={120} t="el mes pasado." tam={10} clase="fill-ink-soft" />
      <rect x="12" y="142" width="296" height="28" rx="14" className="fill-paper-raised stroke-line" strokeWidth="1.5" />
      <Texto x={26} y={160} t="Escribe tu pregunta…" tam={10} clase="fill-ink-soft" />
    </Marco>
  )
}

function Privacidad() {
  return (
    <Marco>
      <path d="M62 26 L100 38 V80 C100 104 84 120 62 130 C40 120 24 104 24 80 V38 Z" className="fill-accent-soft stroke-accent" strokeWidth="2.5" />
      <path d="M44 78 l13 13 l23 -26" fill="none" className="stroke-accent" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <Texto x={120} y={42} t="Lo que sí leemos" tam={10} peso={800} clase="fill-accent" />
      <Texto x={120} y={58} t="✓ Avisos de bancos y billeteras" tam={10} />
      <Texto x={120} y={72} t="✓ Extractos que tú subes" tam={10} />
      <Texto x={120} y={100} t="Lo que nunca hacemos" tam={10} peso={800} clase="fill-danger" />
      <Texto x={120} y={116} t="✗ Leer tus correos personales" tam={10} />
      <Texto x={120} y={130} t="✗ Enviar o borrar correos" tam={10} />
      <Texto x={24} y={162} t="Quitas el permiso y borras tus datos cuando quieras." tam={9} clase="fill-ink-soft" />
    </Marco>
  )
}

const POR_ID = { inicio: Inicio, cuentas: Cuentas, traer: Traer, movimientos: Movimientos, presupuesto: Presupuesto, metas: Metas, informes: Informes, asistente: Asistente, privacidad: Privacidad }

export default function IlustracionRecorrido({ id }) {
  const Pieza = POR_ID[id]
  return Pieza ? <Pieza /> : null
}
