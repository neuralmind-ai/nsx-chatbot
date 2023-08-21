"""
Script used for debugging the chatbot.
python debug_chat.py
"""

import argparse

from rich import print

from app.services.chat_handler import ChatHandler
from app.services.chat_handler_factory import getHandler

# from app.services.memory_handler import RedisMemoryHandler
from app.services.database import JSONLDBManager
from app.services.memory_handler import JSONMemoryHandler

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--user")
    parser.add_argument("--index", "-i")
    parser.add_argument("--dev", action=argparse.BooleanOptionalAction)
    parser.add_argument("--disable-faq", action=argparse.BooleanOptionalAction)
    parser.add_argument("--disable-mem", action=argparse.BooleanOptionalAction)
    parser.add_argument("--use-sense", action=argparse.BooleanOptionalAction)
    parser.add_argument("--bm25-only", action=argparse.BooleanOptionalAction)
    parser.add_argument("--verbose", action=argparse.BooleanOptionalAction)
    parser.add_argument("--use-func", action=argparse.BooleanOptionalAction)
    parser.add_argument("question", nargs="?")
    args = parser.parse_args()

    memory_handler = JSONMemoryHandler(path="validation/config/memory.json")
    db_manager = JSONLDBManager(
        chat_history_path="validation/config/database.jsonl",
        index_infos_path="validation/config/index.jsonl",
    )

    chat_bot_id = "chatbot"

    user_id = args.user if args.user is not None else "teste"
    index = args.index if args.index is not None else "FUNDEP_Paraopeba"

    dev_mode = args.dev if args.dev is not None else True
    disable_faq = args.disable_faq if args.disable_faq is not None else True
    disable_memory = args.disable_mem if args.disable_mem is not None else False
    bm25_only = args.bm25_only or False
    verbose = args.verbose if args.verbose is not None else True
    first_question = args.question
    use_func = args.use_func
    use_nsx_sense = args.use_sense if args.use_sense is not None else True

    print("--------[blue]Chatbot Settings[/]--------")
    print("Dev mode:", dev_mode)
    print("Disable FAQ:", disable_faq)
    print("Disable memory:", disable_memory)
    print("BM25 only:", bm25_only)
    print("Verbose mode:", verbose)

    Handler: ChatHandler = getHandler("ChatHandler")
    if use_func:
        Handler = getHandler("ChatHandlerFunctionCall")

    chat_bot = Handler(
        db=db_manager,
        memory=memory_handler,
        dev_mode=dev_mode,
        disable_faq=disable_faq,
        disable_memory=disable_memory,
        use_nsx_sense=use_nsx_sense,
        verbose=verbose,
        return_debug=False,
    )

    print("--------------[blue]CHAT[/]--------------")
    print('[yellow]Type "exit()" to end the chat[/]')

    is_first_question = True
    while True:
        print(f"[green]{user_id}>>[/] ", end="")
        if is_first_question and (first_question is not None):
            user_message = first_question
            print(
                first_question,
            )
        else:
            user_message = input()

        is_first_question = False
        if user_message == "exit()":
            break
        answer = chat_bot.get_response(
            user_message=user_message,
            user_id=user_id,
            chatbot_id=chat_bot_id,
            index=index,
            bm25_only=bm25_only,
        )
        print("[red]chatbot>>", answer)
