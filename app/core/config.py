from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Bacchus Office Panel Backend"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # Cryptographic JWT Settings
    SECRET_KEY: str = "680875221eea6b89a1b1ce5d17c55229df8236c5245b6232206c422f8237042544267a0bab21af9a8e97c15be614b9b38951ae68a2ecb59fbcca5e1ea5949ca4"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Strict 15-minute access lifetime
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # 7-day sliding refresh session

    # SuperAdmin Master Provisioning
    SUPERADMIN_EMAIL: str = "superadmin@bacchusdistilleryindia.com"
    SUPERADMIN_PASSWORD: str = "Mohit@12345"

    # Database Parameters
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "niyaz2004"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "bacchus_office_db"

    # Redis Connection
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @computed_field
    def ASYNC_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()