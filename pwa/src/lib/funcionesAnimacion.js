// Motor de animación de framer-motion, en su propio archivo para que LazyMotion lo descargue
// DESPUÉS del primer pintado (ver App.jsx). Los componentes usan `m` (la versión liviana de
// `motion`): sin este archivo la app ya se ve; las animaciones arrancan en cuanto llega.
import { domAnimation } from 'framer-motion'

export default domAnimation
