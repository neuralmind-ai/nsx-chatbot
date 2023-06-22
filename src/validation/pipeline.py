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


class AnswerLog(BaseModel):
    index: str = Field(..., description="Index name")
    domain: str = Field(..., description="Index Domain description")
    tag: str = Field(..., description="Evaluation description tag")
    question: str = Field(..., description="Dataset Question")
    gold_answer: str = Field(..., description="Dataset Gold Answer")
    chatbot_answer: str = Field(..., description="Chatbot Answer")
    reasoning: str = Field(..., description="chatbot reasoning steps log")
    latency: float = Field(..., description="Latency in seconds")
    evaluation: str = Field(
        default="incorrect", description="Evaluation result (correct, incorrect)"
    )


class EvaluationConfig(BaseModel):
    tag: str = Field(..., description="Evaluation description tag")
    index: str = Field(..., description="Index name")
    domain: str = Field(..., description="Index Domain description")
    memory: bool = Field(..., description="Use Memory")
    faq: bool = Field(..., description="Use FAQ")
    sense: bool = Field(..., description="Use Sense")
    unique_questions: int = Field(..., description="Number of unique questions")
    question_variants: int = Field(..., description="Number of question variants")


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
    chatbot: ChatHandler,
    data_manager: EvalDataManager,
    params: EvaluationParams,
    settings: PipelineSettings,
) -> DatasetEvaluation:
    """Evaluate Chatbot answers for a Dataset

    Args:
        chatbot (ChatHandler): Chatbot handler
        data_manager (EvalDataManager): Data Manager for evaluation data
        params (EvaluationParams): Evaluation parameters
        settings (PipelineSettings): Pipeline settings

    Returns:
        DatasetEvaluation: Dataset evaluation
    """

    # Load dataset
    dataset = data_manager.get_dataset(local_path=params.dataset_path)

    # Max number of questions to evaluate
    max_questions = (
        params.max_dataset_questions
        if params.max_dataset_questions != -1
        else len(dataset.questions)
    )

    # Max number of variants of a question to evaluate
    max_variants = (
        params.max_variant_questions
        if params.max_variant_questions != -1
        else len(dataset.questions[0].variants)
    )

    # store the log of the evaluation for each question
    responses_log: List[AnswerLog] = []

    # Build chatbot answers for the dataset questions
    # Use rich.Progress to display progress bars for dataset and question variant
    responses = []
    with Progress() as progress:
        # Dataset Progress Bar
        dataset_task = progress.add_task(
            f"{dataset.index} dataset progress",
            total=max_questions,
        )

        for qi, question in enumerate(dataset.questions[:max_questions]):
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

                # Check if it is in debug mode to get the evaluation log
                if chatbot.return_debug:
                    try:
                        reasoning, chatbot_answer = chatbot_answer.split("Answer:")
                    except Exception:
                        reasoning = ""

                    responses_log.append(
                        AnswerLog(
                            index=params.index,
                            domain=params.domain,
                            tag=params.chat_id,
                            question=variant,
                            gold_answer=question.answer,
                            chatbot_answer=chatbot_answer.strip(),
                            reasoning=reasoning.strip(),
                            latency=answer_latency,
                        )
                    )

                variants.append(chatbot_answer.strip())
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

        # Update evaluation logs with the evaluation results
        # The results are stored in the same order as the answer_logs
        idx = 0
        for qa_evaluation in dataset_evaluation.qa_evaluations:
            for evaluation in qa_evaluation.evaluations:
                if evaluation:
                    responses_log[idx].evaluation = "correto"
                else:
                    responses_log[idx].evaluation = "incorreto"
                idx += 1

        # Save evaluation logs
        eval_log = EvaluationLog(
            eval_config=EvaluationConfig(
                tag=params.chat_id,
                index=params.index,
                domain=params.domain,
                memory=(not settings.disable_memory),
                faq=(not settings.disable_faq),
                sense=settings.use_nsx_sense,
                unique_questions=max_questions,
                question_variants=max_variants,
            ),
            log=responses_log,
        )

        with params.log_path.open("w") as f:
            json.dump(eval_log.dict(), f, ensure_ascii=False, indent=4)

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
        return_debug=settings.return_debug,
    )

    data_manager = EvalDataManager(settings=settings)

    # Create data dir
    data_dir = Path(settings.validation_data_dir, settings.pipeline_name)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create log dir
    log_dir = Path(settings.validation_log_dir, settings.pipeline_name)
    log_dir.mkdir(parents=True, exist_ok=True)

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
            domain=database.get_index_information(index, "domain"),
            chatbot_id=f"{index}_chat",
            chat_id=settings.pipeline_name,
            dataset_path=data_dir / f"{index}_dataset.json",
            evaluation_path=evaluations_path,
            responses_path=data_dir / f"{index}_answers.json",
            log_path=log_dir / f"{index}_log.json",
            pa_endpoint=settings.prompt_answerer_endpoint,
            max_dataset_questions=settings.max_dataset_questions,
            max_variant_questions=settings.max_variant_questions,
        )
        for index in indexes
    ]

    # Print Evaluation Settings
    print("Evaluation Settings:")
    print("Pipeline Name:", settings.pipeline_name)
    print("Chatbot Model:", settings.chatbot_model)
    print("Disable Memory:", settings.disable_memory)
    print("Disable FAQ:", settings.disable_faq)
    print("Use NSX Sense:", settings.use_nsx_sense)

    # Evaluate All the datasets (1-by-1)
    results = []
    for params in evaluations:
        evaluation = evaluate(
            chatbot=chatbot, data_manager=data_manager, params=params, settings=settings
        )
        if evaluation:
            print(
                f"Index: [green]{params.index}[/] - ACC: [red]{evaluation.metrics['accuracy']:.2f}[/]"
            )
            results.append(evaluation)

    # Upload the evaluation for the DataStore (Evaluation Container)
    data_manager.upload_evaluations(local_path=evaluations_path)

    # Show evaluation Summary in a table format (Index_name, Accuracy)
    summary = NevalSummary(results, dataset_labels=indexes)
    summary.show()
