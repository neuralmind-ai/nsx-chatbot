import json
from abc import ABC, abstractmethod
from pathlib import Path

import redis

from app.utils.exceptions import MemoryHandlerError
from settings import settings


def handle_memory_errors(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            raise MemoryHandlerError(e)

    return wrapper


class MemoryHandler(ABC):
    """
    This class is used to store and retrieve chat history from a user.
    Methods:
        - save_history: Saves the chat history of a user in a given index.
        - retrieve_history: Eetrieves the chat history of a user in a given index.
        - clear_history: Clears the chat history of a user in a given index.
        - set_latest_user_index: Updates the last index used by the user.
        - get_latest_user_index: Gets the last index used by the user.
    """

    @abstractmethod
    def save_interaction(
        self, user: str, chatbot_id: str, index: str, interaction: str
    ) -> None:
        """
        This method is used to save a interaction of a user in a given index.
        Every time a new message is saved, the expiration time of the key is updated.

        Args:

        - user (str): The id of the user that sent the message (maybe phone number).
        - chatbot_id (str): The id of the chatbot instance (maybe phone number).
        - index (str): The index where the user had the conversation.
        - interaction (str): The new interaction between the user and the bot.
            - Interactions are expected to be written as "User: message\\nAssistant: response"
        """

    @abstractmethod
    def save_history(
        self, user: str, chatbot_id: str, index: str, history: str
    ) -> None:
        """
        This method is used to save the chat history of a user in a given index.
        If the user already has a history in that index, the new history will overwrite the existing history.
        Every time a new message is saved, the expiration time of the key is updated.

        Args:

        - user (str): The id of the user that sent the message (maybe phone number).
        - chatbot_id (str): The id of the chatbot instance (maybe phone number).
        - index (str): The index where the user had the conversation.
        - history (str): String representing a JSON object:
            {
                "interactions": ["User: message\nAssistant: response", ...]
            }
        """

    @abstractmethod
    def retrieve_history(self, user: str, chatbot_id: str, index: str) -> dict:
        """
        This method is used to retrieve the chat history of a user in a given index.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - index (str): The index where the user had the conversation.
        Returns:
            - A dictionary in the following format: {
                "interactions": [list of strings, each of which representing a message-response pair],
                "summary": string containing a summary of interactions older than those in the list
            }
        """

    @abstractmethod
    def clear_history(self, user: str, chatbot_id: str, index: str) -> None:
        """
        This method is used to clear the chat history of a user in a given index.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - index (str): The index where the user had the conversation.
        """

    @abstractmethod
    def set_latest_user_index(self, user: str, chatbot_id: str, index: str) -> None:
        """
        This method is used to set the last index used by the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - index (str): The last index used by the user.
        """

    @abstractmethod
    def get_latest_user_index(self, user: str, chatbot_id: str) -> str:
        """
        This method is used to get the last index used by the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
        Returns:
            - str: The last index used by the user.
        """

    @abstractmethod
    def set_intro_message_sent(self, user: str, chatbot_id: str, index: str) -> None:
        """
        This method is used to set the intro message was sent to the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
        """

    @abstractmethod
    def check_intro_message_sent(self, user: str, chatbot_id: str, index: str) -> bool:
        """
        This method is used to check if the intro message was already sent to the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
        Returns:
            - bool: True if the intro message was already sent, False otherwise.
        """

    @abstractmethod
    def set_disclaimer_sent(self, user: str, chatbot_id: str, index: str) -> None:
        """
        This method is used to set the disclaimer was sent to the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
        """

    @abstractmethod
    def check_disclaimer_sent(self, user: str, chatbot_id: str, index: str) -> bool:
        """
        This method is used to check if the disclaimer was already sent to the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
        Returns:
            - bool: True if the disclaimer was already sent, False otherwise.
        """


class JSONMemoryHandler(MemoryHandler):
    """
    This class implements the MemoryHandler using a JSON file to store the chat history.
    NOTE: This class is for development use only. It is not recommended to use it in production environments.
    """

    def __init__(self, path: str) -> None:
        self._memory_path = path
        self._memory = Path(path)
        self._memory.touch(exist_ok=True)
        self._save(memory={})

    @handle_memory_errors
    def _open(self) -> dict:
        with self._memory.open("r", encoding="utf-8") as f:
            try:
                memory = json.load(f)
            except Exception:
                memory = {}
        return memory

    @handle_memory_errors
    def _save(self, memory) -> None:
        with self._memory.open("w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=4)

    @handle_memory_errors
    def save_interaction(
        self, user: str, chatbot_id: str, index: str, interaction: str
    ) -> None:

        user_id = user + "_" + chatbot_id
        memory = self._open()

        # Checks if the user has a history:
        user_chat_history = memory.get(user_id, None)
        if user_chat_history is None:
            memory[user_id] = {index: {"interactions": [], "summary": ""}}

        history = memory[user_id][index]
        history["interactions"].append(interaction)
        history_string = json.dumps(history, ensure_ascii=False)

        self.save_history(user, chatbot_id, index, history_string)

    @handle_memory_errors
    def save_history(
        self, user: str, chatbot_id: str, index: str, history: str
    ) -> None:

        user_id = user + "_" + chatbot_id
        memory = self._open()

        # Checks if the user already has a chat history:
        user_chat_history = memory.get(user_id, None)
        if not user_chat_history:
            memory[user_id] = {}

        memory[user_id][index] = json.loads(history)

        self._save(memory=memory)

    @handle_memory_errors
    def retrieve_history(self, user: str, chatbot_id: str, index: str) -> dict:
        user_id = user + "_" + chatbot_id
        history = self._open().get(user_id, {}).get(index, None)
        return history

    def clear_history(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        memory = self._open()
        try:
            del memory[user_id][index]["interactions"]
            self._save(memory=memory)
        except Exception:
            pass

    @handle_memory_errors
    def set_latest_user_index(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        memory = self._open()
        try:
            memory[user_id]["latest_index"] = index
        except Exception:
            memory[user_id] = {"latest_index": index}
        self._save(memory=memory)

    @handle_memory_errors
    def get_latest_user_index(self, user: str, chatbot_id: str) -> str:
        user_id = user + "_" + chatbot_id
        memory = self._open()
        return memory.get(user_id, {}).get("latest_index", None)

    @handle_memory_errors
    def set_intro_message_sent(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        memory = self._open()
        try:
            memory[user_id][f"{index}_intro_message_sent"] = True
        except Exception:
            memory[user_id] = {f"{index}_intro_message_sent": True}
        self._save(memory=memory)

    @handle_memory_errors
    def check_intro_message_sent(self, user: str, chatbot_id: str, index: str) -> bool:
        user_id = user + "_" + chatbot_id
        memory = self._open()
        return memory.get(user_id, {}).get(f"{index}_intro_message_sent", False)

    @handle_memory_errors
    def set_disclaimer_sent(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        memory = self._open()
        try:
            memory[user_id][f"{index}_disclaimer_sent"] = True
        except Exception:
            memory[user_id] = {f"{index}_disclaimer_sent": True}
        self._save(memory=memory)

    @handle_memory_errors
    def check_disclaimer_sent(self, user: str, chatbot_id: str, index: str) -> bool:
        user_id = user + "_" + chatbot_id
        memory = self._open()
        return memory.get(user_id, {}).get(f"{index}_disclaimer_sent", False)


class RedisMemoryHandler(MemoryHandler):
    """
    This class implements the MemoryHandler using Redis to store the chat history.
    """

    def __init__(self, host: str, port: int):
        self.client = redis.Redis(host=host, port=port)

    @handle_memory_errors
    def save_interaction(
        self, user: str, chatbot_id: str, index: str, interaction: str
    ) -> None:
        user_id = user + "_" + chatbot_id
        chat_history = self.retrieve_history(user, chatbot_id, index)
        if chat_history is None:
            chat_history = {"interactions": [], "summary": ""}
        chat_history["interactions"].append(interaction)
        history_string = json.dumps(chat_history)
        self.save_history(user, chatbot_id, index, history_string)
        self.client.expire(user_id, settings.expiration_time_in_seconds)

    @handle_memory_errors
    def save_history(
        self, user: str, chatbot_id: str, index: str, history: str
    ) -> None:
        user_id = user + "_" + chatbot_id
        self.client.hset(user_id, index, history)
        self.client.expire(user_id, settings.expiration_time_in_seconds)

    @handle_memory_errors
    def retrieve_history(self, user: str, chatbot_id: str, index: str) -> dict:
        user_id = user + "_" + chatbot_id
        if self.client.hexists(user_id, index) == 0:
            return None
        return json.loads(self.client.hget(user_id, index).decode("utf-8"))

    @handle_memory_errors
    def clear_history(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        self.client.hdel(user_id, index)

    @handle_memory_errors
    def set_latest_user_index(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        self.client.hset(user_id, "latest_index", index)

    @handle_memory_errors
    def get_latest_user_index(self, user: str, chatbot_id: str) -> str:
        user_id = user + "_" + chatbot_id
        if self.client.hexists(user_id, "latest_index") == 0:
            return None
        return self.client.hget(user_id, "latest_index").decode("utf-8")

    def set_user_configs(self, user: str, chatbot_id: str, configs: dict) -> None:
        """
        This method is used to set the user configs. The configs are used for debugging purposes.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - configs (dict): The configs to be set.
                - key (str): The key of the config.
                - value (str): The value of the config.
        """
        user_id = user + "_" + chatbot_id
        for key, value in configs.items():
            self.client.hset(user_id, key, value)

    def get_user_config(self, user: str, chatbot_id: str, config: str):
        """
        This method is used to get the user configs. The configs are used for debugging purposes.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - config (str): The config to be retrieved.
        """
        user_id = user + "_" + chatbot_id
        if self.client.hexists(user_id, config) == 0:
            return 0
        return self.client.hget(user_id, config)

    def reset_chatbot(self, user: str, chatbot_id: str) -> None:
        """
        This method is used to reset all configs and history of a user in a given index.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
        """
        user_id = user + "_" + chatbot_id
        self.client.delete(user_id)

    @handle_memory_errors
    def set_intro_message_sent(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        self.client.hset(user_id, f"{index}_intro_message_sent", "True")

    @handle_memory_errors
    def check_intro_message_sent(self, user: str, chatbot_id: str, index: str) -> bool:
        user_id = user + "_" + chatbot_id
        if self.client.hexists(user_id, f"{index}_intro_message_sent") == 0:
            return False
        return (
            self.client.hget(user_id, f"{index}_intro_message_sent").decode("utf-8")
            == "True"
        )

    @handle_memory_errors
    def set_disclaimer_sent(self, user: str, chatbot_id: str, index: str) -> None:
        user_id = user + "_" + chatbot_id
        self.client.hset(user_id, f"{index}_disclaimer_sent", "True")

    @handle_memory_errors
    def check_disclaimer_sent(self, user: str, chatbot_id: str, index: str) -> bool:
        user_id = user + "_" + chatbot_id
        if self.client.hexists(user_id, f"{index}_disclaimer_sent") == 0:
            return False
        return (
            self.client.hget(user_id, f"{index}_disclaimer_sent").decode("utf-8")
            == "True"
        )
