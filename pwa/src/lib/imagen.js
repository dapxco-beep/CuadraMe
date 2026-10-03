// Prepara una foto para enviarla a la IA: la reduce y la comprime en el
// dispositivo (una foto de celular pesa 3-8 MB; leer un recibo no necesita
// tanto). Menos datos = más rápido, más barato y menos riesgo de exceder el
// límite del servidor. La imagen nunca se guarda: solo viaja y se descarta.
export const MAX_BYTES_ORIGINAL = 20 * 1024 * 1024 // rechaza archivos absurdos antes de decodificar
export const MAX_BYTES_ENVIO = 900 * 1024 // el servidor acepta hasta ~1.5 MB
const LADO_MAX = 1600

export function calcularTamano(ancho, alto, ladoMax = LADO_MAX) {
  const escala = Math.min(1, ladoMax / Math.max(ancho, alto))
  return { ancho: Math.round(ancho * escala), alto: Math.round(alto * escala) }
}

function cargarImagen(archivo) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(archivo)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('No pudimos abrir esa imagen. Prueba con otra foto.'))
    }
    img.src = url
  })
}

function aBlob(canvas, calidad) {
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', calidad))
}

function blobABase64(blob) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader()
    lector.onload = () => resolve(String(lector.result).split(',')[1])
    lector.onerror = () => reject(new Error('No pudimos leer la imagen.'))
    lector.readAsDataURL(blob)
  })
}

// Devuelve { base64, mime } en JPEG. Baja la calidad (y luego el tamaño) hasta
// quedar bajo el límite de envío.
export async function prepararImagen(archivo) {
  if (!archivo || !String(archivo.type).startsWith('image/')) {
    throw new Error('Elige una foto (JPG, PNG o WebP).')
  }
  if (archivo.size > MAX_BYTES_ORIGINAL) {
    throw new Error('Esa foto es muy pesada. Toma otra o elige una más pequeña.')
  }
  const img = await cargarImagen(archivo)
  let lado = LADO_MAX
  for (let intento = 0; intento < 4; intento++) {
    const { ancho, alto } = calcularTamano(img.naturalWidth, img.naturalHeight, lado)
    const canvas = document.createElement('canvas')
    canvas.width = ancho
    canvas.height = alto
    canvas.getContext('2d').drawImage(img, 0, 0, ancho, alto)
    for (const calidad of [0.8, 0.65, 0.5]) {
      const blob = await aBlob(canvas, calidad)
      if (blob && blob.size <= MAX_BYTES_ENVIO) return { base64: await blobABase64(blob), mime: 'image/jpeg' }
    }
    lado = Math.round(lado * 0.75)
  }
  throw new Error('No logramos reducir la foto lo suficiente. Intenta con otra.')
}
