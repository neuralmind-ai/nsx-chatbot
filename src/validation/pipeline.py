# Fix for import errors
import os
import sys

sys.path.append(os.getcwd())

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from azure.storage.blob import BlobServiceClient
from neval import Evaluator, NevalSummary
from neval.models import Dataset, DatasetEvaluation
from neval.qa import build_evaluation, gpt4_evaluator
from neval.tasks import CompletionsException, completions
from neval.utils import generate_uuid
from pydantic import BaseModel, Field
from rich import print, progress
from rich.progress import Progress, TaskID

from app.services.chat_handler import ChatHandler
from app.services.database import JSONLDBManager
from app.services.memory_handler import JSONMemoryHandler
from settings import settings as chatbot_settings
from validation.gsheet_utils import get_datasets_from_sheet, update_evaluation_sheet
from validation.log_to_table import to_table
from validation.pipeline_settings import PipelineSettings


def get_timestamp():
    """Get current timestamp"""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


class AnswerLog(BaseModel):
    evaluation_id: str = Field(..., description="Evaluation ID")
    timestamp: str = Field(..., description="Evaluation Timestamp")
    chatbot_version: str = Field(
        default=chatbot_settings.version, description="Chatbot Version"
    )
    # TODO: Get NSX Version using the NSX API when available
    nsx_version: str = Field(default="0.41.0", description="NSX Version")
    neval_version: str = Field(default=gpt4_evaluator.name, description="Neval Version")
    index: str = Field(..., description="Index Name")
    question: str = Field(..., description="Dataset Question")
    expected_answer: str = Field(..., description="Expected answer for the question")
    answer: str = Field(..., description="Chatbot Answer")
    evaluation: str = Field(..., description="Evaluation result (correct, incorrect)")
    reasoning: str = Field(..., description="Chatbot reasoning steps log")
    answered: bool = Field(..., description="Flag if question was answered")
    evaluated: bool = Field(..., description="Flag if question was evaluated")
    latency: float = Field(..., description="Latency in seconds")
    eval_prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    eval_completion_tokens: int = Field(
        ..., description="Number of tokens in the completion"
    )
    metadata: str = Field(..., description="Evaluation metadata")


class EvaluationConfig(BaseModel):
    id: str = Field(..., description="Evaluation ID")
    memory: bool = Field(..., description="Use Memory")
    faq: bool = Field(..., description="Use FAQ")
    sense: bool = Field(..., description="Use Sense")
    number_of_questions: int = Field(..., description="Number of questions")
    timestamp: str = Field(..., description="Evaluation Timestamp")
    chatbot_version: str = Field(
        default=chatbot_settings.version, description="Chatbot Version"
    )
    # TODO: Get NSX Version using the NSX API when available
    nsx_version: str = Field(default="0.41.0", description="NSX Version")
    # Evaluation Version is the name of the evaluator used
    neval_version: str = Field(default=gpt4_evaluator.name, description="Neval Version")
    metadata: str = Field(..., description="Evaluation metadata")


class EvaluationLog(BaseModel):
    eval_config: EvaluationConfig
    log: List[AnswerLog] = Field(..., description="List of answers")


class EvaluationParams(BaseModel):
    """Evaluation parameters

    This class is used to store the parameters for the evaluation pipeline.
    """

    index: str = Field(..., description="Index name")
    domain: str = Field(..., description="Index Domain description")
    chatbot_id: str = Field(..., description="Chatbot ID")
    chat_id: str = Field(..., description="Chat Session ID")
    dataset_path: Path = Field(..., description="Dataset path")
    evaluation_path: Path = Field(..., description="Evaluation path")
    responses_path: Path = Field(..., description="Responses path")
    log_path: Path = Field(..., description="Evaluation log path")
    pa_endpoint: str = Field(..., description="Prompt-answerer endpoint")
    max_dataset_questions: int = Field(
        ..., description="Max questions used from dataset"
    )
    max_variant_questions: int = Field(..., description="Max question variant used")


