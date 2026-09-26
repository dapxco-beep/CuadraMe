import sharp from 'sharp'
import path from 'node:path'

const SRC = 'C:/Users/danie/Downloads/Gemini_Generated_Image_jf66h3jf66h3jf66.jpg'
const OUT = path.resolve('public/icons')

const meta = await sharp(SRC).metadata()
const w = meta.width
const h = meta.height

// El squircle en la imagen original va aprox. del 24% al 76% del lienzo.
const left = Math.round(w * 0.245)
const top = Math.round(h * 0.255)
const size = Math.round(w * 0.51)

const cropped = sharp(SRC).extract({ left, top, width: size, height: size })

// Icono maestro cuadrado, fondo sólido, llenando todo el lienzo (para 512/192/favicon)
await cropped.clone().resize(1024, 1024).toFile(`${OUT}/master-1024.png`)
await cropped.clone().resize(512, 512).toFile(`${OUT}/icon-512.png`)
await cropped.clone().resize(192, 192).toFile(`${OUT}/icon-192.png`)
await cropped.clone().resize(180, 180).toFile(`${OUT}/apple-touch-icon.png`)
await cropped.clone().resize(64, 64).toFile(`${OUT}/favicon-64.png`)
await cropped.clone().resize(32, 32).toFile(`${OUT}/favicon-32.png`)

// Maskable: símbolo con más aire alrededor (safe zone ~80% central) sobre fondo del degradado
const bgColor = { r: 13, g: 92, b: 67, alpha: 1 } // #0D5C43
const maskSize = 512
const innerSize = Math.round(maskSize * 0.72)
const innerBuf = await cropped.clone().resize(innerSize, innerSize).toBuffer()
await sharp({
  create: { width: maskSize, height: maskSize, channels: 4, background: bgColor },
})
  .composite([{ input: innerBuf, gravity: 'center' }])
  .png()
  .toFile(`${OUT}/icon-maskable-512.png`)

console.log('Listo. Archivos generados en', OUT)
