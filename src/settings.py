from pydantic import BaseSettings, HttpUrl


class Settings(BaseSettings):
    """Whatsapp Bot settings"""

    token: str
    base_url: HttpUrl
    text_url: HttpUrl

    # Logging configurations:
    log_path: str = "logs/"

    # Prompt_answerer
    completion_endpoint: str = "http://localhost:7000/api/openai/completions"
    moderation_endpoint: str = "http://localhost:7000/api/openai/moderations"
    max_tokens_prompt: int = 4000

    # Neuralsearchx
    nsx_endpoint: str = "https://nsx.ai/api/search"
    api_key: str = ""
    search_index: str = "FUNDEP_Ciencias"

    # Chat_history
    max_tokens_chat_history: int = 1500

    # Tiktoken
    encoding_model = "gpt-3.5-turbo"

    # Redis
    expiration_time_in_seconds: int = 3600

    # ChatHandler
    max_num_reasoning: int = 6

    # AzureCosmos
    cosmos_endpoint: str = "https://chatbot-nosql.documents.azure.com:443/"
    cosmos_key: str
    cosmos_database_name: str = "chatbot"
    cosmos_container_name: str = "chatHistory"

    class Config:
        env_file = ".env"


settings = Settings()
