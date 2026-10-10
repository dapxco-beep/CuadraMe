// Solo se usa la autenticación de Supabase (login, sesión, recuperar clave). Por eso se importa
// el cliente de Auth directamente (@supabase/auth-js) y no el paquete completo
// (@supabase/supabase-js), que además trae realtime, storage, postgrest y functions: ~150 KB
// de JavaScript que nunca se ejecutan aquí y que el celular tenía que bajar y analizar antes
// de poder mostrar el login. La API es la misma: supabase.auth.getSession(), etc.
//
// Se replican los valores por defecto de createClient para NO cerrar la sesión de nadie:
//  - misma llave de almacenamiento: sb-<primer-segmento-del-host>-auth-token
//  - mismas cabeceras (apikey + Authorization con la llave anónima)
//  - autoRefreshToken, persistSession y detectSessionInUrl activos, flujo implícito
import { AuthClient } from '@supabase/auth-js'

const url = String(import.meta.env.VITE_SUPABASE_URL || '').replace(/\/+$/, '')
const llave = import.meta.env.VITE_SUPABASE_ANON_KEY

let host = ''
try {
  host = new URL(url).hostname.split('.')[0]
} catch {
  host = 'supabase'
}

export const supabase = {
  auth: new AuthClient({
    url: `${url}/auth/v1`,
    headers: { Authorization: `Bearer ${llave}`, apikey: `${llave}` },
    storageKey: `sb-${host}-auth-token`,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    flowType: 'implicit',
  }),
}
