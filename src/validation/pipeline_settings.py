from pydantic import BaseSettings


class PipelineSettings(BaseSettings):
    """Chatbot Validation Pipeline settings

    This class is used to store the settings for the validation pipeline.
    """

    # Azure storage
    evalchatbot_storage_cs: str = ""
    evalchatbot_dataset_container: str = "datasets"
    evalchatbot_evaluation_container: str = "evaluations"

    # Pipeline Settings
    validation_data_dir = "validation/data"  # Path to store the data
    validation_log_dir = "validation/logs"  # Path to store the logs

    pipeline_name: str
    max_dataset_questions: int = -1  # -1 for all questions
    max_variant_questions: int = -1  # -1 for all questions

    # Chatbot Settings
    chatbot_model: str = "gpt-3.5-turbo-azure"
    disable_memory: bool = True
    disable_faq: bool = True
    use_nsx_sense: bool = False
    dev_mode: bool = False
    verbose: bool = False
    return_debug: bool = True

    database_path: str = "validation/config/database.jsonl"
    memory_path: str = "validation/config/memory.json"
    index_infos_path: str = "validation/config/index.jsonl"

    prompt_answerer_endpoint: str = "http://localhost:7000/api/openai/completions"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
