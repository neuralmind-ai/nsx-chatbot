import json
from datetime import datetime
from typing import Union

from fastapi import APIRouter, BackgroundTasks, Request

from app.schemas.messages import WebhookMessage, WebhookStatus
from app.services.build_timed_logger import build_timed_logger
from app.services.dialog_360 import post_360_dialog_text_message
from settings import settings

router = APIRouter()

logger = build_timed_logger("webhook_logger", "whatsappbot_log")


def process_request(request: Request, body: Union[WebhookMessage, WebhookStatus]):
    """Processes the webhook request."""

    # checks if the webhook is receiving a message:
    if isinstance(body, WebhookMessage):

        destinatary = body.messages[0]["from"]

        message = body.messages[0]["text"]["body"]

        try:
            answer = request.app.state.chatbot.get_response(message, destinatary)
            post_360_dialog_text_message(destinatary, answer)

        except Exception as e:
            error_message = "Erro no processamento da mensagem. Tente novamente."
            post_360_dialog_text_message(destinatary, error_message)
            raise e

        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": destinatary,
                    "message": message,
                    "type": "NSX request at index " + settings.search_index,
                    "response": answer,
                }
            )
        )


@router.post("/webhook")
async def waba_webhook(
    request: Request,
    body: Union[WebhookMessage, WebhookStatus],
    background_tasks: BackgroundTasks,
) -> dict:

    """Webhook for handling messages to the NSX Whatsapp Bot."""
    background_tasks.add_task(process_request, request, body)

    return {"message": "OK"}
