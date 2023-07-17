from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseSettings, HttpUrl

# Load environment variables from .env file
load_dotenv()


def get_version():
    """Get version from pyproject.toml

    NOTE:
        It's expected that the file is in the root of the project
        and this function is called from the src folder
    """
    # whatsappbot dir
    root_path = Path(__file__).parent.parent
    pyproject_path = root_path / "pyproject.toml"
    with pyproject_path.open("r", encoding="utf-8") as f:
        for line in f:
            if "version" in line:
                return line.split("=")[1].replace('"', "").strip()
    # If version is not found, return unknown
    return "unknown"


class Settings(BaseSettings):
    """Whatsapp Bot settings"""

    # Which environment this is running in ("prod", "staging", etc)
    environment: str

    token: str = ""
    base_url: HttpUrl = "https://nsx.ai"
    text_url: HttpUrl = "https://waba.360dialog.io/v1/messages"

    # Logging configurations:
    log_path: str = "logs/"

    # Prompt_answerer
    completion_endpoint: str = "http://localhost:7000/api/openai/completions"
    moderation_endpoint: str = "http://localhost:7000/api/openai/moderations"
    max_tokens_prompt: int = 4000

    # CORS
    # TODO: Change this to allow only the client's domain
    cors_origins = ["*"]

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
    # Features to use
    disable_faqs: bool = True
    disable_memory: bool = False
    use_sense: bool = True

    # IndexMenu
    menu_message = "Olá. Escolha um dos itens abaixo para iniciar a conversa."
    selection_message: str = "Selecione um item"
    request_menu_message: str = "Para selecionar outro item futuramente, envie #menu"

    # Domain
    default_index_domain = "documentos em minha base de dados"

    # Azure key vault
    azure_vault_url: str = "https://nm-chatbot-keys.vault.azure.net/"

    # Azure Account
    account_name = "stchatbotnm"
    azure_chatbot_access_key: str = None

    # AzureCosmos
    cosmos_endpoint: str = "https://chatbot-nosql.documents.azure.com:443/"
    cosmos_key: str = ""
    cosmos_database_name: str = "chatbot"
    cosmos_container_name: str = "chatHistory"
    cosmos_index_container_name: str = "chatIndexConfig"

    # Timeouts and retries
    max_retries: int = 3
    nsx_timeout: int = 30
    nsx_sense_timeout: int = 30
    reasoning_timeout: int = 30

    # NSX-Chatbot version
    # This variable is read in the class initialization
    version: str

    class Config:
        env_file = ".env"


settings = Settings(version=get_version())
