import { CircleCheck } from 'lucide-react'
import Icono from './Icono'
import { Boton } from './ui'
import { textoAgregarAlterno } from '../lib/cuentaNueva'

/**
 * Se muestra justo después de crear una cuenta de un banco: ofrece crear la otra del mismo
 * banco (ahorros <-> tarjeta de crédito) sin volver a elegir banco, o seguir.
 */
export default function AgregarOtraDelBanco({ banco, tipoCreado, nombreCreada, onAgregar, onListo, textoListo = 'No, ya está' }) {
  return (
    <div data-testid="agregar-otra-del-banco" role="status" className="space-y-4">
      <div className="flex items-start gap-3">
        <span className="text-accent mt-0.5"><Icono icono={CircleCheck} tam="lg" /></span>
        <div>
          <p className="t-h2">Listo, creamos «{nombreCreada}»</p>
          <p className="t-cuerpo text-ink-soft mt-1">
            Muchos bancos dan las dos cosas: cuenta de ahorros y tarjeta de crédito. Si tienes la otra, agrégala ahora y
            no tendrás que elegir el banco de nuevo.
          </p>
        </div>
      </div>
      <Boton bloque onClick={onAgregar}>{textoAgregarAlterno(banco, tipoCreado)}</Boton>
      <Boton bloque variante="secundario" onClick={onListo}>{textoListo}</Boton>
    </div>
  )
}
