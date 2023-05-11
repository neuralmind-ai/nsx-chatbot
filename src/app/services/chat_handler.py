import json
import re
import time
from datetime import datetime
from glob import glob
from typing import List

import requests
import tiktoken

from app.schemas.cosmos_item import Item
from app.services.crud_cosmos import upsert_chat_history
from app.services.memory_handler import MemoryHandler
from settings import settings

from .build_timed_logger import build_timed_logger

chat_logger = build_timed_logger("chat_logger", "chat.log")
error_logger = build_timed_logger("error_logger", "error.log")
harmful_logger = build_timed_logger("harmful_logger", "harmful.log")
latency_logger = build_timed_logger("latency_logger", "latency.log")

memory_handler = MemoryHandler("localhost", 6380)


class ChatHandler:
    """
    This class is responsible for handling the chatbot.
    Methods:
        get_response: returns the response for the user message.
        load_faqs: loads the faqs from the faqs folder.
        get_reasoning: returns the reasoning for the message.
        get_observation: returns the observation for the message.
        get_nsx_answer: returns the answer from nsx.
        get_faq_answer: search for an answer in the faqs.
        get_chat_history: returns the chat history for the user.
        get_num_tokens: returns the number of tokens in the text.
    """

    def __init__(self, verbose: bool = False, return_debug: bool = False):
        """
        Args:
            - verbose: if True, prints all the steps of the reasoning.
            - return_debug: if True, returns the debug string containing
            all reasoning steps.
        """
        # Loads all prompts
        prompts = json.load(
            open("app/prompts/base_prompt_pt.json", "r", encoding="utf8")
        )
        # TODO: add support for other languages
        self.language = "pt"

        # Base prompts
        self.chat_prompt = prompts[self.language]["chat_prompt"]
        self.faq_prompt = prompts[self.language]["faq_prompt"]
        self.summary_prompt = prompts[self.language]["new_summary_prompt"]
        self.force_finish_prompt = prompts[self.language]["force_finish_prompt"]

        # Loads the FAQs
        self.faq = self.load_faqs("app/faqs")

        # Verbose and debug
        self.verbose = verbose
        self.return_debug = return_debug

    def load_faqs(self, faq_folder: str):
        """
        Returns a dictionary with the faqs.
        """
        # TODO: Stop using json files for the faqs -> use a database
        faq_files = glob(f"{faq_folder}/*.json")
        faqs = {}
        for faq in faq_files:
            faqs[faq.split("/")[-1].split(".")[0]] = json.load(open(faq, "r"))
        return faqs

    def get_response(
        self, user_message: str, user_id: str, index: str = settings.search_index
    ) -> str:
        """
        Returns the response for the user message.
        Args:
            - user_message: the message sent by the user.
            - user_id: the id of the user (used to access the chat history).
            - index: the index to be used for the search (FAQ and NSX).
        """
        # Stores all reasoning steps for debugging
        debug_string = ""

        time_begin = time.time()
        # Stores the latency for each step
        latency_dict = {}

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Checks if the user message is harmful
        if self.is_the_message_harmful(user_message):
            harmful_logger.info(
                json.dumps(
                    {"user_id": user_id, "message": user_message, "timestamp": date}
                )
            )
            return "Mensagem ignorada por conter conteúdo ofensivo."

        # Gets the chat history from Redis
        time_pre_redis = time.time()
        chat_history = self.get_chat_history(user_id, index)
        latency_dict["redis_get"] = time.time() - time_pre_redis

        prompt = f"{self.chat_prompt}\n{chat_history}\nMensagem: {user_message}\n"

        # Starts the reasoning loop
        done = True
        time_pre_reasoning = time.time()
        for i in range(1, settings.max_num_reasoning + 1):
            # Adds the reasoning to the prompt
            reasoning_prompt = f"{prompt}Pensamento {i}:"
            reasoning = self.get_reasoning(
                prompt=reasoning_prompt, stop=[f"Observação {i}:", "Mensagem:"]
            )
            try:
                thought, action = reasoning.strip().split(f"\nAção {i}:")
            except Exception:
                # Occurs if there is no action
                thought = reasoning.strip().split("\n")[0]
                action = self.get_reasoning(
                    f"{reasoning_prompt}Pensamento {i}: {thought}\nAção {i}:",
                    stop=["\n"],
                ).strip()

            # Prints the reasoning
            if self.verbose:
                print(f"Thought {i}: {thought}")
                print(f"Action {i}: {action}")
            debug_string += f"Thought {i}: {thought}\nAction {i}: {action}\n"

            # TODO: Create a better regex to match actions
            if action.startswith(" Finalizar"):
                done = True
                break
            else:
                # If the action is not to finish, gets an observation
                observation = self.get_observation(action, index)

                if self.verbose:
                    print(f"Observation {i}: {observation}")
                debug_string += f"Observation {i}: {observation}\n"

            # Adds the thought, action and observation to the iteration string
            iteration_string = f"Pensamento {i}: {thought}\nAção {i}: {action}\nObservação {i}: {observation}\n"

            # Checks if the number of tokens is under the limit
            total_tokens = self.get_num_tokens(prompt + iteration_string)
            if total_tokens > settings.max_tokens_prompt:
                break

            # Adds the iteration string to the prompt
            prompt += iteration_string

        # If the reasoning is not done, forces the finish
        if not done:
            action = self.get_reasoning(
                f"{prompt}Pensamento: 'Máximo número de iteracões atingido. Devo responder com as informações que tenho até agora.'\n\nAção: Finalizar["
            )
            if self.verbose:
                print(f"Action {i}: {action}")
            debug_string += f"Action {i}: {action}\n"

        # TODO: Create a better regex to match actions
        try:
            answer = re.search("(?<=\\[).*(?=\\])|(?<=\\[).*", action).group()
        except Exception:
            # If the action did not match the regex, uses the action as the answer
            answer = action

        # Moderates the answer
        if self.is_the_message_harmful(answer):
            harmful_logger.info(
                json.dumps(
                    {
                        "user_id": user_id,
                        "user_message": user_message,
                        "answer": answer,
                        "reasoning": debug_string,
                        "timestamp": date,
                    }
                )
            )

            return "Mensagem ignorada por conter conteúdo ofensivo."

        latency_dict["reasoning"] = time.time() - time_pre_reasoning

        # Adds the answer to the user's chat history
        time_pre_redis_history = time.time()
        memory_handler.save_history(
            user_id, index, f"Usuário: {user_message}\nAssistente: {answer}\n"
        )
        latency_dict["redis_set"] = time.time() - time_pre_redis_history

        chat_logger.info(
            json.dumps(
                {
                    "user_id": user_id,
                    "user_message": user_message,
                    "answer": answer,
                    "reasoning": debug_string,
                    "timestamp": date,
                }
            )
        )

        # Save user message and answer to CosmosDB
        try:
            time_pre_cosmos = time.time()
            upsert_chat_history(
                user_id=user_id,
                index=index,
                content=Item(
                    timestamp=date,
                    user_message=user_message,
                    answer=answer,
                    reasoning=debug_string,
                    latency=latency_dict,
                ).dict(),
            )
            latency_dict["cosmos"] = time.time() - time_pre_cosmos
        except Exception as e:
            if self.verbose:
                print("Error sending to Azure CosmosDB", e)
            error_logger.error(
                json.dumps(
                    {
                        "user_id": user_id,
                        "user_message": user_message,
                        "answer": answer,
                        "reasoning": debug_string,
                        "timestamp": date,
                        "error": str(e),
                    }
                )
            )

        total_time = time.time() - time_begin
        latency_dict["total"] = total_time

        # Save all latency steps to latency.log
        latency_logger.info(
            json.dumps(
                {
                    **latency_dict,
                    "user_id": user_id,
                    "user_message": user_message,
                    "answer": answer,
                    "timestamp": date,
                }
            )
        )

        # If the debug is not requested, returns the answer
        if not self.return_debug:
            return answer
        # If the debug is requested, returns the answer and the debug string
        return f"{debug_string}\nAnswer: {answer}"

    @staticmethod
    def get_num_tokens(text: str) -> int:
        """
        Returns the number of tokens in the text.
        """
        encoding = tiktoken.encoding_for_model(settings.encoding_model)
        return len(encoding.encode(text))

    @staticmethod
    def get_reasoning(prompt: str, stop: List[str] = None) -> str:
        """
        Sends a request to prompt_answerer to get a reasoning.
        Args:
            - prompt: the prompt to be sent to prompt_answerer.
            - stop: the stop tokens list.
        returns:
            - the reasoning for the message (str).
        """
        if stop is None:
            stop = ["\n"]
        # Returns the reasoning for the message
        body = {
            "service": "ChatBot",
            "prompt": [{"role": "user", "content": prompt}],
            "model": settings.encoding_model,
            "configurations": {
                "temperature": 0,
                "max_tokens": 512,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "stop": stop,
            },
        }
        response = requests.post(settings.completion_endpoint, json=body)
        if not response.ok:
            error_logger.error(
                json.dumps(
                    {
                        "prompt": prompt,
                        "stop": stop,
                        "status_code": response.status_code,
                        "service": "prompt_answerer",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            )
            raise Exception("Error in reasoning")
        return response.json()["text"].strip()

    def get_observation(self, action: str, index: str):
        """
        Returns the observation for the message.
        Args:
            - action: string with the action to be performed.
            - index: the index to be used for the search (FAQ and NSX).
        Returns:
            - the observation for the message (str).
        """
        # Extracts the query from the action
        try:
            query = re.search("(?<=\\[).*(?=\\])|(?<=\\[).*", action).group()
        except Exception:
            query = action

        # Tries to find a similar query in the FAQ
        answer = self.get_faq_answer(query, index)

        if answer == "irrespondível":
            # Get the first document from NSX
            answer = self.get_nsx_answer(query, index)

            if self.verbose:
                print("NSX: ", answer)

        return answer

    def get_nsx_answer(self, query: str, index: str):
        """
        Gets the first document from NSX.
        Args:
            - query: the query to be sent to NSX.
            - index: the index to be used for the search.
        Returns:
            - the first document from NSX (str).
        """
        # Parameters for the request
        params = {
            "index": index,
            "query": query,
            "max_docs_to_return": 1,
            "format_response": True,
        }
        # Headers for the request
        headers = {
            "Authorization": f"APIKey {settings.api_key}",
        }
        response = requests.get(settings.nsx_endpoint, params=params, headers=headers)
        if response.ok:
            response = response.json()
            return response["response_reranker"][0]["paragraphs"][0]
        return "Não foi possível encontrar uma resposta."

    def get_faq_answer(self, query: str, index: str):
        """
        Search for an answer in the FAQ.
        Args:
            - query: the query to be used in the search.
            - index: the FAQ to be used for the search.
        Returns:
            - the answer for the query (str).
        """
        # TODO: Check for prompt length before sending the request
        # TODO: How to deal with large FAQs?
        # Creates the prompt based on the FAQ
        prompt = self.faq_prompt.format(
            queries="\n".join([question for question in self.faq[index]]),
            search_input=query,
        )
        # Gets the reasoning for the prompt
        response = self.get_reasoning(prompt, stop=["\n"])

        # If there is an answer
        if not response.startswith(" irrespondível"):
            # Returns the exact answer if it is in the FAQ
            if response in self.faq:
                if self.verbose:
                    print("Found the answer in the FAQ")
                return self.faq[response]
            # TODO: Improve substring search
            else:  # If the query is in the answer, returns the answer
                for query in self.faq:
                    if query in response:
                        if self.verbose:
                            print("Found the answer in the FAQ")
                        return self.faq[query]
        return "irrespondível"

    def get_chat_history(self, user_id: str, index: str) -> str:
        """
        Gets the chat history for the user using the memory_handler.
        Args:
            - user_id: the id of the user (could be the number).
        Returns:
            - the chat history for the user (str).
        """
        chat_history = memory_handler.retrieve_history(user_id, index)
        # If there is no history
        if chat_history is None:
            return ""

        # If the chat history is too long, makes a summary
        # TODO: Experiments to check if making a summary is a good idea
        if self.get_num_tokens(chat_history) > settings.max_tokens_chat_history:
            summary = self.make_summary(chat_history)
            memory_handler.clear_history(user_id, index)
            memory_handler.save_history(
                user_id, index, f"Resumo de conversas anteriores: {summary}\n"
            )
        return chat_history

    def make_summary(self, chat_history: str) -> str:
        """
        Creates a summary for the chat history.
        Args:
            - chat_history: the chat history to be summarized.
        Returns:
            - the summary for the chat history (str).
        """
        # TODO: Check for prompt length before sending the request
        prompt = self.summary_prompt.format(chat_history=chat_history)

        # Gets the reasoning for the prompt
        summary = self.get_reasoning(prompt)

        if self.verbose:
            print(f"Summary: {summary}")
        return summary

    @staticmethod
    def is_the_message_harmful(user_message: str) -> bool:
        """
        Checks if the message is harmful using the moderation service.
        Args:
            - user_message: the message sent by the user.
        Returns:
            - True if the message is harmful, False otherwise.
        """
        body = {"service": "ChatBot", "input": [user_message]}
        response = requests.post(settings.moderation_endpoint, json=body)
        if response.ok:
            response = response.json()
            if response["results"][0]["flagged"]:
                return True
            return False
        # TODO: Log if the message comes from the user or the assistant
        error_logger.error(response.text)
        raise Exception("Error in moderation")
