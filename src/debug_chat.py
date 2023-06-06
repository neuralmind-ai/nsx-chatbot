"""
Script used for debugging the chatbot.
python debug_chat.py
"""

from rich import print

from app.services.chat_handler import ChatHandler

# from app.services.memory_handler import RedisMemoryHandler
from app.services.database import JSONLDBManager
from app.services.memory_handler import JSONMemoryHandler

# memory_handler = RedisMemoryHandler(host="localhost", port=6380)
memory_handler = JSONMemoryHandler(path=".cache/memory.json")
db_manager = JSONLDBManager(
    chat_history_path=".cache/database.jsonl", index_infos_path=".cache/index.jsonl"
)

chat_bot_id = "chatbot"

print("--------[blue]Chatbot Settings[/]--------")
user_id = input("User_ID: ")
index = input("Index: ")

# Dev mode
dev_mode = input("Dev mode? ([y]/n): ")
dev_mode = True if dev_mode.strip() in ("y", "") else False
# Disable FAQ
disable_faq = input("Disable FAQ? ([y]/n): ")
disable_faq = True if disable_faq.strip() in ("y", "") else False
# Disable Memory
disable_memory = input("Disable Memory? ([y]/n): ")
disable_memory = True if disable_memory.strip() in ("y", "") else False
# Use NSX Sense
use_nsx_sense = input("Use NSX Sense? ([y]/n): ")
use_nsx_sense = True if use_nsx_sense.strip() in ("y", "") else False
# Verbose
verbose = input("Verbose? ([y]/n): ")
verbose = True if verbose.strip() in ("y", "") else False


chat_bot = ChatHandler(
    db=db_manager,
    memory=memory_handler,
    dev_mode=dev_mode,
    disable_faq=disable_faq,
    disable_memory=disable_memory,
    use_nsx_sense=use_nsx_sense,
    verbose=verbose,
)

print("--------------[blue]CHAT[/]--------------")
print('[yellow]Type "exit()" to end the chat[/]')

while True:
    print(f"[green]{user_id}>>[/] ", end="")
    user_message = input()
    if user_message == "exit()":
        break
    answer = chat_bot.get_response(
        user_message=user_message, user_id=user_id, chatbot_id=chat_bot_id, index=index
    )
    print("[red]chatbot>>", answer)
