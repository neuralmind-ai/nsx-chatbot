from fastapi import FastAPI

from app.routers import chatbot, webhook
from app.services.chat_handler import ChatHandler
from app.services.memory_handler import MemoryHandler

app = FastAPI(title="NSXBot")

app.state.memory = MemoryHandler("localhost", 6380)
app.state.chatbot = ChatHandler(verbose=False)

app.include_router(webhook.router, tags=["webhook"])
app.include_router(chatbot.router, tags=["chatbot"])