class EvalDataManager:
    """Class used to manage Chatbot Evaluation Data
    Data is stored in an Azure Blob Storage (ABS)

    Attributes:
     - _dataset_container_name (str): The name of the Container in the ABS
     that stores the Datasets used in the evaluation (each Dataset is a JSON file).
     - _evaluation_container_name (str): The name of the Container in the ABS
     which stores the DatasetEvaluation data from all datasets evaluated in the pipeline
     in JSONL format (each DatasetEvaluation is a JSON).
     - _blob_service_client (BlobServiceClient): the client of the ABS services.
     - _dataset_container (ContainerClient): The container client that handles
     communication with the ABS Dataset Container.
     - _evaluation_container (ContainerClient): The container client that handles
     communication with the ABS Evaluation Container.

    """

    def __init__(self, settings: PipelineSettings) -> None:
        self._dataset_container_name = settings.evalchatbot_dataset_container
        self._evaluation_container_name = settings.evalchatbot_evaluation_container
        self._blob_service_client = BlobServiceClient.from_connection_string(
            settings.evalchatbot_storage_cs
        )
        self._dataset_container = self._blob_service_client.get_container_client(
            container=self._dataset_container_name
        )
        self._evaluation_container = self._blob_service_client.get_container_client(
            container=self._evaluation_container_name
        )

    def list_datasets(self, datasets_path: Path) -> List[str]:
        """Returns a list of all datasets available in the Container"""
        dataset_indexes = []
        for dataset_path in datasets_path.iterdir():
            if dataset_path.exists():
                dataset_indexes.append(dataset_path.name)

        if len(dataset_indexes) > 0:
            return sorted(dataset_indexes)

        return [
            dataset_name for dataset_name in self._dataset_container.list_blob_names()
        ]

    def get_dataset(self, local_path: Path, dataset_name: str = None) -> Dataset:
        """Returns a Dataset object of the Data Store

        Args:
            - local_path: local path to store de dataset file
            - dataset_name: The name of the dataset (can use the name of the local file)
        """

        blob_name = local_path.name or dataset_name

        if not local_path.exists():
            with local_path.open("wb") as file:
                try:
                    file.write(
                        self._dataset_container.download_blob(blob=blob_name).readall()
                    )
                except Exception as e:
                    print(e)
                    return None

        with local_path.open("r") as file:
            try:
                dataset = Dataset(**json.load(file))
            except Exception as e:
                print(e)
                return None

        return dataset

    def save_evaluation(
        self, evaluation: DatasetEvaluation, dataset_name: str, local_path: Path
    ):
        """Save the Dataset Evaluation in the local storage

        Args:
         - evaluation: The Dataset Evaluation
         - local_path: local path to store the evaluation
        """

        with local_path.open("w", encoding="utf-8") as file:
            eval_dict = evaluation.dict()
            eval = {dataset_name: eval_dict}
            json.dump(eval, file, ensure_ascii=False)

    def upload_evaluations(self, local_path: Path, evaluation_name=None):
        """Upload the local stored evaluations to DataStore

        Args:
            - local_path: local path to load de evaluaions file
            - evaluation_name: The name of the dataset (can use the name of the local file)
        """

        blob_name = local_path.name or evaluation_name

        with local_path.open("rb") as file:
            try:
                blob_client = self._evaluation_container.get_blob_client(blob=blob_name)
                blob_client.upload_blob(data=file)
            except Exception as e:
                print("Error uploading evaluations.")
                print(e)


def evaluate(
    eval_content: str, evaluator: Evaluator, endpoint: str
) -> Tuple[str, Dict[str, int]]:
    """Evaluate the chatbot answer for a question"""

    messages = [
        {"role": "system", "content": evaluator.prompt.system},
        {"role": "user", "content": eval_content},
    ]

    payload = {
        "service": "NeuralEvaluation",
        "prompt": messages,
        "model": evaluator.model,
        "configurations": evaluator.settings,
    }

    response = completions(payload, endpoint)
    grade = response["text"].split(":")[1].strip()
    tokens_usage = response["tokens_usage"]
    return grade, tokens_usage


def eval_task(
    question_data: dict,
    chatbot: ChatHandler,
    evaluator: Evaluator,
    settings: PipelineSettings,
    progress: Progress,
    task_id: TaskID,
) -> dict:
    """Evaluate the chatbot answer for a question

    Parameters:
        question_data (dict): Question data
        chatbot (ChatHandler): Chatbot handler
        evaluator (Evaluator): Evaluator handler
        settings (PipelineSettings): Pipeline settings
    Returns:
        dict: Question evaluation
    """

    answer_latency = time.time()
    answered = False
    evaluated = False
    eval_prompt_tokens = 0
    eval_completion_tokens = 0

    try:
        chatbot_answer = chatbot.get_response(
            user_message=question_data["question"],
            user_id=question_data["id"],
            chatbot_id=f"{question_data['index']}_chat",
            index=question_data["index"],
            bm25_only=settings.bm25_only,
        )
        reasoning, chatbot_answer = chatbot_answer.split("Answer:")
        answered = True

    except Exception as e:
        print(f"Error getting chatbot answer: {e}, Type: {type(e)}")
        reasoning = "Indisponível"
        chatbot_answer = "Erro ao obter a resposta para a pergunta."

    answer_latency = time.time() - answer_latency

    if answered:
        try:

            eval_content = evaluator.prompt.template.format(
                question=question_data["question"],
                answer=chatbot_answer.strip(),
                groundtruth=question_data["gold_answer"],
            ).strip()

            evaluation, tokens_usage = evaluate(
                eval_content, evaluator, settings.prompt_answerer_endpoint
            )

            eval_prompt_tokens = tokens_usage["prompt_tokens"]
            eval_completion_tokens = tokens_usage["completion_tokens"]
            evaluated = True

        except CompletionsException as e:
            print(f"Error evaluating chatbot answer: {e}, Type: {type(e)}")
            evaluation = "not evaluated"

        except Exception as e:
            print(f"Unexpected error evaluating chatbot answer: {e}, Type: {type(e)}")
            evaluation = "not evaluated"

    question_data.update(
        {
            "chatbot_answer": chatbot_answer.strip(),
            "evaluation": evaluation,
            "reasoning": reasoning.strip(),
            "latency": answer_latency,
            "answered": answered,
            "evaluated": evaluated,
            "eval_prompt_tokens": eval_prompt_tokens,
            "eval_completion_tokens": eval_completion_tokens,
        }
    )

    progress.update(task_id, advance=1)

    return question_data


