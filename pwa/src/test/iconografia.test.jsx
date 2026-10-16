// Una sola familia de íconos (lucide-react). Los emojis quedan SOLO para lo que elige la persona
// (ícono de cuenta o categoría) y para los logros del ahorcado.
import { readFileSync, readdirSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Wallet } from 'lucide-react'
import Icono from '../components/Icono'
import { ICONO } from '../lib/tokens'

// Archivos donde el emoji es dato del usuario (selector/valor por defecto de cuenta o categoría),
// texto de un script/mensaje, o pertenecen a otro frente de trabajo (Traer movimientos).
const PERMITIDOS = new Set([
  'SelectorEmoji.jsx', 'HojaNuevaCategoria.jsx', 'CrearCuentaBanco.jsx', 'CrearCuenta.jsx', 'Cuentas.jsx', 'Categorias.jsx', 'SelectorCuenta.jsx',
  'SelectorCategoria.jsx', 'ConectarDispositivo.jsx', 'Sincronizacion.jsx', 'Correos.jsx', 'Conciliacion.jsx', 'ImportarArchivo.jsx',
])
const EMOJI = /\p{Extended_Pictographic}/u

function archivos(dir) {
  return readdirSync(dir).filter((f) => f.endsWith('.jsx'))
}

describe('Iconografía unificada', () => {
  it('no quedan emojis decorativos en pantallas ni componentes', () => {
    const raiz = `${process.cwd()}/src`
    const culpables = []
    for (const carpeta of ['screens', 'components']) {
      for (const f of archivos(`${raiz}/${carpeta}`)) {
        if (PERMITIDOS.has(f)) continue
        const texto = readFileSync(`${raiz}/${carpeta}/${f}`, 'utf8')
        // los comentarios no cuentan
        const sinComentarios = texto.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
        sinComentarios.split('\n').forEach((linea, i) => {
          if (EMOJI.test(linea)) culpables.push(`${carpeta}/${f}:${i + 1} ${linea.trim().slice(0, 60)}`)
        })
      }
    }
    expect(culpables).toEqual([])
  })

  it('<Icono> usa los tamaños 16/20/24 y es decorativo salvo que lleve título', () => {
    expect(ICONO).toEqual({ sm: 16, md: 20, lg: 24 })
    const { container } = render(
      <>
        <Icono icono={Wallet} tam="sm" />
        <Icono icono={Wallet} tam="lg" titulo="Billetera" />
      </>
    )
    const svgs = container.querySelectorAll('svg')
    expect(svgs[0]).toHaveAttribute('width', '16')
    expect(svgs[0]).toHaveAttribute('aria-hidden', 'true')
    expect(svgs[1]).toHaveAttribute('width', '24')
    expect(screen.getByRole('img', { name: 'Billetera' })).toBeInTheDocument()
  })

  it('los íconos lucide de la interfaz usan solo 16, 20 o 24 px (o ilustraciones ≥ 30)', () => {
    const raiz = `${process.cwd()}/src`
    const malos = []
    for (const carpeta of ['screens', 'components']) {
      for (const f of archivos(`${raiz}/${carpeta}`)) {
        if (['Sincronizacion.jsx', 'Correos.jsx', 'Conciliacion.jsx', 'ImportarArchivo.jsx'].includes(f)) continue
        const texto = readFileSync(`${raiz}/${carpeta}/${f}`, 'utf8')
        const nombres = [...texto.matchAll(/import\s*\{([^}]*)\}\s*from\s*'lucide-react'/g)].flatMap((m) =>
          m[1].split(',').map((x) => x.trim().split(/\s+as\s+/).pop()).filter(Boolean)
        )
        if (!nombres.length) continue
        const re = new RegExp(`<(${nombres.join('|')})(?:\\s[^>]*?)?\\ssize=\\{(\\d+)\\}`, 'g')
        for (const m of texto.matchAll(re)) {
          const n = Number(m[2])
          if (![16, 20, 24].includes(n) && n < 30) malos.push(`${carpeta}/${f}: ${m[1]} size=${n}`)
        }
      }
    }
    expect(malos).toEqual([])
  })
})
