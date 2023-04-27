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
