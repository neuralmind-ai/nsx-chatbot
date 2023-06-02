import json
import traceback
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.schemas.messages import ChatAnswer, ChatMessage
from app.services.build_timed_logger import build_timed_logger
from app.services.crud_cosmos import get_index_information

router = APIRouter()

chatbot_api_logger = build_timed_logger("chatbot_api_logger", "chatbot_api_log")


@router.post(
    "/chatbot",
    status_code=status.HTTP_200_OK,
    response_model=ChatAnswer,
    responses={
        200: {
            "content": {"application/json": {}},
            "description": "Search completed",
        },
        400: {
            "content": {"application/json": {}},
            "description": "Bad request",
        },
    },
)
def get_chat_answer(
    request: Request,
    body: ChatMessage,
    index: str = Query(..., description="Index to search for the answer"),
):
    try:
        if "authorization" in request.headers:
            api_key = request.headers["authorization"].split(" ")[1]
            answer = request.app.state.chatbot.get_response(
                user_message=body.message,
                user_id=body.user,
                index=index,
                api_key=api_key,
            )
        else:
            answer = request.app.state.chatbot.get_response(
                user_message=body.message,
                user_id=body.user,
                index=index,
            )
        chatbot_api_logger.info(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": body.user,
                    "message": body.message,
                    "index": index,
                    "chatbot_answer": answer,
                }
            )
        )
        message_prefix = get_index_information(index, "message_prefix")
        if message_prefix:
            answer = message_prefix + answer
        return ChatAnswer(answer=answer)
    except Exception as e:
        chatbot_api_logger.error(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": body.user,
                    "message": body.message,
                    "index": index,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
        )
        raise HTTPException(status_code=400, detail=str(e))
