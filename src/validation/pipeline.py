# Fix for import errors
import os
import sys

sys.path.append(os.getcwd())

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List

from azure.storage.blob import BlobServiceClient
from neval import NevalSummary
from neval.models import Answer, Dataset, DatasetEvaluation
from neval.qa import QAValidator
from pydantic import BaseModel, Field
from rich import print
from rich.progress import Progress

from app.services.chat_handler import ChatHandler
from app.services.database import JSONLDBManager
from app.services.memory_handler import JSONMemoryHandler
from validation.pipeline_settings import PipelineSettings


class EvaluationParams(BaseModel):
    """Evaluation parameters

    This class is used to store the parameters for the evaluation pipeline.
    """

    index: str = Field(..., description="Index name")
    chatbot_id: str = Field(..., description="Chatbot ID")
    chat_id: str = Field(..., description="Chat Session ID")
    dataset_path: Path = Field(..., description="Dataset path")
    evaluation_path: Path = Field(..., description="Evaluation path")
    responses_path: Path = Field(..., description="Responses path")
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

    def list_datasets(self) -> List[str]:
        """Returns a list of all datasets available in the Container"""
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

        with local_path.open("a") as file:
            eval_dict = evaluation.dict()
            eval = {dataset_name: eval_dict}
            eval_json = json.dumps(eval, ensure_ascii=False)
            file.write(eval_json + "\n")

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
    chatbot: ChatHandler, data_manager: EvalDataManager, params: EvaluationParams
) -> DatasetEvaluation:
    """Evaluate Chatbot answers for a Dataset

    Args:
        chatbot (ChatHandler): Chatbot handler
        data_manager (EvalDataManager): Data Manager for evaluation data
        params (EvaluationParams): Evaluation parameters

    Returns:
        DatasetEvaluation: Dataset evaluation
    """

    # Load dataset
    dataset = data_manager.get_dataset(local_path=params.dataset_path)

    # Build chatbot answers for the dataset questions
    # Use rich.Progress to display progress bars for dataset and question variant
    responses = []
    with Progress() as progress:
        # Max number of questions to evaluate
        max_questions = (
            params.max_dataset_questions
            if params.max_dataset_questions != -1
            else len(dataset.questions)
        )
        # Dataset Progress Bar
        dataset_task = progress.add_task(
            f"{dataset.index} dataset progress",
            total=max_questions,
        )

        for qi, question in enumerate(dataset.questions[:max_questions]):
            # Max number of variants of a question to evaluate
            max_variants = (
                params.max_variant_questions
                if params.max_variant_questions != -1
                else len(question.variants)
            )
            # Question variants progress bar
            variants_task = progress.add_task(
                f"Variants of question {qi}",
                total=max_variants,
            )

            # Get chatbot answers to variant questions
            variants = []
            variants_latencies = []
            for variant in question.variants[:max_variants]:
                answer_start = time.time()
                try:
                    chatbot_answer = chatbot.get_response(
                        user_message=variant,
                        user_id=params.chat_id,
                        chatbot_id=params.chatbot_id,
                        index=params.index,
                    )
                except Exception:
                    chatbot_answer = (
                        f"Erro ao obter a resposta para a pergunta: {variant}."
                    )
                answer_latency = time.time() - answer_start
                variants_latencies.append(answer_latency)

                variants.append(chatbot_answer)
                progress.advance(variants_task)

            responses.append(
                Answer(
                    creator=params.chat_id,
                    question=question.id,
                    index=params.index,
                    variants=variants,
                    metadata={"latencies": variants_latencies},
                )
            )

            progress.remove_task(variants_task)
            progress.advance(dataset_task)

    # Save Chatbot answers
    with params.responses_path.open("w") as f:
        json.dump(
            [response.dict() for response in responses], f, ensure_ascii=False, indent=4
        )

    try:
        validator = QAValidator(endpoint=params.pa_endpoint)
        dataset_evaluation = validator.validate(dataset, responses)

        # Save evaluation locally
        data_manager.save_evaluation(
            evaluation=dataset_evaluation,
            dataset_name=params.index,
            local_path=params.evaluation_path,
        )

        return dataset_evaluation

    except Exception as e:
        print(e)
        return None  # type: ignore


if __name__ == "__main__":

    settings = PipelineSettings()

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
    )

    data_manager = EvalDataManager(settings=settings)

    # Create data dir
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    evaluations_path = (
        data_dir
        / f"{settings.pipeline_name}_evaluations_{datetime.utcnow().strftime('%m-%d-%Y-%H-%M-%S')}.jsonl"
    )

    # Get the dataset indexes (TODO: get them in a better way)
    indexes = [
        dataset.split("_dataset.json")[0] for dataset in data_manager.list_datasets()
    ]

    # Create pipeline settings for all datasets in the evaluation
    evaluations = [
        EvaluationParams(
            index=index,
            chatbot_id=f"{index}_chat",
            chat_id=settings.pipeline_name,
            dataset_path=data_dir / f"{index}_dataset.json",
            evaluation_path=evaluations_path,
            responses_path=data_dir / f"{index}_answers.json",
            pa_endpoint=settings.prompt_answerer_endpoint,
            max_dataset_questions=settings.max_dataset_questions,
            max_variant_questions=settings.max_variant_questions,
        )
        for index in indexes
    ]

    # Evaluate All the datasets (1-by-1)
    results = []
    for params in evaluations:
        evaluation = evaluate(chatbot=chatbot, data_manager=data_manager, params=params)
        if evaluation:
            results.append(evaluation)

    # Upload the evaluation for the DataStore (Evaluation Container)
    data_manager.upload_evaluations(local_path=evaluations_path)

    # Show evaluation Summary in a table format (Index_name, Accuracy)
    summary = NevalSummary(results, dataset_labels=indexes)
    summary.show()
