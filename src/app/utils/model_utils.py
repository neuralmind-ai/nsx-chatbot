import json
from datetime import datetime
from typing import List

import requests
import tiktoken

from app.services.azure_table_storage import AzureTableLoggerHandler
from app.services.build_timed_logger import build_timed_logger
from app.utils.exceptions import ContentFilterError, PromptAnswererError
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


def check_content_filtering(response: dict) -> bool:
    """
    Checks if the response was filtered by the content filter.
    returns True if it was, False otherwise.
    """
    finish_reason = response.get("finish_reason", None)
    return finish_reason == "content_filter"


def log_content_filtering(response: dict, user_id: str, user_message: str, prompt: str):
    """
    Logs the content filtering.
    """

    def find_reason(results: dict):
        for result in results:
            if results[result]["filtered"]:
                return result, results[result]["severity"]
        return None, None

    content_filter_results = response.get("content_filter_results", None)
    reason = "The message was filtered by content filter but the reason could not be determined"

    if content_filter_results:
        prompt_results = content_filter_results.get("prompt") or {}
        completion_results = content_filter_results.get("completion") or {}
        prompt_reason, prompt_severity = find_reason(prompt_results)
        completion_reason, completion_severity = find_reason(completion_results)
        if prompt_reason:
            reason = f"The prompt was filtered by {prompt_reason} content with severity {prompt_severity}"
        elif completion_reason:
            reason = f"The completion was filtered by {completion_reason} content with severity {completion_severity}"

    harmful_logger.info(
        json.dumps(
            {
                "user_id": user_id,
                "user_message": user_message,
                "prompt": prompt,
                "reason": reason,
            },
            ensure_ascii=False,
        )
    )

    return reason


def get_reasoning(
    prompt: str, model, stop: List[str] = None, max_tokens=512, **kwargs
) -> str:
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
            "max_tokens": max_tokens,
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
        response.raise_for_status()
        response = response.json()
        if check_content_filtering(response):
            user_id = kwargs.get("user_id")
            user_message = kwargs.get("user_message")
            reason = log_content_filtering(response, user_id, user_message, prompt)
            raise ContentFilterError(reason)
        return response["text"].strip()
    except requests.exceptions.HTTPError as he:
        error_logger.error(
            json.dumps(
                {
                    "prompt": prompt,
                    "stop": stop,
                    "status_code": he.response.status_code,
                    "service": "prompt_answerer",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
                ensure_ascii=False,
            )
        )
        raise PromptAnswererError(
            f"Prompt Answerer is down. Error: {he.response.json()}"
        )
    except requests.exceptions.Timeout as te:
        raise te
    except requests.exceptions.ConnectionError as ce:
        raise PromptAnswererError(f"Prompt Answerer is down. Error: {ce}")
    except Exception as e:
        raise e
