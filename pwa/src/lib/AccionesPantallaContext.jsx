import { createContext, useContext } from 'react'
import { createPortal } from 'react-dom'

// Las pantallas con pestañas (Presupuesto, Metas, Cuentas…) ponen el título arriba y las pestañas debajo. Los botones de
// acción de cada pestaña («+», «Pasar plata», ayuda…) antes caían en una fila propia, sola, bajo las pestañas. Ahora el
// contenedor ofrece un destino en la MISMA línea del título y `EncabezadoPantalla` mueve ahí esos botones.
//
//   undefined → no hay contenedor con pestañas: la pantalla pinta su encabezado de siempre (pantalla suelta).
//   null      → el contenedor existe pero su destino aún no está montado (un instante): no se pinta nada.
//   Element   → destino listo: los botones se pintan allí (el estado y los eventos siguen siendo de la pantalla).
export const AccionesPantallaContext = createContext(undefined)

/** Encabezado de una pantalla que puede ir dentro de pestañas. Fuera de ellas es un <header> normal. */
export function EncabezadoPantalla({ embebido, className, children }) {
  const destino = useContext(AccionesPantallaContext)
  if (embebido && destino !== undefined) return destino ? createPortal(children, destino) : null
  return <header className={className}>{children}</header>
}
