// Seguridad local de la app: PIN, biometría (WebAuthn) y preferencias.
//
// Decisión clave: TODO vive en el dispositivo (localStorage). Nada de esto viaja
// al backend ni se escribe en logs. El PIN nunca se guarda: solo un hash
// PBKDF2-SHA256 con sal aleatoria y muchas iteraciones, para que robar el
// localStorage no revele el PIN trivialmente (aun así, 4-6 dígitos son pocas
// combinaciones: esto es una barrera contra curiosos, no contra un atacante
// con acceso total al dispositivo).
//
// Toda lectura/escritura va en try/catch porque localStorage puede lanzar
// (modo privado, almacenamiento bloqueado) y la app debe seguir funcionando.

const K_PIN = 'cuadrame_pin'
const K_BLOQUEO_MIN = 'cuadrame_bloqueo_min'
const K_BIO = 'cuadrame_bio_cred'
const K_OCULTAR = 'cuadrame_ocultar_saldos'
const K_INTENTOS = 'cuadrame_pin_intentos'

const ITERACIONES = 150_000
export const OPCIONES_BLOQUEO = [0, 1, 5, 15, 30] // minutos en segundo plano (0 = al instante)
export const BLOQUEO_POR_DEFECTO = 1

function leer(clave) {
  try {
    return localStorage.getItem(clave)
  } catch {
    return null
  }
}
function escribir(clave, valor) {
  try {
    localStorage.setItem(clave, valor)
    return true
  } catch {
    return false
  }
}
function borrar(clave) {
  try {
    localStorage.removeItem(clave)
  } catch {
    /* sin almacenamiento: nada que borrar */
  }
}

export function pinValido(pin) {
  return typeof pin === 'string' && /^\d{4,6}$/.test(pin)
}

const aHex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('')
const deHex = (hex) => new Uint8Array(hex.match(/../g).map((h) => parseInt(h, 16)))

async function derivar(pin, sal, iter) {
  const llave = await crypto.subtle.importKey('raw', new TextEncoder().encode(pin), 'PBKDF2', false, ['deriveBits'])
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: sal, iterations: iter }, llave, 256)
  return aHex(bits)
}

export function tienePin() {
  return !!leer(K_PIN)
}

export async function guardarPin(pin) {
  if (!pinValido(pin)) throw new Error('El PIN debe tener entre 4 y 6 dígitos')
  const sal = crypto.getRandomValues(new Uint8Array(16))
  const hash = await derivar(pin, sal, ITERACIONES)
  const ok = escribir(K_PIN, JSON.stringify({ sal: aHex(sal), hash, iter: ITERACIONES }))
  if (!ok) throw new Error('Tu navegador no permite guardar el PIN en este dispositivo')
  borrar(K_INTENTOS)
}

export async function verificarPin(pin) {
  const crudo = leer(K_PIN)
  if (!crudo || !pinValido(pin)) return false
  try {
    const { sal, hash, iter } = JSON.parse(crudo)
    const calculado = await derivar(pin, deHex(sal), iter)
    // comparación de longitud fija: no corta en el primer carácter distinto
    let dif = calculado.length ^ hash.length
    for (let i = 0; i < calculado.length; i++) dif |= calculado.charCodeAt(i) ^ (hash.charCodeAt(i) || 0)
    return dif === 0
  } catch {
    return false
  }
}

// ── Intentos fallidos: tras 5 errores seguidos se espera un tiempo creciente ──
export function estadoIntentos(ahora = Date.now()) {
  try {
    const { n = 0, hasta = 0 } = JSON.parse(leer(K_INTENTOS) || '{}')
    return { fallos: n, espera: Math.max(0, Math.ceil((hasta - ahora) / 1000)) }
  } catch {
    return { fallos: 0, espera: 0 }
  }
}
export function registrarFallo(ahora = Date.now()) {
  const { fallos } = estadoIntentos(ahora)
  const n = fallos + 1
  const espera = n >= 5 ? Math.min(300, 15 * 2 ** (n - 5)) : 0 // 15s, 30s, 60s... tope 5 min
  escribir(K_INTENTOS, JSON.stringify({ n, hasta: ahora + espera * 1000 }))
  return { fallos: n, espera }
}
export function limpiarFallos() {
  borrar(K_INTENTOS)
}

// ── Bloqueo automático ──
export function minutosBloqueo() {
  const n = Number(leer(K_BLOQUEO_MIN))
  return OPCIONES_BLOQUEO.includes(n) && leer(K_BLOQUEO_MIN) !== null ? n : BLOQUEO_POR_DEFECTO
}
export function guardarMinutosBloqueo(min) {
  escribir(K_BLOQUEO_MIN, String(min))
}

// ── Ocultar saldos ──
export function leerOcultarSaldos() {
  return leer(K_OCULTAR) === '1'
}
export function guardarOcultarSaldos(valor) {
  escribir(K_OCULTAR, valor ? '1' : '0')
}

// ── Biometría (WebAuthn) ──
// La huella/Face ID la verifica el sistema operativo; aquí solo guardamos el id
// de la credencial para pedirla después. Es un candado local: sin servidor que
// valide la firma, por eso el PIN sigue siendo el respaldo y la fuente de verdad.
export function biometriaSoportada() {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials?.create
}
export async function biometriaDisponible() {
  try {
    if (!biometriaSoportada()) return false
    return await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
  } catch {
    return false
  }
}
export function biometriaActiva() {
  return !!leer(K_BIO)
}
export async function activarBiometria(nombreUsuario = 'usuario') {
  const cred = await navigator.credentials.create({
    publicKey: {
      challenge: crypto.getRandomValues(new Uint8Array(32)),
      rp: { name: 'CuadraMe' },
      user: { id: crypto.getRandomValues(new Uint8Array(16)), name: nombreUsuario, displayName: nombreUsuario },
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
      authenticatorSelection: { authenticatorAttachment: 'platform', userVerification: 'required' },
      timeout: 60000,
    },
  })
  if (!cred) throw new Error('No se pudo registrar la huella o el rostro')
  escribir(K_BIO, aHex(cred.rawId))
}
export async function verificarBiometria() {
  const id = leer(K_BIO)
  if (!id || !biometriaSoportada()) return false
  try {
    const res = await navigator.credentials.get({
      publicKey: {
        challenge: crypto.getRandomValues(new Uint8Array(32)),
        allowCredentials: [{ type: 'public-key', id: deHex(id) }],
        userVerification: 'required',
        timeout: 60000,
      },
    })
    return !!res
  } catch {
    return false // cancelado o fallido: el usuario usa el PIN
  }
}
export function desactivarBiometria() {
  borrar(K_BIO)
}

// Cerrar sesión borra todo lo de seguridad (PIN, huella, intentos y ajuste de bloqueo).
// La preferencia de ocultar saldos es cosmética y se conserva.
export function borrarSeguridad() {
  borrar(K_PIN)
  borrar(K_BIO)
  borrar(K_INTENTOS)
  borrar(K_BLOQUEO_MIN)
}
