// Tokens de diseño en JS. Los mismos valores viven en index.css (--dur-*, --ease)
// para el CSS; aquí están para framer-motion y para temporizadores (p. ej. la salida
// de las hojas), de modo que CSS y JS nunca se desincronicen en la duración.
export const DUR_MS = { rapido: 120, normal: 200, lento: 320 }
export const DUR = { rapido: 0.12, normal: 0.2, lento: 0.32 } // segundos (framer-motion)
export const EASE = [0.22, 1, 0.36, 1] // misma curva que --ease

// Tamaños de ícono permitidos (px): dentro de texto, estándar, protagonista
export const ICONO = { sm: 16, md: 20, lg: 24 }