def create_eval_metadata(settings: PipelineSettings) -> str:
    """Create a id for the evaluation"""

    def get_git_cmd_response(cmd_args: List[str]) -> str:
        return subprocess.check_output(cmd_args).decode("ascii").strip()

    def get_activated_features(settings: PipelineSettings) -> str:
        features = ""
        if not settings.disable_memory:
            features += "memory,"
        if not settings.disable_faq:
            features += "faq,"
        if settings.bm25_only:
            features += "bm25-only,"
        if settings.use_nsx_sense:
            features += "sense"
        else:
            features += "nsx"
        return features

    commit_hash = get_git_cmd_response(["git", "rev-parse", "--short", "HEAD"])
    branch_name = get_git_cmd_response(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    activated_features = get_activated_features(settings)

    eval_metadata = (
        f"ACTIVATED:{activated_features}"
        f"_BRANCH:{branch_name.replace('/', '-')}"
        f"_COMMIT:{commit_hash}"
    )

    return eval_metadata


if __name__ == "__main__":

    settings = PipelineSettings()
    eval_timestamp = get_timestamp()
    # Create a id  for the evaluation with the prefix "evl-" + 12 random characters
    eval_id = generate_uuid(prefix="evl")[:16]
    eval_metadata = create_eval_metadata(settings)

    # Print Evaluation Settings
    print("Evaluation Settings:")
    print("Pipeline Name:", settings.pipeline_name)
    print("Evaluation ID:", eval_id)
    print("Evaluation Timestamp:", eval_timestamp)
    print("Evaluation Metadata:", eval_metadata)
    print("Chatbot Model:", settings.chatbot_model)
    print("Disable Memory:", settings.disable_memory)
    print("Disable FAQ:", settings.disable_faq)
    print("Use NSX Sense:", settings.use_nsx_sense)
    print("BM25 Only:", settings.bm25_only)

    database = JSONLDBManager(
        chat_history_path=settings.database_path,
        index_infos_path=settings.index_infos_path,
    )

    memory = JSONMemoryHandler(path=settings.memory_path)

    chatbot = ChatHandler(
        db=database,
        memory=memory,
        model=settings.chatbot_model,
        disable_memory=settings.disable_memory,
        disable_faq=settings.disable_faq,
        use_nsx_sense=settings.use_nsx_sense,
        dev_mode=settings.dev_mode,
        verbose=settings.verbose,
        return_debug=True,
    )

    data_manager = EvalDataManager(settings=settings)

    # Create data dir
    data_dir = Path(settings.validation_data_dir, settings.pipeline_name)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create log dir
    log_dir = Path(settings.validation_log_dir, settings.pipeline_name)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{eval_id}_log.json"

    # Create dataset dir
    dataset_dir = Path(data_dir, "datasets")
    dataset_dir.mkdir(parents=True, exist_ok=True)

    evaluations_path = data_dir / f"{eval_id}_evaluations.jsonl"

    # Download the datasets from Google Sheets if its is possible
    if settings.google_oauth2_token:
        get_datasets_from_sheet(
            token=settings.google_oauth2_token,
            spreadsheet_id=settings.dataset_spreadsheet_id,
            range_name=settings.dataset_sheet_name,
            datasets_dir=dataset_dir,
        )

    # Get the paths of the datasets
    dataset_paths = [
        dataset_dir / dataset for dataset in data_manager.list_datasets(dataset_dir)
    ]

    datasets = [
        data_manager.get_dataset(local_path=dataset_path)
        for dataset_path in dataset_paths
    ]

    # Filter the datasets to evaluate by the indexes if it is defined
    if len(settings.evaluation_indexes) > 0:
        datasets = [
            dataset
            for dataset in datasets
            if dataset.index in settings.evaluation_indexes
        ]

    # Map the dataset indexes to the new indexes if it is defined
    if len(settings.index_mapping) > 0:
        for dataset in datasets:
            # Get the new index name if it is defined or keep the original index name
            index = settings.index_mapping.get(dataset.index, dataset.index)
            dataset.index = index

    # Get the indexes of the datasets to later identify the evaluation results
    indexes = [dataset.index for dataset in datasets]

    question_pool = []

    for dataset in datasets:
        # Max number of questions to evaluate
        max_questions = (
            settings.max_dataset_questions
            if settings.max_dataset_questions != -1
            else len(dataset.questions)
        )

        # Max number of variants of a question to evaluate
        max_variants = (
            settings.max_variant_questions
            if settings.max_variant_questions != -1
            else len(dataset.questions[0].variants)
        )

        question_pool.extend(
            [
                {
                    "vqid": f"{question.id}_{vidx}",
                    "qid": question.id,
                    "index": dataset.index,
                    "id": eval_id,
                    "question": variant,
                    "gold_answer": question.answer,
                }
                for question in dataset.questions[:max_questions]
                for vidx, variant in enumerate(question.variants[:max_variants])
            ]
        )

    with Progress(
        progress.TextColumn("[progress.description]{task.description}"),
        progress.BarColumn(),
        progress.MofNCompleteColumn(),
        progress.TaskProgressColumn(),
        progress.TimeRemainingColumn(),
        progress.TimeElapsedColumn(),
    ) as progress:

        overall_progress_task = progress.add_task(
            "[green]Evaluation progress:", total=len(question_pool)
        )

        with ThreadPoolExecutor(
            max_workers=settings.max_concurrent_questions
        ) as executor:

            evaluated_questions = list(
                executor.map(
                    lambda question_data: eval_task(
                        question_data=question_data,
                        chatbot=chatbot,
                        evaluator=gpt4_evaluator,
                        settings=settings,
                        progress=progress,
                        task_id=overall_progress_task,
                    ),
                    question_pool,
                )
            )

    # Log the evaluation results
    answers_log = [
        AnswerLog(
            evaluation_id=eval_id,
            timestamp=eval_timestamp,
            index=question_data["index"],
            question=question_data["question"],
            expected_answer=question_data["gold_answer"],
            answer=question_data["chatbot_answer"],
            evaluation=question_data["evaluation"],
            reasoning=question_data["reasoning"],
            answered=question_data["answered"],
            evaluated=question_data["evaluated"],
            latency=question_data["latency"],
            eval_prompt_tokens=question_data["eval_prompt_tokens"],
            eval_completion_tokens=question_data["eval_completion_tokens"],
            metadata=eval_metadata,
        )
        for question_data in evaluated_questions
    ]

    eval_log = EvaluationLog(
        eval_config=EvaluationConfig(
            id=eval_id,
            memory=(not settings.disable_memory),
            faq=(not settings.disable_faq),
            sense=settings.use_nsx_sense,
            number_of_questions=len(evaluated_questions),
            timestamp=eval_timestamp,
            metadata=eval_metadata,
        ),
        log=answers_log,
    )

    with log_path.open("w") as f:
        json.dump(eval_log.dict(), f, ensure_ascii=False, indent=4)

    # parse the evaluation log to a csv table
    eval_table_file = to_table(log_path)

    # Update the evaluation google sheet with the evaluation results
    update_evaluation_sheet(
        token=settings.google_oauth2_token,
        spreadsheet_id=settings.spreadsheet_id,
        range_name=settings.raw_sheet_name,
        table_file=eval_table_file,
    )

    # Upload the evaluation log to the DataStore (Evaluation Container)
    data_manager.upload_evaluations(local_path=log_path)

    all_evaluations_df = pd.DataFrame(evaluated_questions)

    evaluation_results = []

    for index, dataset in zip(indexes, datasets):
        dataset_evaluations_df = all_evaluations_df.query(
            f"index == '{index}' & evaluated == True"
        )
        evaluation_results.append(
            build_evaluation(dataset_evaluations_df, gpt4_evaluator, dataset)
        )

    with evaluations_path.open("w", encoding="utf-8") as f:
        for evaluation in evaluation_results:
            eval_dict = evaluation.dict()
            eval = {evaluation.index: eval_dict}
            f.write(json.dumps(eval, ensure_ascii=False) + "\n")

    # Upload the evaluation for the DataStore (Evaluation Container)
    data_manager.upload_evaluations(local_path=evaluations_path)

    # Show evaluation Summary in a table format (Index_name, Accuracy)
    summary = NevalSummary(evaluation_results, dataset_labels=indexes)
    summary.show()
