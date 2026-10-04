import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import TarjetaCuenta from './TarjetaCuenta'

// Mazo de cuentas tipo billetera: la tarjeta de enfrente se arrastra hacia un lado
// (o se desliza con el dedo) y pasa al fondo; tocarla abre el detalle de esa cuenta (saldo actual, movimientos, ajustar saldo).
// Se ven como mucho 3 tarjetas apiladas; las demás esperan detrás sin pesar en pantalla.

const VISIBLES = 3
const DESPLAZAMIENTO = 18 // px que asoma cada tarjeta de atrás
const UMBRAL = 70 // px de arrastre para pasar a la siguiente

// Se remonta si cambia el número de cuentas (alta/baja), lo que reinicia el orden.
export default function MazoCuentas({ cuentas, ultimos }) {
  return <Mazo key={cuentas.length} cuentas={cuentas} ultimos={ultimos} />
}

function Mazo({ cuentas, ultimos }) {
  const navegar = useNavigate()
  const reducir = useReducedMotion()
  const [orden, setOrden] = useState(() => cuentas.map((_, i) => i))

  if (cuentas.length === 0) return null

  const apilables = Math.min(cuentas.length, VISIBLES)
  const alto = 112 + (apilables - 1) * DESPLAZAMIENTO
  const resorte = reducir ? { duration: 0 } : { type: 'spring', stiffness: 380, damping: 32 }

  function pasarAlFondo() {
    setOrden((o) => [...o.slice(1), o[0]])
  }

  function traerAlFrente(posicion) {
    // Tocar una tarjeta de atrás la trae al frente, conservando el orden del resto.
    setOrden((o) => [...o.slice(posicion), ...o.slice(0, posicion)])
  }

  const frente = orden[0]

  return (
    <div>
      <div
        className="relative"
        style={{ height: `${alto}px`, touchAction: 'pan-y' }}
        role="group"
        aria-label={`Tus cuentas, ${cuentas.length}. Desliza la tarjeta para ver la siguiente.`}
      >
        {orden.map((idx, pos) => {
          const c = cuentas[idx]
          if (!c || pos >= VISIBLES) return null
          const esFrente = pos === 0
          return (
            <motion.div
              key={c.id}
              className="absolute inset-x-0 top-0"
              style={{ zIndex: VISIBLES - pos, transformOrigin: 'top center', cursor: esFrente ? 'grab' : 'pointer' }}
              initial={false}
              animate={{ y: pos * DESPLAZAMIENTO, scale: 1 - pos * 0.05, opacity: 1 }}
              transition={resorte}
              drag={esFrente && cuentas.length > 1 ? 'x' : false}
              dragSnapToOrigin
              dragElastic={0.6}
              whileDrag={{ scale: 1.02, rotate: 0 }}
              onDragEnd={(_, info) => {
                if (Math.abs(info.offset.x) > UMBRAL || Math.abs(info.velocity.x) > 500) pasarAlFondo()
              }}
              onTap={() => (esFrente ? navegar(`/cuentas?cuenta=${c.id}`) : traerAlFrente(pos))}
            >
              <TarjetaCuenta cuenta={c} ultimoMovimiento={ultimos ? (ultimos[c.id] ?? null) : undefined} />
            </motion.div>
          )
        })}
      </div>

      {cuentas.length > 1 && (
        <div className="flex items-center justify-center mt-1">
          {cuentas.map((c, i) => (
            <button
              key={c.id}
              type="button"
              aria-label={`Ver ${c.nombre}`}
              aria-current={i === frente ? 'true' : undefined}
              onClick={() => traerAlFrente(orden.indexOf(i))}
              className="w-6 h-8 flex items-center justify-center"
            >
              <span className={`h-1.5 rounded-full transition-all ${i === frente ? 'w-4 bg-accent' : 'w-1.5 bg-line'}`} />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
