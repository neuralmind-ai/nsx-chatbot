import requests
from requests.api import request

from typing import Union
import requests

from fastapi import APIRouter

from app.services.query import query
from app.schemas.messages import WebhookMessage, WebhookStatus, TextMessage

from settings import settings

router = APIRouter()


@router.post("/webhook")
async def waba_webhook(body: Union[WebhookMessage, WebhookStatus]):
    if isinstance(body, WebhookMessage):

        message = query(body.messages[0]["text"]["body"])
        payload = {
            "to": body.messages[0]["from"],
            "type": "text",
            "text": {"body": message[:4096]},
        }
        response = requests.post(
            settings.text_url,
            json=payload,
            headers={"D360-Api-Key": settings.token, "Content-Type": "application/json"},
        )
        print(response.json())
    else:
        print(body)

    return {"message": "OK"}
