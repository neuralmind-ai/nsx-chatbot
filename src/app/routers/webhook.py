import json
import logging
from datetime import datetime
from typing import Union

from fastapi import APIRouter, BackgroundTasks, Request
from requests.exceptions import Timeout

from app.schemas.messages import WebhookMessage, WebhookStatus
from app.services.build_timed_logger import build_timed_logger
from app.services.dialog_360 import (
    post_360_dialog_disclaimer_message,
    post_360_dialog_error_message,
    post_360_dialog_intro_message,
    post_360_dialog_menu_message,
    post_360_dialog_text_message,
)
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import ChatbotException, DialogConfigError, WebhookError
from app.utils.log_templates import log_error
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
        message = body.messages[0]["text"]["body"] if "text" in body.messages[0] else ""

        try:
            if not is_message_a_question(request, body, destinatary, nm_number):
                return
            current_index = request.app.state.memory.get_latest_user_index(
                destinatary, nm_number
            )
            # Send a message introducing the chatbot if it's the first message from the user
            if (
                request.app.state.memory.check_intro_message_sent(
                    destinatary, nm_number, current_index
                )
                is False
            ):
                post_360_dialog_intro_message(
                    destinatary,
                    current_index,
                    nm_number,
                    request.app.state.db,
                )
                request.app.state.memory.set_intro_message_sent(
                    destinatary, nm_number, current_index
                )
            # Send a message saying that the chatbot is processing the user's question
            post_360_dialog_text_message(
                destinatary,
                settings.wait_message,
                nm_number,
            )

            # Check if the user is in the verbose mode: (whatsapp only)
            whatsapp_verbose = request.app.state.memory.get_user_config(
                user=destinatary, chatbot_id=nm_number, config="whatsapp_verbose"
            )

            if not whatsapp_verbose:
                whatsapp_verbose = False

            api_key = request.headers.get("api-key", settings.api_key)

            answer = request.app.state.chatbot.get_response(
                message,
                destinatary,
                nm_number,
                current_index,
                api_key,
                whatsapp_verbose=whatsapp_verbose,
            )
            post_360_dialog_text_message(destinatary, answer, nm_number)
            # Send a disclaimer message if the user has not seen it yet
            if (
                request.app.state.memory.check_disclaimer_sent(
                    destinatary, nm_number, current_index
                )
                is False
            ):
                post_360_dialog_disclaimer_message(
                    destinatary, nm_number, current_index, request.app.state.db
                )
                request.app.state.memory.set_disclaimer_sent(
                    destinatary, nm_number, current_index
                )

        except ChatbotException as ce:
            handle_exception(
                destinatary, nm_number, message, ce, ce.error_code.value, error_logger
            )
        except Timeout as te:
            handle_exception(
                destinatary,
                nm_number,
                message,
                te,
                ErrorCodes.TIMEOUT.value,
                error_logger,
            )
        except Exception as e:
            handle_exception(
                destinatary,
                nm_number,
                message,
                e,
                ErrorCodes.GENERIC.value,
                error_logger,
            )

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
    try:
        if body.messages[0]["type"] == "interactive":
            # The user selected a index from the menu:
            selected_index = body.messages[0]["interactive"]["list_reply"]["id"]
            request.app.state.memory.set_latest_user_index(
                destinatary, nm_number, selected_index
            )
            # Send intro message:
            post_360_dialog_intro_message(
                destinatary,
                selected_index,
                nm_number,
                request.app.state.db,
            )
            request.app.state.memory.set_intro_message_sent(
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
                raise DialogConfigError(
                    "The request menu message must end with a command starting with #"
                )
        if menu_button_message is None:
            menu_button_message = settings.selection_message
        else:
            # 360 dialog does not allow button texts over 20 characters
            if len(menu_button_message) > 20:
                raise DialogConfigError(
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
    except DialogConfigError as de:
        raise de
    except Exception as e:
        raise WebhookError(e)


def handle_exception(
    destinatary: str,
    nm_number: str,
    message: str,
    error: Exception,
    error_code: int,
    error_logger: logging.Logger,
):
    """
    Handles exceptions raised by the chatbot by sending the appropriate message to the user, and logging the error.
    """
    post_360_dialog_error_message(destinatary, nm_number, error_code)
    log_error(error_logger, destinatary, nm_number, message, error)
    raise error


@router.post("/webhook")
async def waba_webhook(
    request: Request,
    body: Union[WebhookMessage, WebhookStatus],
    background_tasks: BackgroundTasks,
) -> dict:

    """Webhook for handling messages to the NSX Whatsapp Bot."""
    background_tasks.add_task(process_request, request, body)

    return {"message": "OK"}
