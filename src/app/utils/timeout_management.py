from enum import Enum

import requests

from settings import settings


class RequestMethod(str, Enum):
    GET = "GET"
    POST = "POST"


def retry_request_with_timeout(
    request_method: str,
    request_url: str,
    headers: str = None,
    params: str = None,
    body: dict = None,
    request_timeout: int = 5,
) -> requests.Response:
    """
    Makes a request with a timeout. In case of timeout, tries again until the max number of retries is reached.
    """
    for attempts in range(settings.max_retries):
        try:
            if request_method == RequestMethod.GET:
                response = requests.get(
                    request_url,
                    headers=headers,
                    params=params,
                    timeout=request_timeout,
                )
                return response
            elif request_method == RequestMethod.POST:
                response = requests.post(
                    request_url, json=body, timeout=request_timeout
                )
                return response
            else:
                raise ValueError(
                    "Invalid HTTP method. Only 'GET' and 'POST' are supported."
                )
        except requests.exceptions.Timeout as te:
            if attempts == settings.max_retries - 1:
                raise te
            continue
        except Exception as e:
            raise e
