from fastapi import FastAPI

from app.routers import chatbot, webhook
from app.services.chat_handler import ChatHandler

app = FastAPI(title="NSXBot")

app.state.chatbot = ChatHandler(verbose=False)

app.include_router(webhook.router, tags=["webhook"])
app.include_router(chatbot.router, tags=["chatbot"])
