import json
import traceback
from datetime import datetime
from typing import Union

from fastapi import APIRouter, BackgroundTasks, Request

from app.schemas.messages import WebhookMessage, WebhookStatus
from app.services.build_timed_logger import build_timed_logger
from app.services.dialog_360 import (
    post_360_dialog_error_message,
    post_360_dialog_intro_message,
    post_360_dialog_menu_message,
    post_360_dialog_text_message,
)
from settings import settings

router = APIRouter()

logger = build_timed_logger("webhook_logger", "webhook_log")
error_logger = build_timed_logger("error_logger", "error_log")


def process_request(request: Request, body: Union[WebhookMessage, WebhookStatus]):
    """Processes the webhook request."""

    # checks if the webhook is receiving a message:
    if isinstance(body, WebhookMessage):

        destinatary = body.messages[0]["from"]

        nm_number = request.headers["nm-number"]

        if body.messages[0]["type"] == "interactive":
            selected_index = body.messages[0]["interactive"]["list_reply"]["id"]
            request.app.state.memory.set_latest_user_index(
                destinatary, nm_number, selected_index
            )
            return

        message = body.messages[0]["text"]["body"]
        current_index = request.app.state.memory.get_latest_user_index(
            destinatary, nm_number
        )
        header_indexes = request.headers["indexes"]
        header_labels = request.headers["labels"]

        num_indexes = len(header_indexes.split("$"))
        if current_index is None and num_indexes == 1:
            request.app.state.memory.set_latest_user_index(
                destinatary, nm_number, header_indexes
            )
            current_index = header_indexes
        elif (
            message == settings.request_menu_message or current_index is None
        ) and num_indexes > 1:
            post_360_dialog_menu_message(
                destinatary, header_indexes, header_labels, nm_number
            )
            return

        try:
            # Send a message to the user to let them know the bot is processing their request:
            user_history = request.app.state.memory.retrieve_history(
                destinatary, nm_number, current_index
            )
            post_360_dialog_intro_message(
                destinatary, current_index, nm_number, user_history
            )

            answer = request.app.state.chatbot.get_response(
                message, destinatary, nm_number, current_index
            )
            post_360_dialog_text_message(destinatary, answer, nm_number)

        except Exception as e:
            post_360_dialog_error_message(destinatary, current_index, nm_number)
            error_logger.error(
                json.dumps(
                    {
                        "user_id": destinatary,
                        "user_message": message,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            )
            raise e

        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": destinatary,
                    "message": message,
                    "type": "NSX request at index " + current_index,
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
