// Ayudas puras de «Enséñale a leer este correo»: qué números del texto pueden ser el monto y cómo se arma
// el nombre a partir de las palabras que la persona toca. El servidor vuelve a comprobar todo lo que recibe.

// Números que parecen una cifra de plata: con «$» o de 3 dígitos o más. Cada uno con las palabras que le anteceden.
export function montosDelTexto(texto) {
  const salida = []
  const vistos = new Set()
  const re = /\$?\s?\d[\d.,]*/g
  let m
  while ((m = re.exec(texto || '')) !== null) {
    const crudo = m[0].trim().replace(/[.,]+$/, '')
    const digitos = crudo.replace(/\D/g, '').length
    if (!crudo.includes('$') && digitos < 3) continue
    if (vistos.has(crudo)) continue
    vistos.add(crudo)
    const antes = texto.slice(Math.max(0, m.index - 40), m.index).trim().split(/\s+/).slice(-3).join(' ')
    salida.push({ texto: crudo, contexto: antes })
  }
  return salida
}

export function palabrasDelTexto(texto) {
  return (texto || '').split(/\s+/).filter(Boolean)
}

// Rango de palabras tocadas [a, b] (en cualquier orden) -> «ICETEX», «Colegio San José».
export function nombreDelRango(palabras, rango) {
  if (!rango) return ''
  const [a, b] = rango.a <= rango.b ? [rango.a, rango.b] : [rango.b, rango.a]
  return palabras.slice(a, b + 1).join(' ').replace(/^[\s.,;:]+|[\s.,;:]+$/g, '')
}

// Un toque sobre la palabra i: el primero marca una palabra, el segundo extiende hasta ahí, el tercero empieza de nuevo.
export function tocarPalabra(rango, i) {
  if (!rango) return { a: i, b: i }
  if (rango.a === rango.b && rango.a !== i) return { a: rango.a, b: i }
  if (rango.a === rango.b && rango.a === i) return null
  return { a: i, b: i }
}

export function textoSimilares(n) {
  return n === 1 ? 'Encontré 1 correo parecido que había dejado de lado.' : `Encontré ${n} correos parecidos que había dejado de lado.`
}

export function textoRecuperados(n) {
  if (!n) return 'No había correos parecidos para pasar.'
  return n === 1 ? 'Pasé 1 correo a «Por revisar».' : `Pasé ${n} correos a «Por revisar».`
}
