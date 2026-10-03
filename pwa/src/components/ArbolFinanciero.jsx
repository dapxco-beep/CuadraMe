// Medidor visual de salud financiera: un árbol que crece con tus buenas
// decisiones, en vez de un muñeco que se ahorca con las malas. Misma idea
// (cada estado financiero se ve reflejado en el dibujo) pero constructiva.
// etapa va de 0 (solo tierra, aún no hay nada que mostrar) a 6 (árbol
// florecido, salud financiera excelente).
export default function ArbolFinanciero({ etapa }) {
  const mostrar = (n) => etapa >= n
  const colorTronco = etapa >= 3 ? '#8a6a4a' : '#b8a88f'
  const colorHojas = etapa >= 5 ? 'var(--color-accent)' : etapa >= 3 ? 'var(--color-accent-2)' : '#c9c2ae'

  return (
    <svg viewBox="0 0 200 200" className="w-full h-full">
      {/* suelo — siempre visible, es la base de tus finanzas */}
      <line x1="30" y1="175" x2="170" y2="175" stroke="currentColor" strokeWidth="4" strokeLinecap="round" className="text-ink-soft" opacity="0.3" />

      {/* tronco, crece en alto según la etapa */}
      {mostrar(1) && (
        <line x1="100" y1="175" x2="100" y2={175 - Math.min(etapa, 3) * 22} stroke={colorTronco} strokeWidth="8" strokeLinecap="round" />
      )}

      {/* ramas */}
      {mostrar(2) && (
        <>
          <line x1="100" y1="130" x2="78" y2="108" stroke={colorTronco} strokeWidth="5" strokeLinecap="round" />
          <line x1="100" y1="130" x2="122" y2="108" stroke={colorTronco} strokeWidth="5" strokeLinecap="round" />
        </>
      )}
      {mostrar(3) && (
        <>
          <line x1="100" y1="109" x2="85" y2="88" stroke={colorTronco} strokeWidth="4" strokeLinecap="round" />
          <line x1="100" y1="109" x2="115" y2="88" stroke={colorTronco} strokeWidth="4" strokeLinecap="round" />
        </>
      )}

      {/* follaje, crece en tamaño y cambia de verde apagado a vibrante */}
      {mostrar(2) && <circle cx="78" cy="100" r="16" fill={colorHojas} opacity="0.9" />}
      {mostrar(2) && <circle cx="122" cy="100" r="16" fill={colorHojas} opacity="0.9" />}
      {mostrar(4) && <circle cx="100" cy="78" r="24" fill={colorHojas} opacity="0.95" />}
      {mostrar(5) && <circle cx="72" cy="82" r="14" fill={colorHojas} />}
      {mostrar(5) && <circle cx="128" cy="82" r="14" fill={colorHojas} />}

      {/* flores/frutos — solo cuando la salud financiera es excelente */}
      {mostrar(6) && (
        <>
          <circle cx="88" cy="72" r="4" fill="var(--color-accent-2)" />
          <circle cx="112" cy="68" r="4" fill="var(--color-accent-2)" />
          <circle cx="100" cy="90" r="4" fill="var(--color-accent-2)" />
          <circle cx="68" cy="88" r="4" fill="var(--color-accent-2)" />
          <circle cx="130" cy="90" r="4" fill="var(--color-accent-2)" />
        </>
      )}
    </svg>
  )
}
