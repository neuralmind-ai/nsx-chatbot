from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from settings import settings

client = CosmosClient(settings.cosmos_endpoint, settings.cosmos_key)
database = client.get_database_client(settings.cosmos_database_name)
container = database.get_container_client(settings.cosmos_container_name)


def read_item(user_id: str):
    """
    Reads an item from the Cosmos DB container.
    Returns:
        A dict with the item. Returns None if the item does not exist.
    """
    try:
        return container.read_item(item=user_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return None


def upsert_chat_history(user_id: str, index: str, content: dict):
    """
    Inserts or updates an item in the Cosmos DB container.
    Args:
        user_id: The id of the user.
        index: The index of the chat history.
        content: The content of item to be inserted or updated.
    """
    item = read_item(user_id)
    if item:
        if item["messages"].get(index):
            item["messages"][index].append(content)
        else:
            item["messages"][index] = [content]
    else:
        item = {"id": user_id, "messages": {index: [content]}}
    container.upsert_item(body=item)
