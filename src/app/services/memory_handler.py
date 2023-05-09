import redis
from settings import settings


# This class will be used store and retrieve chat history from a user, and this chat history will be stored in Redis.
class MemoryHandler:
    def __init__(self, host: str, port: int):
        self.client = redis.Redis(host=host, port=port)

    def save_history(self, user: str, message: str) -> None:
        if self.client.get(user) == None: 
            self.client.set(user, message)
            self.client.expire(user, settings.expiration_time_in_seconds)
        else:
            self.client.append(user, message)
    
    def retrieve_history(self, user: str) -> str:
        if self.client.get(user) == None:
            return None
        return self.client.get(user).decode('utf-8')
    
    def clear_history(self, user: str) -> None:
        self.client.delete(user)