from fastapi import FastAPI

from app.routers import chatbot, webhook
from app.services.chat_handler import ChatHandler
from app.services.crud_cosmos import CosmosDBManager
from app.services.memory_handler import RedisMemoryHandler
from settings import settings

app = FastAPI(title="NSXBot")

app.state.memory = RedisMemoryHandler(host="localhost", port=6380)
app.state.db = CosmosDBManager()
app.state.chatbot = ChatHandler(
    db=app.state.db,
    memory=app.state.memory,
    disable_faq=settings.disable_faqs,
    disable_memory=settings.disable_memory,
    use_nsx_sense=settings.use_sense,
)

app.include_router(webhook.router, tags=["webhook"])
app.include_router(chatbot.router, tags=["chatbot"])
