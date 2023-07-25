from typing import List

from pydantic import BaseModel


class WebhookMessage(BaseModel):
    contacts: List[dict]
    messages: List[dict]


class WebhookStatus(BaseModel):
    statuses: List[dict]


class TextMessage(BaseModel):
    to: str
    type: str
    text: dict


# TODO remove user from this class:
# TODO get the user from the request header (authentication)
class ChatMessage(BaseModel):
    message: str
    user: str


class ChatAnswer(BaseModel):
    answer: str
