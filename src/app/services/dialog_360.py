import requests

from settings import settings


def post_360_dialog_text_message(destinatary: str, message: str):

    """Posts a text message to 360 dialog."""

    try:
        payload = {
            "to": destinatary,
            "type": "text",
            "text": {"body": message[:4096]},
        }
        requests.post(
            settings.text_url,
            json=payload,
            headers={
                "D360-Api-Key": settings.token,
                "Content-Type": "application/json",
            },
        )
    except Exception as e:

        raise e


def post_360_dialog_interative_message(
    destinatary: str, message: str, explanation_button_id: str
):

    """Posts a interative message to 360 dialog."""

    try:
        payload = {
            "to": destinatary,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": message[:4096]},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": explanation_button_id,
                                "title": "Referências",
                            },
                        }
                    ]
                },
            },
        }
        requests.post(
            settings.text_url,
            json=payload,
            headers={
                "D360-Api-Key": settings.token,
                "Content-Type": "application/json",
            },
        )

    except Exception as e:

        raise e
