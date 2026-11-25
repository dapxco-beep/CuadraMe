import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { anotarPantalla } from '../lib/usoPantallas'

/** No pinta nada: cada vez que se abre una pantalla nueva en la sesión, la anota (solo si la persona lo autorizó). */
export default function MedidorUso() {
  const { pathname, search } = useLocation()
  useEffect(() => {
    anotarPantalla(pathname, search)
  }, [pathname, search])
  return null
}
