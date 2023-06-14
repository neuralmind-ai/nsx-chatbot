from dotenv import load_dotenv
from pydantic import BaseSettings, HttpUrl

# Load environment variables from .env file
load_dotenv()


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
    api_key: str = ""
    max_docs_to_return: int = 5
    nsx_endpoint: str = "https://nsx.ai/api/search"
    nsx_score_endpoint: str = "https://nsx.ai/api/inference/score"
    nsx_sense_endpoint = "https://nsx.ai/api/multidocqa"
    search_index: str = "FUNDEP_Ciencias"

    # Chat_history
    max_tokens_chat_history: int = 1500

    # Tiktoken
    encoding_model = "gpt-3.5-turbo"

    # Redis
    expiration_time_in_seconds: int = 3600

    # ChatHandler
    available_models = ["gpt-3.5-turbo", "gpt-3.5-turbo-azure", "gpt-4"]
    max_faq_questions: int = 5
    max_num_reasoning: int = 6
    max_tokens_faq_prompt: int = 3700
    reasoning_model = "gpt-3.5-turbo-azure"
    chatbot_language: str = "pt"

    # IndexMenu
    menu_message = "Olá. Escolha um dos itens abaixo para iniciar a conversa."
    selection_message: str = "Selecione um item"
    request_menu_message: str = "Para selecionar outro item futuramente, envie #menu"

    # Azure key vault
    azure_vault_url: str = "https://nm-chatbot-keys.vault.azure.net/"

    # AzureCosmos
    cosmos_endpoint: str = "https://chatbot-nosql.documents.azure.com:443/"
    cosmos_key: str
    cosmos_database_name: str = "chatbot"
    cosmos_container_name: str = "chatHistory"
    cosmos_index_container_name: str = "chatIndexConfig"

    class Config:
        env_file = ".env"


settings = Settings()
