from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./cuadrame.db"
    supabase_url: str = "https://ondijathequbilrohxtk.supabase.co"
    openrouter_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_lifetime_cop: int = 2000000  # $20.000 COP × 100 (COP usa centavos en Stripe, no es zero-decimal)

    class Config:
        env_file = ".env"


settings = Settings()
