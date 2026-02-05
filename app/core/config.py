from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str | None = None
    VECTOR_DB_PATH: str = "./vector_store"

    class Config:
        env_file = ".env"

settings = Settings()
