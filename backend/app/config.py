from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./cuadrame.db"
    supabase_url: str = "https://pkapcorvslqdmigjmggu.supabase.co"
    openrouter_api_key: str = ""
    # Modelo de OpenRouter de PAGO y con política de no entrenamiento. Es lo único con lo que
    # contenido de Gmail podría llegar a una IA externa (y solo con consentimiento «ia»).
    # Vacío (por defecto) = el contenido de Gmail NUNCA sale hacia un proveedor de IA.
    openrouter_model_privado: str = ""
    # Frase secreta con la que se CIFRA el respaldo diario antes de enviarlo por correo.
    # Vacía = el respaldo por correo NO se envía (y se avisa al administrador).
    backup_passphrase: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_lifetime_cop: int = 2000000  # $20.000 COP × 100 (COP usa centavos en Stripe, no es zero-decimal)
    google_client_id: str = ""
    google_client_secret: str = ""
    fernet_key: str = ""
    api_base_url: str = "https://backend-production-aeab.up.railway.app"
    pwa_url: str = "https://cuadrame.dapx.shop"
    vapid_public_key: str = ""
    vapid_private_key_pem: str = ""
    vapid_subject: str = "mailto:dapxco@gmail.com"
    # Orígenes extra permitidos por CORS, separados por coma (además de la PWA y localhost)
    cors_origins_extra: str = ""
    cors_origin_regex: str = r"https://pwa-.*-dapxco\.vercel\.app"  # previews de Vercel
    cron_secret: str = ""
    # Cuadre con el extracto: un ajuste de saldo «grande» pide confirmación reforzada (puede ocultar
    # un movimiento que falta). Es grande si pasa este porcentaje del saldo del banco o este monto.
    cuadre_ajuste_grande_pct: float = 0.05
    cuadre_ajuste_grande_monto: float = 500000.0
    # Opcional: con esta clave (Supabase → Settings → API → service_role) el borrado de
    # cuenta también elimina el usuario de Supabase Auth. Sin ella se borran todos los
    # datos de CuadraMe, pero el registro de login (correo) queda en Supabase.
    supabase_service_role_key: str = ""
    sentry_dsn: str = ""  # vacío = monitoreo de errores desactivado, sin romper nada
    environment: str = "production"
    resend_api_key: str = ""  # vacío = backup por correo desactivado
    resend_from: str = "CuadraMe <backup@resend.dev>"
    backup_email: str = "dapxco@gmail.com"
    # Correo al que los usuarios piden acceso a Gmail mientras la app de Google está en modo Pruebas.
    soporte_email: str = "dapxco@gmail.com"
    # Mientras sea True, Correos avisa que Gmail es "por invitación" (la app de Google aún no está verificada).
    # Cuando Google apruebe la verificación, poner GMAIL_MODO_PRUEBAS=false en Railway.
    gmail_modo_pruebas: bool = True
    # Exigir el consentimiento específico (Gmail / IA) antes de usar esas funciones. Solo se apaga en pruebas.
    exigir_consentimientos: bool = True

    # ── Retención de datos de Gmail (minimización). 0 = NO purgar (apagado por defecto: decide el dueño) ──
    retencion_correos_ignorados_dias: int = 0   # propuesta 30: correos ignorados/descartados y extractos descartados
    retencion_correos_procesados_dias: int = 0  # propuesta 365: correos/extractos ya convertidos en movimiento
    retencion_eventos_dias: int = 0             # propuesta 365: eventos_actividad (avisos del administrador)

    # ── Monitor de capacidad y crecimiento (metricas/cron/avisos-crecimiento) ──
    # Correo de Daniel (dueño): recibe los avisos y es el único que ve «Salud del negocio».
    admin_email: str = ""
    # Límites del plan gratuito de Resend; si se sube de plan, cambiar las variables en Railway.
    resend_limite_dia: int = 100
    resend_limite_mes: int = 3000
    # Plan gratuito de Supabase: 500 MB de base.
    supabase_db_limite_mb: int = 500
    # Tope de usuarios con Gmail mientras la app de Google no está verificada.
    gmail_tope_usuarios: int = 100
    # Referencia de preguntas a la IA por mes antes de revisar el saldo de OpenRouter.
    ia_preguntas_mes_aviso: int = 3000
    # Errores 5xx en 24 h (en este proceso) a partir de los cuales se avisa.
    errores_5xx_aviso: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
