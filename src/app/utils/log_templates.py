import json
import logging
import traceback
from datetime import datetime


def log_error(
    logger: logging.Logger,
    destinatary: str,
    nm_number: str,
    user_message: str,
    error: Exception,
):
    logger.error(
        json.dumps(
            {
                "user_id": destinatary,
                "chatbot_id": nm_number,
                "user_message": user_message,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            ensure_ascii=False,
        )
    )
