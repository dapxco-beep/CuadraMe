# Registro con código: configurar el correo de Supabase (3 minutos)

**Por qué:** Supabase manda hoy los correos de registro con su servicio gratuito integrado, que solo entrega a correos del equipo y
permite 2 correos por hora. Por eso una persona nueva no recibe la confirmación. Con Resend (ya verificado en `cuadrame.dapx.shop`)
llega a cualquiera. La pantalla de la app ya pide el código (y también sirve el enlace del correo).

Panel: `https://supabase.com/dashboard/project/pkapcorvslqdmigjmggu`

## 1. Servidor de correo (Authentication → Emails → SMTP Settings → Enable custom SMTP)
| Campo | Valor |
|---|---|
| Sender email | `hola@cuadrame.dapx.shop` |
| Sender name | `CuadraMe` |
| Host | `smtp.resend.com` |
| Port | `465` |
| Username | `resend` |
| Password | la clave de Resend (`DANIEL_RESEND_API_KEY` en `DAPX/.secretos/daniel.env`; es de la cuenta donde está verificado el dominio) |

Guarda. Después, en **Authentication → Rate Limits**, sube «Emails sent per hour» a `30`.

## 2. URL del sitio (Authentication → URL Configuration)
- **Site URL:** `https://cuadrame.dapx.shop` (hoy apunta a `pwa-seven-ecru.vercel.app`).

## 3. Correo de confirmación con código (Authentication → Emails → Templates → «Confirm signup»)
- **Subject:** `Tu código de CuadraMe: {{ .Token }}`
- **Body (HTML):**

```html
<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;color:#201B14">
  <h2 style="color:#B9461A;margin-bottom:4px">Confirma tu correo en CuadraMe</h2>
  <p>Escribe este código en la app:</p>
  <p style="font-size:32px;font-weight:bold;letter-spacing:6px;background:#F7F4EE;padding:14px;text-align:center;border-radius:12px;margin:12px 0">{{ .Token }}</p>
  <p>Si prefieres, toca este enlace: <a href="{{ .ConfirmationURL }}" style="color:#B9461A">Confirmar mi correo</a></p>
  <p style="color:#6B6258;font-size:13px">El código vence en una hora. Si no creaste una cuenta en CuadraMe, ignora este correo.</p>
</div>
```

- (Opcional) **Authentication → Providers → Email → «OTP Length»:** `6` (hoy es 8; la app acepta de 6 a 8 dígitos).

## 4. Probar
Abre `cuadrame.dapx.shop` en una ventana de incógnito → «¿No tienes cuenta? Regístrate» → escribe un correo tuyo distinto al habitual
(sirve `dapxco+prueba@gmail.com`) → debe llegar un correo «Tu código de CuadraMe» → escribe el código en la app → entra solo.

**Revertir:** apaga «Custom SMTP» y vuelve a poner el subject/body anteriores (el panel conserva la plantilla original como «Reset to default»).
