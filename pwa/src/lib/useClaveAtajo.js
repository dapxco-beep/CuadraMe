import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

// Estado de la clave del Atajo, según el contrato del backend:
//  - GET /perfil/api-key devuelve `api_key` completa si se guardó cifrada (siempre visible para su dueño) o si aún
//    está en claro. Las claves de antes del cifrado quedan visibles solas cuando el Atajo las usa una vez.
//  - Si solo existe el hash devuelve `api_key: null` + `prefijo` ("cdm_ab12…").
//  - POST /perfil/api-key/regenerar devuelve la clave nueva completa.
// `clave` solo existe mientras la pantalla esté abierta; `recienCreada` activa el aviso «esta es tu clave nueva».
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
