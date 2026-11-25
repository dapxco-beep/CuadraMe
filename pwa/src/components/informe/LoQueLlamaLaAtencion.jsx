import { AlertTriangle, PartyPopper, PieChart, Store, Wallet } from 'lucide-react'

// Frases cortas con lo más llamativo del periodo, calculadas aquí con las cifras que ya trae el informe (sin inventar nada):
// la categoría que más subió, la que más bajó, qué pesa demasiado, el comercio donde más gastas y cómo va el ahorro.
export function obtenerHallazgos(informe, fmt) {
  const out = []
  const cats = informe.categorias || []
  const sube = cats.filter((c) => c.variacion_pct != null && c.variacion_pct >= 20 && c.monto - c.anterior >= 30000)
    .sort((a, b) => b.monto - b.anterior - (a.monto - a.anterior))[0]
  if (sube) out.push({ id: 'sube', tono: 'alerta', Icono: AlertTriangle, titulo: `${sube.categoria} subió ${Math.round(sube.variacion_pct)} %`, texto: `Son ${fmt(sube.monto - sube.anterior)} más que en el periodo anterior.` })
  const baja = cats.filter((c) => c.variacion_pct != null && c.variacion_pct <= -20 && c.anterior - c.monto >= 30000)
    .sort((a, b) => b.anterior - b.monto - (a.anterior - a.monto))[0]
  if (baja) out.push({ id: 'baja', tono: 'bien', Icono: PartyPopper, titulo: `Bajaste ${baja.categoria}`, texto: `Gastaste ${fmt(baja.anterior - baja.monto)} menos que en el periodo anterior.` })
  const top = cats[0]
  if (top && top.pct >= 40) out.push({ id: 'peso', tono: 'info', Icono: PieChart, titulo: `${top.categoria} pesa mucho`, texto: `Se lleva el ${String(top.pct).replace('.', ',')} % de todo lo que gastas.` })
  const comercio = (informe.comercios || [])[0]
  if (comercio && comercio.num >= 2) out.push({ id: 'comercio', tono: 'info', Icono: Store, titulo: `${comercio.nombre} es donde más gastas`, texto: `${comercio.num} compras por ${fmt(comercio.monto)}.` })
  if (informe.ingresos > 0) {
    if (informe.ahorro < 0) out.push({ id: 'ahorro', tono: 'alerta', Icono: Wallet, titulo: 'Gastaste más de lo que entró', texto: `Te faltaron ${fmt(Math.abs(informe.ahorro))} frente a tus ingresos.` })
    else {
      const t = Math.round((informe.ahorro / informe.ingresos) * 100)
      out.push({ id: 'ahorro', tono: t >= 20 ? 'bien' : 'info', Icono: Wallet, titulo: `Ahorraste el ${t} % de lo que entró`, texto: t >= 20 ? 'Vas por encima de la meta de ahorro más común (20 %).' : 'La meta más común es llegar al 20 %.' })
    }
  }
  // Primero lo que requiere atención, luego las buenas noticias y al final lo informativo.
  const rango = { alerta: 0, bien: 1, info: 2 }
  return out.map((h, i) => ({ h, i })).sort((a, b) => rango[a.h.tono] - rango[b.h.tono] || a.i - b.i).map((x) => x.h).slice(0, 4)
}

const TONOS = {
  alerta: 'border-danger/30 bg-danger/5',
  bien: 'border-cuadra/30 bg-cuadra/5',
  info: 'border-line bg-paper-raised',
}

export default function LoQueLlamaLaAtencion({ informe, fmt, className = '' }) {
  const hallazgos = obtenerHallazgos(informe, fmt)
  if (!hallazgos.length) return null
  return (
    <section className={className} aria-label="Lo que llama la atención">
      <h2 className="text-[15px] font-semibold mb-2">Lo que llama la atención</h2>
      <ul className="flex gap-3 overflow-x-auto -mx-6 px-6 scroll-px-6 pb-1 snap-x">
        {hallazgos.map(({ id, tono, Icono, titulo, texto }) => (
          <li key={id} className={`snap-start shrink-0 w-[15rem] rounded-2xl border p-3 ${TONOS[tono]}`}>
            <Icono size={18} className={tono === 'alerta' ? 'text-danger' : tono === 'bien' ? 'text-cuadra' : 'text-ink-soft'} aria-hidden="true" />
            <p className="text-sm font-semibold mt-1.5 leading-snug">{titulo}</p>
            <p className="text-xs text-ink-soft mt-0.5 leading-snug">{texto}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
