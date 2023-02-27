from pydantic import BaseSettings, HttpUrl


class Settings(BaseSettings):

    """Whatsapp Bot settings"""

    token: str
    base_url: HttpUrl
    text_url: HttpUrl

    # Configurations for requesting in NSX API's:
    search_index: str = "web"  # index where documents are searched
    language: str = "pt"  # language in which the responses will be generated

    search_data_base_path: str = "/whatsappbot/app/search_data/"
    storing_duration_in_minutes: float = 60

    class Config:
        env_file = ".env"


settings = Settings()
