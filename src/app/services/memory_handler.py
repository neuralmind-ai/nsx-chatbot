import redis
from settings import settings


class MemoryHandler: 
    """
    This class is used to store and retrieve chat history from a user, and this chat history will be stored in Redis.
    Methods:
        - save_history: Saves the chat history of a user in a given index.
        - retrieve_history: Eetrieves the chat history of a user in a given index.
        - clear_history: Clears the chat history of a user in a given index.
        - set_latest_user_index: Updates the last index used by the user.
        - get_latest_user_index: Gets the last index used by the user.
    """

    def __init__(self, host: str, port: int):
        self.client = redis.Redis(host=host, port=port)

    def save_history(self, user: str, chatbot_id: str, index:str, message: str) -> None:
        """
        This method is used to save the chat history of a user in a given index. 
        If the user already has a history in that index, the new message will be appended to the existing history.
        Every time a new message is saved, the expiration time of the key is updated.
        Args:
            - user (str): The id of the user that sent the message (maybe phone number).
            - chatbot_id (str): The id of the chatbot instance (maybe phone number).
            - index (str): The index where the user had the conversation.
            - message (str): The new message exchange between the user and the bot.
        """
        user_id = user + '_' + chatbot_id
        if self.client.hexists(user_id, index) == 0: 
            self.client.hset(user_id, index, message)
        else:
            current_history = self.retrieve_history(user, chatbot_id, index)
            updated_history = current_history + '\n' + message
            self.client.hset(user_id, index, updated_history)
        self.client.expire(user_id, settings.expiration_time_in_seconds)
    
    def retrieve_history(self, user: str, chatbot_id: str, index: str) -> str:
        """
        This method is used to retrieve the chat history of a user in a given index.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - index (str): The index where the user had the conversation.
        Returns:
            - str: The chat history of the user in the given index.
        """
        user_id = user + '_' + chatbot_id
        if self.client.hexists(user_id, index) == 0:
            return None
        return self.client.hget(user_id, index).decode('utf-8')
    
    def clear_history(self, user: str, chatbot_id: str, index: str) -> None:
        """
        This method is used to clear the chat history of a user in a given index.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - index (str): The index where the user had the conversation.
        """
        user_id = user + '_' + chatbot_id
        self.client.hdel(user_id, index)
    
    def set_latest_user_index(self, user: str, chatbot_id: str, index: str) -> None:
        """
        This method is used to set the last index used by the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
            - index (str): The last index used by the user.
        """
        user_id = user + '_' + chatbot_id
        self.client.hset(user_id, 'latest_index', index)
    
    def get_latest_user_index(self, user: str, chatbot_id: str) -> str:
        """
        This method is used to get the last index used by the user.
        Args:
            - user (str): The id of the user that sent the message.
            - chatbot_id (str): The id of the chatbot instance.
        Returns:
            - str: The last index used by the user.
        """
        user_id = user + '_' + chatbot_id
        if self.client.hexists(user_id, 'latest_index') == 0:
            return None
        return self.client.hget(user_id, 'latest_index').decode('utf-8')
    