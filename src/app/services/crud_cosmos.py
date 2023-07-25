from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.services.database import DBManager
from settings import settings


class CosmosDBManager(DBManager):
    """Class that manages chatbot-cosmosdb communication"""

    def __init__(self) -> None:
        self._client = CosmosClient(settings.cosmos_endpoint, settings.cosmos_key)
        self._database = self._client.get_database_client(settings.cosmos_database_name)
        self._chat_history_container = self._database.get_container_client(
            settings.cosmos_container_name
        )
        self._index_container = self._database.get_container_client(
            settings.cosmos_index_container_name
        )

    def upsert_chat_history(self, user_id: str, index: str, content: dict):
        """
        Inserts or updates an item in the Cosmos DB container.
        Args:
            user_id: The id of the user.
            index: The index of the chat history.
            content: The content of item to be inserted or updated.
        """
        try:
            item = self._chat_history_container.read_item(
                item=user_id, partition_key=user_id
            )
            if item["messages"].get(index):
                item["messages"][index].append(content)
            else:
                item["messages"][index] = [content]
        except CosmosResourceNotFoundError:
            item = {"id": user_id, "messages": {index: [content]}}

        self._chat_history_container.upsert_item(body=item)

    def get_index_information(self, index_id: str, information: str):
        """
        Gets the information of a specific index.
        Args:
            index_id: The id of the index.
            information: The information to be retrieved.
        Returns:
            The information of the index.
        """
        try:
            item = self._index_container.read_item(
                item=index_id, partition_key=index_id
            )
            return item[information]
        except (CosmosResourceNotFoundError, KeyError):
            return None
