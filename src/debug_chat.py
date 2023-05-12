"""
Script used for debugging the chatbot.
python debug_chat.py
"""
from app.services.chat_handler import ChatHandler

chat_bot = ChatHandler(verbose=True)
user_id = "TEST"

while True:
    user_message = input("\nMensagem: ")
    print(chat_bot.get_response(user_message=user_message, user_id=user_id, index="FUNDEP_Ciencias"))
