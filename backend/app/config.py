from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./cuadrame.db"
    supabase_url: str = "https://pkapcorvslqdmigjmggu.supabase.co"
    openrouter_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_lifetime_cop: int = 2000000  # $20.000 COP × 100 (COP usa centavos en Stripe, no es zero-decimal)
    google_client_id: str = ""
    google_client_secret: str = ""
    fernet_key: str = ""
    api_base_url: str = "https://backend-production-aeab.up.railway.app"
    pwa_url: str = "https://pwa-seven-ecru.vercel.app"
    vapid_public_key: str = ""
    vapid_private_key_pem: str = ""
    vapid_subject: str = "mailto:dapxco@gmail.com"
    # Orígenes extra permitidos por CORS, separados por coma (además de la PWA y localhost)
    cors_origins_extra: str = ""
    cors_origin_regex: str = r"https://pwa-.*-dapxco\.vercel\.app"  # previews de Vercel
    cron_secret: str = ""
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

    class Config:
        env_file = ".env"


settings = Settings()
