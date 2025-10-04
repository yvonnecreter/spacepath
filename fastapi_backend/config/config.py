import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    LLM_BACKEND: str = "openai"
    OPENAI_API_KEY: str = "dummy_key_for_development"
    LLM_MODEL: str = "gpt-3.5-turbo"
    EMBEDDING_MODEL: str = "text-embedding-ada-002"

    class Config:
        home_path = os.path.join(os.path.dirname(__file__), "../..")
        env_file = os.path.join(home_path, "fastapi_backend/.env")
        env_file_encoding = "utf-8"

settings = Settings()