// userEvent sin pausas: la API directa de user-event espera un setTimeout(0) entre acciones
// (delay: 0). En jsdom con muchas pruebas en paralelo cada pausa se convierte en cientos de ms.
// Con delay: null no hay pausas y las acciones siguen siendo igual de realistas (mismos eventos).
// Cada llamada crea su propia sesión, igual que la API directa original, para no compartir estado.
import real from '@testing-library/user-event'

const acciones = [
  'click', 'dblClick', 'tripleClick', 'hover', 'unhover', 'type', 'clear', 'keyboard',
  'tab', 'selectOptions', 'deselectOptions', 'upload', 'paste', 'pointer', 'copy', 'cut',
]

const userEvent = {
  setup: (opciones = {}) => real.setup({ delay: null, ...opciones }),
}
for (const nombre of acciones) {
  userEvent[nombre] = (...args) => real.setup({ delay: null })[nombre](...args)
}

export default userEvent
