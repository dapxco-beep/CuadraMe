from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./cuadrame.db"
    supabase_url: str = "https://ondijathequbilrohxtk.supabase.co"
    openrouter_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
