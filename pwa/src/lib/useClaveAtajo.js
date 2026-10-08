import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

// Estado de la clave del Atajo, según el contrato del backend:
//  - GET /perfil/api-key devuelve `api_key` completa solo si es nueva o si aún está en claro
//    (clave antigua sin migrar: sigue funcionando igual que siempre).
//  - Si ya está guardada como hash devuelve `api_key: null` + `prefijo` ("cdm_ab12…").
//  - POST /perfil/api-key/regenerar siempre devuelve la clave completa, UNA sola vez.
// `clave` solo existe mientras la pantalla esté abierta; `recienCreada` activa el aviso
// «cópiala ahora, no se vuelve a mostrar».
export function useClaveAtajo() {
  const [estado, setEstado] = useState({ cargando: true, clave: null, tieneClave: false, prefijo: '', recienCreada: false })

  useEffect(() => {
    let vivo = true
    api.apiKey()
      .then((r) => {
        if (!vivo) return
        setEstado({
          cargando: false,
          clave: r.api_key || null,
          tieneClave: r.tiene_clave !== false && (!!r.api_key || !!r.tiene_clave),
          prefijo: r.prefijo || '',
          // Una clave que acaba de crearse en este mismo GET tampoco se podrá ver otra vez.
          recienCreada: !!r.nueva,
        })
      })
      .catch(() => vivo && setEstado((e) => ({ ...e, cargando: false })))
    return () => { vivo = false }
  }, [])

  const crearNueva = useCallback(async () => {
    const r = await api.regenerarApiKey()
    setEstado({ cargando: false, clave: r.api_key, tieneClave: true, prefijo: '', recienCreada: true })
    return r.api_key
  }, [])

  return { ...estado, crearNueva }
}
