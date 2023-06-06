from pydantic import BaseModel


class Item(BaseModel):
    timestamp: str
    user_message: str
    answer: str
    reasoning: str
    latency: dict
