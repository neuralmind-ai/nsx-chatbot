from app.utils.error_codes import ErrorCodes


class ChatbotException(Exception):
    """
    Base class for all exceptions raised by the chatbot
    """

    def __init__(self, error_code, *args, **kwargs):
        self.error_code = error_code
        super().__init__(*args, **kwargs)


class NSXAuthenticationError(ChatbotException):
    """
    Raised when the NSX authentication fails, which usually is related to an invalid API Key
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.NSX_AUTHENTICATION
        super().__init__(error_code, *args, **kwargs)


class NSXSearchError(ChatbotException):
    """
    Raised when the NSX search fails for any reason other than a timeout or an authentication error
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.NSX_SEARCH
        super().__init__(error_code, *args, **kwargs)


class SenseSearchError(ChatbotException):
    """
    Raised when the Sense search fails for any other reason other than a timeout
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.SENSE_SEARCH
        super().__init__(error_code, *args, **kwargs)


class ModerationError(ChatbotException):
    """
    Raised when there is an error when calling OpenAI Moderation API.
    This does not include errors related to a malfunction of the Prompt Answerer
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.MODERATION
        super().__init__(error_code, *args, **kwargs)


class PromptAnswererError(ChatbotException):
    """
    Raised when there is an error when calling the Prompt Answerer container.
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.PROMPT_ANSWERER
        super().__init__(error_code, *args, **kwargs)


class DialogConfigError(ChatbotException):
    """
    Raised when the 360dialog configuration is invalid. This includes:
    - A menu message that is longer than 20 characters
    - A message for requesting the menu that does not start with a "#"
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.DIALOG_CONFIG
        super().__init__(error_code, *args, **kwargs)


class WebhookError(ChatbotException):
    """
    Raised when there is any generic error related to the handling of messages received by the webhook endpoint.
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.WEBHOOK
        super().__init__(error_code, *args, **kwargs)


class MaxTokensError(ChatbotException):
    """
    Raised when the number of tokens in a message exceeds the maximum allowed by OpenAI
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.MAX_TOKENS
        super().__init__(error_code, *args, **kwargs)


class MemoryHandlerError(ChatbotException):
    """
    Raised when there is an error related to the Memory Handler.
    """

    def __init__(self, *args, **kwargs):
        error_code = ErrorCodes.MEMORY
        super().__init__(error_code, *args, **kwargs)
