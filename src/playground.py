from app.utils.timeout_management import RequestMethod, retry_request_with_timeout
from settings import settings
import json
import argparse
import importlib

## To use playground, you should create a file src/my_playground.py copying the contents from
## src/my_playground.py.example.
##
## The playground is useful to test function calls and other features that the OpenAI playground 
## does not support.
##
## You can edit edit src/my_playground.py as you wish, and then use the playground with
## `python playground.py playground_prompts.my_playground_example`.

def get_messages_from_prompt(prompt):
    return {'role': 'user', 'content': prompt}

def call(messages, functions, stop, model):
    if type(messages) == str:
        messages = get_messages_from_prompt(messages)

    body = {
    "prompt": messages,
    "service": "ChatBot",
    "model": model,
    "configurations": {
        "temperature": 0,
        "max_tokens": 512,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "stop": stop,
    },
    "functions": functions,
}
    response = retry_request_with_timeout(
        RequestMethod.POST,
        settings.completion_endpoint,
        body=body,
        request_timeout=settings.reasoning_timeout,
    )
    text = response.text
    j = json.loads(text)
    text = j.get('text')
    function_call = j.get('function_call')
    if text is not None:
        print('--- TEXT ---')
        print(text)
    if function_call is not None:
        function_call['arguments'] = json.loads(function_call['arguments'])
        print('--- FUNCTION_CALL ---')
        print(json.dumps(function_call, indent=2))

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('module')
    args = parser.parse_args()

    p = importlib.import_module(args.module)

    if 'messages' not in dir(p):
        raise Exception("'messages' must be defined.")

    messages = p.messages
    functions = p.functions if 'functions' in dir(p) else []
    stop = p.stop if 'stop' in dir(p) else []
    model = p.model if 'model' in dir(p) else 'gpt-3.5-turbo-0613'

    call(messages, functions, stop, model)