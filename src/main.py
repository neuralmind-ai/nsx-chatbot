from fastapi import FastAPI

from app.routers import webhook

app = FastAPI(title="NSXBot")

app.include_router(webhook.router, tags=["webhook"])
