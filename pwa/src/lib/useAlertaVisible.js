import { useEffect, useRef } from 'react'

// Un mensaje de error de formulario que aparece bajo el pliegue pasa inadvertido: el usuario
// toca "Guardar" y parece que no pasó nada. Este hook devuelve un ref para el <p> del error;
// cada vez que aparece un error nuevo se desplaza hasta dejarlo a la vista.
export function useAlertaVisible(error) {
  const ref = useRef(null)
  useEffect(() => {
    if (error) ref.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
  }, [error])
  return ref
}
