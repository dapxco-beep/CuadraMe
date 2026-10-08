// Cuadri, la mascota de CuadraMe: preferencia del usuario y frases cortas. Sin React (salvo el hook).
//
// Tono: tierno, curioso, humor suave, español colombiano. Reglas de oro para quien edite las frases:
//  - NUNCA burlarse de un gasto ni culpar a la persona ("gastaste de más" no; "revisemos juntos" sí).
//  - NUNCA prometer ahorro, rentabilidad ni dar asesoría ("compra/invierte en…" no).
//  - Una idea por frase, máximo ~60 caracteres, para que quepa en un globo pequeño.
// Para cambiar un texto basta editar este objeto; la app lo lee por clave.

import { useEffect, useState } from 'react'

export const POSES = ['feliz', 'hablando', 'sorprendido', 'preocupado', 'senalando', 'celebrando']

// Cada clave admite varias frases: `frase(clave, semilla)` elige una de forma estable (misma
// semilla = misma frase), así no cambia sola en cada render.
export const FRASES = {
  saludo: ['¡Hola! Soy Cuadri, vamos a cuadrar tus cuentas.', '¡Qué bueno verte! Empecemos con calma.'],
  cuadra: ['¡Eso cuadra!', '¡Todo en su sitio!'],
  noCuadra: ['Ups, algo no cuadra… lo revisamos juntos.', 'Mmm, aquí falta una pieza. La buscamos juntos.'],
  cargando: ['Un momentico, estoy acomodando tus cuentas…', 'Contando con cuidado…'],
  vacio: ['Aquí no hay nada todavía. ¡Todo empieza con el primero!', 'Esto está tranquilo. Cuando quieras, empezamos.'],
  consejo: ['Te cuento algo que me llamó la atención.', 'Mira, un dato que te puede servir.'],
  consejoSuave: ['Ojo con esto, sin afán: lo miramos juntos.', 'Esto merece una mirada, nada grave.'],
  errorGenerico: ['Ups, algo no salió bien. Intentémoslo otra vez.'],
  sinConexion: ['Parece que se fue el internet. Tus datos están a salvo; reintenta cuando vuelva.'],
  asistente: ['Pregúntame por tu plata y lo miramos juntos.'],
  asistentePensando: ['Déjame pensarlo un momentico…'],
  ayuda: ['Te muestro cómo se hace, paso a paso.'],
  aprende: ['Una lección de un minuto, sin letra menuda.'],
  celebraPasos: ['¡Terminaste los primeros pasos! Eso cuadra.'],
  celebraMeta: ['¡Meta cumplida! Eso sí cuadra.'],
  celebraMes: ['¡Cerraste el mes con plata de sobra! Eso cuadra.'],
  recorrido: {
    inicio: '¡Hola! Te muestro dónde está todo.',
    cuentas: 'Aquí van tus cuentas y tarjetas.',
    traer: 'Mira, hay varias formas de que los movimientos lleguen solos.',
    movimientos: 'Aquí ves lo que entra y lo que sale.',
    presupuesto: 'Ponle un tope a cada categoría, a tu ritmo.',
    metas: 'Pon nombre a lo que quieres lograr.',
    informes: 'Un vistazo claro a para dónde va tu plata.',
    asistente: 'Y si dudas, me preguntas.',
    privacidad: 'Tus datos son tuyos. ¡Y listo, a cuadrar!',
  },
}

// Pose de Cuadri en cada paso del recorrido (saluda, señala la zona, celebra al terminar).
export const POSE_RECORRIDO = {
  inicio: 'feliz',
  cuentas: 'senalando',
  traer: 'senalando',
  movimientos: 'senalando',
  presupuesto: 'hablando',
  metas: 'feliz',
  informes: 'senalando',
  asistente: 'hablando',
  privacidad: 'celebrando',
}

export function frase(clave, semilla = 0) {
  const v = FRASES[clave]
  if (!Array.isArray(v) || !v.length) return ''
  const n = typeof semilla === 'number' ? semilla : [...String(semilla)].reduce((a, c) => a + c.charCodeAt(0), 0)
  return v[Math.abs(n) % v.length]
}

// ── Preferencia «Mostrar a Cuadri» (por dispositivo, activada por defecto) ──
export const CLAVE_MOSTRAR = 'cuadrame:mostrar-cuadri'
const EVENTO = 'cuadrame:cuadri-cambio'

export function leerMostrarCuadri() {
  try {
    return localStorage.getItem(CLAVE_MOSTRAR) !== '0'
  } catch {
    return true
  }
}

export function guardarMostrarCuadri(valor) {
  try {
    localStorage.setItem(CLAVE_MOSTRAR, valor ? '1' : '0')
  } catch {
    /* sin almacenamiento: vale solo mientras la app esté abierta */
  }
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENTO))
}

/** [mostrar, cambiar]: se mantiene sincronizado entre pantallas y pestañas. */
export function useMostrarCuadri() {
  const [mostrar, setMostrar] = useState(leerMostrarCuadri)
  useEffect(() => {
    const sync = () => setMostrar(leerMostrarCuadri())
    window.addEventListener(EVENTO, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(EVENTO, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])
  return [mostrar, guardarMostrarCuadri]
}

/** ¿La persona pidió ahorrar datos? (Save-Data del navegador): entonces Cuadri se queda quieto. */
export function ahorroDeDatos() {
  try {
    return !!navigator.connection?.saveData
  } catch {
    return false
  }
}

// ── Celebraciones: cada una sale una sola vez por dispositivo (guarda solo ids de texto) ──
export const CLAVE_CELEBRADAS = 'cuadrame:cuadri-celebrado'

function leerCelebradas() {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE_CELEBRADAS) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

export const yaCelebrado = (id) => leerCelebradas().includes(id)

export function marcarCelebrado(id) {
  try {
    localStorage.setItem(CLAVE_CELEBRADAS, JSON.stringify([...leerCelebradas().filter((x) => x !== id), id].slice(-100)))
  } catch {
    /* sin almacenamiento: puede repetirse al recargar, no pasa nada */
  }
}
