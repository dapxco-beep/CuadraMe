import { useState } from 'react'
import { Copy, Download, Share, X } from 'lucide-react'
import Icono from './Icono'
import GuiaInstalar from './GuiaInstalar'
import { Boton } from './ui'
import { Isotipo } from '../brand/Marca'
import { detectarDispositivo, estaInstalada } from '../lib/primerUso'
import { instalar, useInstalable } from '../lib/instalarPwa'
import { abrirMenuCompartir, avisoInstalarCerrado, cerrarAvisoInstalar, esNavegadorIntegrado, puedeCompartir } from '../lib/instalarIphone'

/**
 * Aviso de Inicio: «Pon CuadraMe en tu celular». Solo sale en un celular, en el navegador (no si ya está instalada) y
 * hasta que se cierre (14 días). Android: botón «Instalar» de un toque. iPhone: abre de una vez el menú de compartir.
 */
export default function AvisoInstalar({ className = '' }) {
  const instalable = useInstalable()
  const [cerrado, setCerrado] = useState(() => avisoInstalarCerrado())
  const [guia, setGuia] = useState(false)
  const [pista, setPista] = useState(false)
  const [copiado, setCopiado] = useState(false)
  const dispositivo = detectarDispositivo()

  if (cerrado || estaInstalada() || (dispositivo !== 'ios' && dispositivo !== 'android')) return null

  const integrado = dispositivo === 'ios' && esNavegadorIntegrado()

  function cerrar() {
    cerrarAvisoInstalar()
    setCerrado(true)
  }
  async function alInstalar() {
    if (dispositivo === 'android') {
      if (instalable) {
        if ((await instalar()) === 'accepted') cerrar()
        return
      }
      setGuia(true)
      return
    }
    const r = await abrirMenuCompartir()
    if (r === 'abierto') setPista(true)
    else if (r === 'no-disponible') setGuia(true)
  }
  async function copiarEnlace() {
    try {
      await navigator.clipboard.writeText(window.location.origin)
      setCopiado(true)
    } catch {
      setGuia(true)
    }
  }

  return (
    <section aria-label="Instalar CuadraMe" data-testid="aviso-instalar" className={`tarjeta-suave relative ${className}`}>
      <button type="button" onClick={cerrar} aria-label="Cerrar este aviso" className="absolute top-1 right-1 w-11 h-11 flex items-center justify-center text-ink-soft">
        <Icono icono={X} tam="sm" />
      </button>
      <div className="flex items-start gap-3 pr-8">
        <Isotipo size={36} />
        <div className="min-w-0">
          <h2 className="t-h2">{integrado ? 'Ábrelo en Safari para instalarlo' : 'Pon CuadraMe en tu celular'}</h2>
          <p className="t-apoyo mt-0.5">
            {integrado
              ? 'Este navegador no deja instalar. Copia el enlace y pégalo en Safari.'
              : 'Queda con su ícono junto a tus apps y se abre con un toque. No cuesta nada.'}
          </p>
        </div>
      </div>

      {pista && (
        <p role="status" data-testid="pista-compartir" className="mt-3 rounded-2xl bg-paper-raised p-3 text-sm">
          En el menú que se abrió, desliza hacia abajo y toca <b>«Añadir a pantalla de inicio»</b>. Luego toca <b>Añadir</b>.
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {integrado ? (
          <Boton tam="sm" onClick={copiarEnlace} data-testid="copiar-enlace">
            <Icono icono={Copy} tam="sm" /> {copiado ? 'Enlace copiado' : 'Copiar enlace'}
          </Boton>
        ) : (
          <Boton tam="sm" onClick={alInstalar} data-testid="instalar-ahora">
            <Icono icono={dispositivo === 'ios' && puedeCompartir() ? Share : Download} tam="sm" />
            {dispositivo === 'ios' ? 'Instalar' : 'Instalar CuadraMe'}
          </Boton>
        )}
        <Boton tam="sm" variante="secundario" onClick={() => setGuia(true)}>
          Ver los pasos
        </Boton>
      </div>
      {guia && <GuiaInstalar onCerrar={() => setGuia(false)} />}
    </section>
  )
}
