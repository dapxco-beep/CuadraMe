import { Link } from 'react-router-dom'
import Cuadri from '../brand/Cuadri'
import { MENSAJE_POR_ESTADO } from '../lib/saludFinanciera'
import { useSaludCuadri } from '../lib/useSaludCuadri'

const NOMBRE = { critico: 'En apuros', mal: 'Mal', cansado: 'Cansado', regular: 'Regular', bien: 'Bien', radiante: 'Radiante' }

/**
 * Franja fija arriba de cada pantalla: a la derecha, Cuadri con su estado de salud financiera.
 * Un toque lleva a «Cómo está Cuadri». Reserva su alto desde el principio (así nada salta al llegar el dato).
 */
export default function CuadriEsquina() {
  const salud = useSaludCuadri()
  return (
    <div className="cuadri-esquina" data-testid="cuadri-esquina">
      {salud && (
        <Link
          to="/ahorcado"
          aria-label={`${MENSAJE_POR_ESTADO[salud.estado]}. Toca para ver cómo está`}
          className="cuadri-esquina-ficha"
        >
          <Cuadri estado={salud.estado} size={30} animar={false} siempre />
          <span className="text-xs font-semibold">{NOMBRE[salud.estado]}</span>
        </Link>
      )}
    </div>
  )
}
