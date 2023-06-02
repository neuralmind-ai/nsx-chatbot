"""
Script used for debugging the chatbot.
python debug_chat.py
"""
from app.services.chat_handler import ChatHandler

chat_bot_sense = ChatHandler(verbose=True)
chat_bot_id = "TEST_Sense"
index = "FUNDEP_Medicina"
user_id = "teste"
user_id_sense = "teste_sense"

while True:
    user_message = input("\nUSER>> ")

    answer = chat_bot_sense.get_response(
        user_message=user_message,
        user_id=user_id_sense,
        chatbot_id=chat_bot_id,
        index=index,
    )
    print("BOT>>", answer)
