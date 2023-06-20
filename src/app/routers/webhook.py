import json
import traceback
from datetime import datetime
from typing import Union

from fastapi import APIRouter, BackgroundTasks, Request
from requests.exceptions import Timeout

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

        # checks if the message is a question:
        destinatary = body.messages[0]["from"]
        nm_number = request.headers["nm-number"]

        try:
            if not is_message_a_question(request, body, destinatary, nm_number):
                return
            current_index = request.app.state.memory.get_latest_user_index(
                destinatary, nm_number
            )
            message = body.messages[0]["text"]["body"]
            # Send a message to the user to let them know the bot is processing their request:
            user_history = request.app.state.memory.retrieve_history(
                destinatary, nm_number, current_index
            )
            post_360_dialog_intro_message(
                destinatary,
                current_index,
                nm_number,
                user_history,
                request.app.state.db,
            )

            answer = request.app.state.chatbot.get_response(
                message, destinatary, nm_number, current_index
            )
            post_360_dialog_text_message(destinatary, answer, nm_number)
        except ValueError as ve:
            current_index = ""
            message = body.messages[0]["text"]["body"]
            post_360_dialog_error_message(
                destinatary, current_index, nm_number, request.app.state.db
            )
            error_logger.error(
                json.dumps(
                    {
                        "user_id": destinatary,
                        "user_message": message,
                        "error": str(ve),
                        "traceback": traceback.format_exc(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    ensure_ascii=False,
                )
            )
            raise ve
        except Timeout as te:
            user_message = body.messages[0]["text"]["body"]
            timeout_message = "Parece que o servidor está demorando muito para responder. Por favor, tente novamente mais tarde."
            post_360_dialog_text_message(destinatary, timeout_message, nm_number)
            error_logger.error(
                json.dumps(
                    {
                        "user_id": destinatary,
                        "user_message": user_message,
                        "error": str(te),
                        "traceback": traceback.format_exc(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    ensure_ascii=False,
                )
            )
            raise te
        except Exception as e:
            current_index = request.app.state.memory.get_latest_user_index(
                destinatary, nm_number
            )
            message = body.messages[0]["text"]["body"]
            post_360_dialog_error_message(
                destinatary, current_index, nm_number, request.app.state.db
            )
            error_logger.error(
                json.dumps(
                    {
                        "user_id": destinatary,
                        "user_message": message,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    ensure_ascii=False,
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
                },
                ensure_ascii=False,
            )
        )


def is_message_a_question(
    request: Request,
    body: Union[WebhookMessage, WebhookStatus],
    destinatary: str,
    nm_number: str,
) -> bool:
    """
    Processes the message before sending it to the chatbot and checks if it is a question. If not, it performs the necessary actions.

    Returns:
        True: if the message is a question and should be sent to the chatbot,
        False: if the message is a menu request or if the user is choosing an index.
    """

    if body.messages[0]["type"] == "interactive":
        selected_index = body.messages[0]["interactive"]["list_reply"]["id"]
        request.app.state.memory.set_latest_user_index(
            destinatary, nm_number, selected_index
        )
        return False

    message = body.messages[0]["text"]["body"]
    current_index = request.app.state.memory.get_latest_user_index(
        destinatary, nm_number
    )
    header_indexes = request.headers["indexes"]
    header_labels = request.headers["labels"]
    menu_message = request.headers.get("menu-message", settings.menu_message)
    menu_button_message = request.headers.get("menu-button-message", None)
    request_menu_message = request.headers.get("request-menu-message", None)

    if menu_message is None:
        menu_message = settings.menu_message
    if request_menu_message is None:
        request_menu_message = settings.request_menu_message
        request_command = request_menu_message.split(" ")[-1]
    else:
        # The request_menu_message must be a string ending with #command
        request_command = request_menu_message.split(" ")[-1]
        if not request_command.startswith("#"):
            raise ValueError(
                "The request menu message must end with a command starting with #"
            )
    if menu_button_message is None:
        menu_button_message = settings.selection_message
    else:
        # 360 dialog does not allow button texts over 20 characters
        if len(menu_button_message) > 20:
            raise ValueError(
                "The menu button message can not be over 20 characters long"
            )

    num_indexes = len(header_indexes.split("$"))
    if current_index is None and num_indexes == 1:
        request.app.state.memory.set_latest_user_index(
            destinatary, nm_number, header_indexes
        )
        current_index = header_indexes
    elif (message == request_command or current_index is None) and num_indexes > 1:
        post_360_dialog_menu_message(
            destinatary,
            header_indexes,
            header_labels,
            menu_message,
            request_menu_message,
            menu_button_message,
            nm_number,
        )
        return False

    return True


@router.post("/webhook")
async def waba_webhook(
    request: Request,
    body: Union[WebhookMessage, WebhookStatus],
    background_tasks: BackgroundTasks,
) -> dict:

    """Webhook for handling messages to the NSX Whatsapp Bot."""
    background_tasks.add_task(process_request, request, body)

    return {"message": "OK"}
