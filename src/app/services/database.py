import json
from abc import ABC, abstractmethod
from pathlib import Path


class DBManager(ABC):
    """Class that manages chatbot-database communication"""

    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def upsert_chat_history(self, user_id: str, index: str, content: dict):
        """
        Inserts or updates an item in the database.
        Args:
            user_id: The id of the user.
            index: The index of the chat history.
            content: The content of item to be inserted or updated.
        """

    @abstractmethod
    def get_index_information(index_id: str, information: str):
        """
        Gets the information of a specific index in the database.
        Args:
            index_id: The id of the index.
            information: The information to be retrieved.
        Returns:
            The information of the index.
        """


class JSONLDBManager(DBManager):
    """Class that manages chatbot-jsonl_database communication
    NOTE: This class is for development use only. It is not recommended to use it in production environments.
    """

    def __init__(self, chat_history_path: str, index_infos_path: str) -> None:
        super().__init__()
        self._chat_history_db_path = chat_history_path
        self._index_infos_db_path = index_infos_path
        self._chat_history_db = Path(self._chat_history_db_path)
        self._chat_history_db.touch(exist_ok=True)
        self._index_infos_db = Path(self._index_infos_db_path)
        assert self._index_infos_db.exists(), "Index infos database does not exist."

    def upsert_chat_history(self, user_id: str, index: str, content: dict):
        """
        Inserts or updates an item in the JSONL DB.
        Args:
            user_id: The id of the user.
            index: The index of the chat history.
            content: The content of item to be inserted or updated.
        """
        with self._chat_history_db.open("r") as f:
            lines = [json.loads(line) for line in f.readlines()]

        for item in lines:
            if item["id"] == user_id:
                if item["messages"].get(index):
                    item["messages"][index].append(content)
                else:
                    item["messages"][index] = [content]
                break
        else:
            item = None
        if len(lines) == 0 or item is None:
            lines.append({"id": user_id, "messages": {index: [content]}})

        with self._chat_history_db.open("w") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    def get_index_information(self, index_id: str, information: str):
        """
        Gets the information of a specific index in the JSONL DB.
        Args:
            index_id: The id of the index.
            information: The information to be retrieved.
        Returns:
            The information of the index.
        """
        with self._index_infos_db.open("r") as f:
            for line in f:
                item = json.loads(line)
                if item.get("id", None) == index_id:
                    return item.get(information, None)
        return None
