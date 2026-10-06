import { marcaDeEntidad } from '../lib/entidadesFinancierasCO'
import { useBloqueo } from '../lib/BloqueoContext'
import { cupoDisponible, deudaTarjeta, esCredito, textoActualizado } from '../lib/saldos'

// Tarjeta con identidad de marca real (color + monograma) de la entidad que el
// usuario escribió al crear la cuenta — igual que abrir la billetera y reconocer
// cada tarjeta física por su color, sin tener que leer el nombre completo.
//
// El número siempre lleva su etiqueta: "Saldo actual" en cuentas normales y, en
// tarjetas de crédito, "Debes" + "Disponible del cupo" (un saldo -800.000 solo
// confunde). `ultimoMovimiento` (ISO) agrega "actualizado hoy" / la fecha.
export default function TarjetaCuenta({ cuenta, style, className = '', ultimoMovimiento, compacta = false }) {
  const marca = marcaDeEntidad(cuenta.nombre)
  const { fmt } = useBloqueo()
  const credito = esCredito(cuenta)
  const disponible = cupoDisponible(cuenta)

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
      <p className="text-[11px] font-semibold uppercase tracking-wide opacity-75 mt-3">{credito ? 'Debes' : 'Saldo actual'}</p>
      <p className="text-xl font-extrabold truncate">{fmt(credito ? deudaTarjeta(cuenta) : cuenta.saldo, cuenta.moneda)}</p>
      {!compacta && (
        <p className="text-[11px] opacity-80 mt-0.5">
          {credito && disponible != null ? `Disponible del cupo: ${fmt(disponible, cuenta.moneda)}` : ''}
          {credito && disponible != null && ultimoMovimiento !== undefined ? ' · ' : ''}
          {/* undefined = aún no sabemos; null = la cuenta no tiene movimientos */}
          {ultimoMovimiento === undefined ? '' : textoActualizado(ultimoMovimiento)}
        </p>
      )}
    </div>
  )
}
