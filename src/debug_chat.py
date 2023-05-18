"""
Script used for debugging the chatbot.
python debug_chat.py
"""
from app.services.chat_handler import ChatHandler

chat_bot = ChatHandler(verbose=True)
chat_bot_id = "TEST"
index = "Serasa"
user_id = input("User_ID: ")

while True:
    user_message = input("\nUSER>> ")
    answer = chat_bot.get_response(
        user_message=user_message, user_id=user_id, chatbot_id=chat_bot_id, index=index
    )
    print("BOT>>", answer)
