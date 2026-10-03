import { marcaDeEntidad } from '../lib/entidadesFinancierasCO'
import { formatMoneda } from '../lib/format'

// Tarjeta con identidad de marca real (color + monograma) de la entidad que el
// usuario escribió al crear la cuenta — igual que abrir la billetera y reconocer
// cada tarjeta física por su color, sin tener que leer el nombre completo.
export default function TarjetaCuenta({ cuenta, style, className = '' }) {
  const marca = marcaDeEntidad(cuenta.nombre)

  return (
    <div
      className={`rounded-[20px] p-4 shadow-lg shadow-black/10 ${className}`}
      style={{ background: marca.bg, color: marca.fg, ...style }}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-bold opacity-85 truncate">{cuenta.nombre}</span>
        <span
          className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center text-[11px] font-extrabold"
          style={{ background: 'rgba(255,255,255,0.22)' }}
        >
          {marca.mono}
        </span>
      </div>
      <p className="text-xl font-extrabold mt-4 truncate">{formatMoneda(cuenta.saldo, cuenta.moneda)}</p>
    </div>
  )
}
