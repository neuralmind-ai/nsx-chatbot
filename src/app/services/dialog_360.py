import requests

from app.services.azure_vault import read_secret
from app.services.database import DBManager
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


def post_360_dialog_intro_message(
    destinatary: str,
    index: str,
    d360_number: str,
    destinatary_history: str,
    db: DBManager,
):
    """
    Sends a message introducing the chatbot to the user, by using the information from the index configuration in CosmosDB.
    If the information is not available in CosmosDB, or if this is not the first message from the user, the introduction is not sent,
    only a message saying that the chatbot is processing the user's question.
    Args:
        destinatary (str): The destinatary's phone number.
        index (str): The index name.
        d360_number (str): The chatbot's number.
        destinatary_history (str): The destinatary's conversation history, used to know if it is the first message in the conversation.
    """
    message_prefix = db.get_index_information(index, "message_prefix")
    if (destinatary_history is None) and (message_prefix is not None):
        intro_message = f"{message_prefix}\nPor favor, aguarde enquanto busco a resposta para sua pergunta..."
    else:
        intro_message = (
            "Por favor, aguarde enquanto busco a resposta para sua pergunta..."
        )
    post_360_dialog_text_message(destinatary, intro_message, d360_number)


def post_360_dialog_error_message(
    destinatary: str, index: str, d360_number: str, db: DBManager
):
    """
    Sends a message to the user saying that an error occurred while processing the message.
    If there is a default error message configured in CosmosDB, it is used. Otherwise, a default message is sent.
    Args:
        destinatary (str): The destinatary's phone number.
        index (str): The index name.
        d360_number (str): The chatbot's number.
    """
    error_message = db.get_index_information(index, "default_message")
    if error_message is None:
        error_message = "Erro no processamento da mensagem. Tente novamente."
    post_360_dialog_text_message(destinatary, error_message, d360_number)
