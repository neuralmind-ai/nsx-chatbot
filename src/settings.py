from pydantic import BaseSettings, HttpUrl


class Settings(BaseSettings):

    """Whatsapp Bot settings"""

    token: str
    base_url: HttpUrl
    text_url: HttpUrl

    # Configurations for requesting in NSX API's:
    search_index: str = "central_solucoes"  # index where documents are searched
    language: str = "pt"  # language in which the responses will be generated
    nsx_auth_requests_attempts: int = 3 # number of attempts NSX API will try in case of auth fail
    keycloak_login: str
    keycloak_password: str

    search_data_base_path: str = "/whatsappbot/app/search_data/"
    storing_duration_in_minutes: float = 60

    class Config:
        env_file = ".env"


settings = Settings()
