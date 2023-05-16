import requests

from app.services.azure_vault import read_secret
from settings import settings


def post_360_dialog_text_message(destinatary: str, message: str, d360_number: str):
    """Posts a text message to 360 dialog."""
    token = read_secret(d360_number)
    payload = {
        "to": destinatary,
        "type": "text",
        "text": {"body": message[:4096]},
    }
    requests.post(
        settings.text_url,
        json=payload,
        headers={
            "D360-Api-Key": token,
            "Content-Type": "application/json",
        },
    )


def post_360_dialog_menu_message(
    destinatary: str, header_indexes: list, header_labels: list, d360_number: str
):

    """
    Send a menu to the user, so they can select an index.
    Args:
        destinatary (str): The destinatary's phone number.
        indexes (list): A string with the indexes names, separated by a $.
        labels (list): A string with the labels names, separated by a $.
    """
    token = read_secret(d360_number)
    indexes = []
    labels = []
    for index, label in zip(header_indexes.split("$"), header_labels.split("$")):
        indexes.append(index.strip())
        labels.append(label.strip())

    rows = []
    for index, label in zip(indexes, labels):
        rows.append({"id": index, "title": label, "description": ""})

    payload = {
        "to": destinatary,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": ""},
            "body": {
                "text": "Olá. Escolha o edital que você deseja receber informações:"
            },
            "footer": {
                "text": "Para escolher outro edital futuramente, digite "
                + settings.request_menu_message
            },
            "action": {
                "button": settings.selection_message,
                "sections": [{"title": "Escolha um dos editais", "rows": rows}],
            },
        },
    }
    requests.post(
        settings.text_url,
        json=payload,
        headers={
            "D360-Api-Key": token,
            "Content-Type": "application/json",
        },
    )
