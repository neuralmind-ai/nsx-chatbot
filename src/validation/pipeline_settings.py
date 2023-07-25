from typing import Union

from pydantic import BaseModel, BaseSettings


class GoogleCredentialsToken(BaseModel):
    """Google Credentials Token

    This class is used to store the google credentials token.
    """

    token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: list
    expiry: str


class PipelineSettings(BaseSettings):
    """Chatbot Validation Pipeline settings

    This class is used to store the settings for the validation pipeline.
    """

    # Azure storage
    evalchatbot_storage_cs: str = ""
    evalchatbot_dataset_container: str = "datasets"
    evalchatbot_evaluation_container: str = "evaluations"

    # Google Sheets settings
    spreadsheet_id: str = ""
    raw_sheet_name: str = "raw"
    dataset_spreadsheet_id: str = ""
    dataset_sheet_name: str = "dataset ouro"
    google_oauth2_token: Union[GoogleCredentialsToken, None] = None

    # Pipeline Settings
    validation_data_dir = "validation/data"  # Path to store the data
    validation_log_dir = "validation/logs"  # Path to store the logs

    pipeline_name: str = "evaluation_pipeline"
    max_dataset_questions: int = -1  # -1 for all questions
    max_variant_questions: int = -1  # -1 for all questions

    # Special evaluation settings
    evaluation_indexes: list = []
    index_mapping: dict = {}

    # Concurrency settings
    max_concurrent_questions: int = 4

    # Chatbot Settings
    chatbot_model: str = "gpt-3.5-turbo-azure"
    disable_memory: bool = True
    disable_faq: bool = True
    use_nsx_sense: bool = False
    dev_mode: bool = False
    verbose: bool = False
    return_debug: bool = True
    bm25_only: bool = False

    database_path: str = "validation/config/database.jsonl"
    memory_path: str = "validation/config/memory.json"
    index_infos_path: str = "validation/config/index.jsonl"

    prompt_answerer_endpoint: str = "http://localhost:7000/api/openai/completions"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
