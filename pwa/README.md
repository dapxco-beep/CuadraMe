# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.

## Estabilidad de la vista (zoom) y accesibilidad

La app se comporta como una app nativa: sin zoom por pellizco ni doble toque
(`viewport maximum-scale=1, user-scalable=no`, `touch-action: manipulation`, bloqueo de
`gesturestart` en iOS en `src/lib/estabilidadVista.js`), campos de 16 px en móvil para que iOS no haga
zoom al enfocar, y sin scroll horizontal. **No** se fija el tamaño de texto de `<html>`: el tamaño de
texto del sistema/navegador se sigue respetando. Verificación en navegador real con datos sintéticos:
`node scripts/verificar-ancho.mjs <url>` (360x740 y 390x844; requiere `playwright-core`).
