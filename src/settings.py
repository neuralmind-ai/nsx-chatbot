from pydantic import BaseSettings, HttpUrl


class Settings(BaseSettings):
    token: str
    base_url: HttpUrl
    text_url: HttpUrl

    class Config:
        env_file = ".env"


settings = Settings()
