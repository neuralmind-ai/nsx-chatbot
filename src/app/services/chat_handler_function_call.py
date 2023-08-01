import json
from concurrent.futures import ThreadPoolExecutor

from app.services.chat_handler import ChatHandler
from app.utils import model_utils
from app.utils.timeout_management import RequestMethod, retry_request_with_timeout
from settings import settings


def get_observation(x):
    i = x["i"]
    value = x["value"]
    index = x["index"]
    used_faq = x["used_faq"]
    latency_dict = x["latency_dict"]
    api_key = x["api_key"]
    self = x["self"]
    bm25_only = x["bm25_only"]
    result, source = self.get_observation(
        value,
        index,
        used_faq,
        latency_dict,
        api_key,
        1,
        settings.num_docs_search,
        bm25_only,
    )
    if self.verbose:
        print(f"\n{value} ({source}): {result}\n")
    return {"index": i, "name": value, "result": result, "source": source}


class ChatHandlerFunctionCall(ChatHandler):
    def call_model(self, messages, functions=None, stop=None, history=None):
        history.extend(messages)
        if functions is None:
            functions = []
        if stop is None:
            stop = []

        body = {
            "service": "ChatBot",
            "prompt": history,
            "model": self._model,
            "configurations": {
                "temperature": 0,
                "max_tokens": settings.max_tokens_function_call,
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
        if not response.ok:
            raise Exception(response.content)
        response = response.json()
        return response

    def find_answer(
        self,
        user_message,
        chat_history,
        index,
        used_faq,
        latency_dict,
        api_key,
        debug_string,
        whatsapp_verbose=False,
        destinatary=None,
        d360_number=None,
        bm25_only=False,
    ):
        history = []

        stop = ["Pergunta:"]
        # make call using function and retrieve list of queries to search
        index_domain = self._db.get_index_information(index, "domain")
        functions = [
            {
                "name": "buscar_informacoes_necessarias",
                "description": "Buscar informacoes necessarias para responder a pergunta {domain}.".format(
                    domain=index_domain
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pergunta": {
                            "type": "string",
                            "description": "Pergunta feita pelo usuario",
                        },
                        "informacoes": {
                            "type": "array",
                            "description": "Informacoes necessarias para responder a pergunta. Cada informação deve ser repetida duas vezes, com nome diferente",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "descrição da informação": {"type": "string"},
                                    "descrição alternativa da informação": {
                                        "type": "string"
                                    },
                                },
                            },
                        },
                    },
                    "required": ["pergunta", "informacoes"],
                },
            }
        ]
        response = self.call_model(
            messages=[
                {
                    "role": "system",
                    "content": f"""
Você é um assistente de chat baseado em Inteligência Artificial desenvolvido pela NeuralMind para
responder a perguntas do usuário sobre o domínio {index_domain}. Você deve seguir as seguintes regras
rigorosamente:

1. Sua função é ser um assistente prestativo que NUNCA gera conteúdo que promova ou glorifique
violência, preconceitos e atos ilegais ou antiéticos, mesmo que em cenários fictícios.
2. Você deve responder as mensagens apenas com as informações presentes no seu histórico
conversacional. Nunca utilize outras fontes.
3. Você não deve responder com o seu conhecimento interno ou que não estejam possivelmente
relacionados ao domínio mencionado anteriormente.

Lembre-se que você deve apenas
responder perguntas utilizando as informações presentes no histórico conversacional abaixo ou
pesquisadas na base de dados do/a(s) {index_domain}.""",
                },
                {"role": "user", "content": f"Pergunta: {user_message}"},
            ],
            functions=functions,
            stop=stop,
            history=history,
        )
        if response["function_call"] is None:
            answer = response["text"]
            # did not receive function call so we should answer to the user
            return answer, "No function call received"

        function_call = response["function_call"]
        debug_string += "Function Call:" + json.dumps(function_call)
        assert function_call["name"] == "buscar_informacoes_necessarias"
        arguments = json.loads(function_call["arguments"])
        history.append(
            {"role": "assistant", "function_call": response["function_call"]}
        )

        tokens_so_far = response["tokens_usage"]["total_tokens"]
        remaining_tokens = (
            settings.max_tokens_prompt
            - tokens_so_far
            - settings.max_tokens_function_call
        )

        # search all of the things using nsx
        big_result = self.search_information_parallel(
            arguments,
            index,
            used_faq,
            latency_dict,
            api_key,
            remaining_tokens,
            bm25_only,
        )

        debug_string += "\nSearch results: " + json.dumps(big_result)

        # provide answer to model and get final result back
        response = self.call_model(
            messages=[
                {
                    "role": "function",
                    "name": "buscar_informacoes_necessarias",
                    "content": json.dumps(big_result),
                }
            ],
            # functions=functions,
            stop=stop,
            history=history,
        )
        if "text" not in response or response["text"] is None:
            raise Exception(f"Error, did not get text back from model {response}")
        answer = response["text"].strip()
        return answer, debug_string

    def search_information_parallel(
        self,
        arguments,
        index,
        used_faq,
        latency_dict,
        api_key,
        remaining_tokens,
        bm25_only,
    ):
        info_list = arguments["informacoes"]
        flat_list = []
        for i, info in enumerate(info_list):
            for k in info:
                name = info[k]
                flat_list.append(
                    {
                        "i": i,
                        "value": name,
                        "self": self,
                        "index": index,
                        "used_faq": used_faq,
                        "latency_dict": latency_dict,
                        "api_key": api_key,
                        "bm25_only": bm25_only,
                    }
                )

        # use ThreadPoolExecutor to parallelize the search
        with ThreadPoolExecutor(
            max_workers=settings.parallel_observations_function_call
        ) as executor:

            answer_flat_list = executor.map(get_observation, flat_list)

            result = [{} for _ in info_list]
            for answer in answer_flat_list:
                i = answer["index"]
                name = answer["name"]
                result[i][name] = answer["result"]

                # remove answer if we've used too many tokens
                num_tokens = model_utils.get_num_tokens(json.dumps(result))
                if remaining_tokens < num_tokens:
                    result[i][name] = ""
                    num_tokens = model_utils.get_num_tokens(json.dumps(result))

            return result
