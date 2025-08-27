from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "resumes"
    minio_secure: bool = Field(default=False, alias="MINIO_USE_SSL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra fields from environment variables

# Create a singleton instance of the Settings class
settings = Settings()
