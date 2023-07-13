import json
from datetime import datetime
from typing import List

import requests
import tiktoken

from app.services.azure_table_storage import AzureTableLoggerHandler
from app.services.build_timed_logger import build_timed_logger
from app.utils.exceptions import PromptAnswererError
from app.utils.timeout_management import RequestMethod, retry_request_with_timeout
from settings import settings

chat_logger = build_timed_logger("chat_logger", "chat.log")
error_logger = build_timed_logger("error_logger", "error.log")
harmful_logger = build_timed_logger("harmful_logger", "harmful.log")
latency_logger = build_timed_logger("latency_logger", "latency.log")

chatlog_table = AzureTableLoggerHandler("chatbotlogs")
chat_logger.addHandler(chatlog_table)

error_table = AzureTableLoggerHandler("chatboterrors")
error_logger.addHandler(error_table)

harmful_table = AzureTableLoggerHandler("chatbotharmful")
harmful_logger.addHandler(harmful_table)

latency_table = AzureTableLoggerHandler("chatbotlatency")
latency_logger.addHandler(latency_table)


def get_num_tokens(text: str) -> int:
    """
    Returns the number of tokens in the text.
    """
    encoding = tiktoken.encoding_for_model(settings.encoding_model)
    return len(encoding.encode(text))


def get_reasoning(prompt: str, model, stop: List[str] = None) -> str:
    """
    Sends a request to prompt_answerer to get a reasoning.

    Args:
        - prompt: the prompt to be sent to prompt_answerer.
        - stop: the stop tokens list.

    Returns:
        - the reasoning for the message (str).
    """
    if stop is None:
        stop = ["\n"]
    # Returns the reasoning for the message
    body = {
        "service": "ChatBot",
        "prompt": [{"role": "user", "content": prompt}],
        "model": model,
        "configurations": {
            "temperature": 0,
            "max_tokens": 512,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "stop": stop,
        },
    }
    try:
        response = retry_request_with_timeout(
            RequestMethod.POST,
            settings.completion_endpoint,
            body=body,
            request_timeout=settings.reasoning_timeout,
        )
        if not response.ok:
            print("ERROR:", response.content)
            error_logger.error(
                json.dumps(
                    {
                        "prompt": prompt,
                        "stop": stop,
                        "status_code": response.status_code,
                        "service": "prompt_answerer",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    ensure_ascii=False,
                )
            )
            raise PromptAnswererError("Error in reasoning. Prompt Answerer is down.")
        return response.json()["text"].strip()
    except requests.exceptions.Timeout as te:
        raise te
    except requests.exceptions.ConnectionError as ce:
        raise PromptAnswererError(f"Prompt Answerer is down. Error: {ce}")
    except PromptAnswererError as pe:
        raise pe
    except Exception as e:
        raise e
