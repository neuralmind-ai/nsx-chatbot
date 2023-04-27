from pydantic import BaseSettings, HttpUrl


class Settings(BaseSettings):

    """Whatsapp Bot settings"""

    token: str
    base_url: HttpUrl
    text_url: HttpUrl

    #Logging configurations:
    log_path: str = "/whatsappbot/logs/"

    # Configurations for requesting in NSX API's:
    search_index: str = "web"  # index where documents are searched
    search_index_needs_token: bool = False #Determine if a keycloak token should be used to access the index
    language: str = "pt"  # language in which the responses will be generated
    nsx_auth_requests_attempts: int = 3 # number of attempts NSX API will try in case of auth fail
    keycloak_login: str
    keycloak_password: str

    # Search data storing configurations: 
    search_data_base_path: str = "/whatsappbot/app/search_data/"
    storing_duration_in_minutes: float = 60

    #Answer configurations:
    answer_base_string: str = "Fundep Concursos\n"

    class Config:
        env_file = ".env"

settings = Settings()
