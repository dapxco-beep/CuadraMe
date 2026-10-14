import { Globe2 } from 'lucide-react'

// Banderas como SVG: en Windows los emoji de bandera se ven como las letras «CO», «US»…
// (el sistema no trae esos glifos). Un dibujo se ve igual en todos los dispositivos.
const PAIS = {
  CO: (
    <>
      <rect width="24" height="8" fill="#FCD116" />
      <rect y="8" width="24" height="4" fill="#003893" />
      <rect y="12" width="24" height="4" fill="#CE1126" />
    </>
  ),
  US: (
    <>
      <rect width="24" height="16" fill="#fff" />
      {[0, 2, 4, 6, 8, 10, 12, 14].map((y) => (
        <rect key={y} y={y * 1.0} width="24" height="1.23" fill="#B22234" />
      ))}
      <rect width="10.5" height="8.6" fill="#3C3B6E" />
    </>
  ),
  MX: (
    <>
      <rect width="8" height="16" fill="#006847" />
      <rect x="8" width="8" height="16" fill="#fff" />
      <rect x="16" width="8" height="16" fill="#CE1126" />
    </>
  ),
  PE: (
    <>
      <rect width="8" height="16" fill="#D91023" />
      <rect x="8" width="8" height="16" fill="#fff" />
      <rect x="16" width="8" height="16" fill="#D91023" />
    </>
  ),
  CL: (
    <>
      <rect width="24" height="8" fill="#fff" />
      <rect y="8" width="24" height="8" fill="#D52B1E" />
      <rect width="8" height="8" fill="#0039A6" />
    </>
  ),
  AR: (
    <>
      <rect width="24" height="16" fill="#74ACDF" />
      <rect y="5.3" width="24" height="5.4" fill="#fff" />
    </>
  ),
  EC: (
    <>
      <rect width="24" height="8" fill="#FFDD00" />
      <rect y="8" width="24" height="4" fill="#034EA2" />
      <rect y="12" width="24" height="4" fill="#ED1C24" />
    </>
  ),
  CR: (
    <>
      <rect width="24" height="16" fill="#002B7F" />
      <rect y="2.7" width="24" height="10.6" fill="#fff" />
      <rect y="5.3" width="24" height="5.4" fill="#CE1126" />
    </>
  ),
  EU: (
    <>
      <rect width="24" height="16" fill="#003399" />
      {Array.from({ length: 12 }, (_, i) => {
        const a = (i / 12) * Math.PI * 2
        return <circle key={i} cx={12 + 5 * Math.sin(a)} cy={8 - 5 * Math.cos(a)} r="0.9" fill="#FFCC00" />
      })}
    </>
  ),
}

export default function Bandera({ pais, className = '' }) {
  const dibujo = PAIS[pais]
  if (!dibujo) return <Globe2 size={16} aria-hidden="true" className={className} />
  return (
    <svg viewBox="0 0 24 16" width="20" height="14" aria-hidden="true" className={`rounded-[2px] shrink-0 ${className}`}>
      {dibujo}
    </svg>
  )
}
