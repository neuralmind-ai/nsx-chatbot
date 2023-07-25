"""
Script used for debugging the chatbot.
python debug_chat.py
"""

import argparse

from rich import print

from app.services.chat_handler import ChatHandler

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
    parser.add_argument("--use-nsx", action=argparse.BooleanOptionalAction)
    parser.add_argument("--bm25-only", action=argparse.BooleanOptionalAction)
    parser.add_argument("--verbose", action=argparse.BooleanOptionalAction)
    parser.add_argument("question", nargs="?")
    args = parser.parse_args()

    memory_handler = JSONMemoryHandler(path="validation/config/memory.json")
    db_manager = JSONLDBManager(
        chat_history_path="validation/config/database.jsonl",
        index_infos_path="validation/config/index.jsonl",
    )

    chat_bot_id = "chatbot"

    def bool_parser(v, prompt=None):
        if prompt and "[n]" in prompt:
            return False if v.strip() in ("n", "") else True
        return True if v.strip() in ("y", "") else False

    def get_arg(arg_value, prompt, parser=None):
        if arg_value is not None:
            return arg_value
        else:
            v = input(prompt)
            if parser is not None:
                return parser(v, prompt)

    user_id = get_arg(args.user, "User_ID: ")
    index = get_arg(args.index, "Index: ")

    print("--------[blue]Chatbot Settings[/]--------")
    dev_mode = get_arg(args.dev, "Dev mode? ([y]/n): ", bool_parser)
    disable_faq = get_arg(args.disable_faq, "Disable FAQ? ([y]/n): ", bool_parser)
    disable_memory = get_arg(args.disable_mem, "Disable Memory? ([y]/n): ", bool_parser)
    use_nsx_sense = get_arg(args.use_nsx, "Use NSX Sense? ([y]/n): ", bool_parser)
    bm25_only = args.bm25_only or False
    verbose = get_arg(args.verbose, "Verbose? ([y]/n): ", bool_parser)
    first_question = args.question

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
