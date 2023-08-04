from app.services.chat_handler import ChatHandler
from app.services.chat_handler_function_call import ChatHandlerFunctionCall


def getHandler(handler_name):
    handlers = {
        "ChatHandler": ChatHandler,
        "ChatHandlerFunctionCall": ChatHandlerFunctionCall,
    }
    handler = handlers.get(handler_name)
    if handler is None:
        raise Exception(f"Could not find handler '{handler_name}'")
    return handler
