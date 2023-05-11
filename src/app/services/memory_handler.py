import redis
from settings import settings


class MemoryHandler: 
    """
    This class is used to store and retrieve chat history from a user, and this chat history will be stored in Redis.
    Methods:
        save_history: Saves the chat history of a user in a given index.
        retrieve_history: Eetrieves the chat history of a user in a given index.
        clear_history: Clears the chat history of a user in a given index.
    """

    def __init__(self, host: str, port: int):
        self.client = redis.Redis(host=host, port=port)

    def save_history(self, user: str, index:str, message: str) -> None:
        """
        This method is used to save the chat history of a user in a given index. 
        If the user already has a history in that index, the new message will be appended to the existing history.
        Every time a new message is saved, the expiration time of the key is updated.
        Args:
            user (str): The phone number of the user that sent the message.
            index (str): The index where the user had the conversation.
            message (str): The new message exchange between the user and the bot.
        """
        if self.client.hexists(user, index) == 0: 
            self.client.hset(user, index, message)
        else:
            current_history = self.retrieve_history(user, index)
            updated_history = current_history + '\n' + message
            self.client.hset(user, index, updated_history)
        self.client.expire(user, settings.expiration_time_in_seconds)
    
    def retrieve_history(self, user: str, index: str) -> str:
        """
        This method is used to retrieve the chat history of a user in a given index.
        Args:
            user (str): The phone number of the user that sent the message.
            index (str): The index where the user had the conversation.
        Returns:
            str: The chat history of the user in the given index.
        """
        if self.client.hexists(user, index) == 0:
            return None
        return self.client.hget(user, index).decode('utf-8')
    
    def clear_history(self, user: str, index: str) -> None:
        """
        This method is used to clear the chat history of a user in a given index.
        Args:
            user (str): The phone number of the user that sent the message.
        """
        self.client.hdel(user, index)
    