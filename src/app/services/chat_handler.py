import json
import re
import time
from datetime import datetime
from glob import glob
from typing import Dict, List

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
        self.message_extractor_prompt = prompts[self.language][
            "message_extractor_prompt"
        ]

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

    def message_extractor(self, action: str) -> str:

        """
        Extracts the input message from an action using the language model.

        Args:
            - action: action from with we need to extract an input message

        Returns:
            - string containing the extracted action
        """

        prompt = self.message_extractor_prompt + action + "\n\nResposta:"

        return self.get_reasoning(prompt)

    def get_response(
        self,
        user_message: str,
        user_id: str,
        chatbot_id: str = "",
        index: str = settings.search_index,
        api_key: str = settings.api_key,
    ) -> str:
        """
        Returns the response for the user message.
        Args:
            - user_message: the message sent by the user.
            - user_id: the id of the user (used to access the chat history).
            - chatbot_id: the id of the chatbot (used to access the chat history).
            - index: the index to be used for the search (FAQ and NSX).
            - api_key: the user's API key to be used for the NSX API.
        """
        # Stores all reasoning steps for debugging
        debug_string = ""

        time_begin = time.time()
        # Stores the latency for each step
        latency_dict = {}

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        used_faq = (
            []
        )  # Restarts the used faq, as a new message is going to be processed

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
        chat_history = self.get_chat_history(user_id, chatbot_id, index)
        latency_dict["redis_get"] = time.time() - time_pre_redis

        prompt = f"{self.chat_prompt}\n{chat_history}\nMensagem: {user_message}\n"

        # Checks if there is enough tokens available to process the message:
        if self.get_num_tokens(prompt) > settings.max_tokens_prompt:
            return "Sua mensagem é muito longa para que eu consiga processá-la adequadamente. Por favor, escreva-a de modo mais conciso."

        # Starts the reasoning loop
        done = False
        time_pre_reasoning = time.time()
        for i in range(1, settings.max_num_reasoning + 1):
            # Adds the reasoning to the prompt
            reasoning_prompt = f"{prompt}Pensamento {i}:"
            reasoning = self.get_reasoning(
                prompt=reasoning_prompt, stop=[f"Observação {i}:", "Mensagem:"]
            )
            try:
                thought, action = reasoning.split(f"\nAção {i}:")
            except Exception:
                # Occurs if there is no action
                thought = reasoning.strip().split("\n")[0]
                action = self.get_reasoning(
                    f"{reasoning_prompt}Pensamento {i}: {thought}\nAção {i}:",
                    stop=["\n"],
                )

            # Prints the reasoning
            if self.verbose:
                print(f"Thought {i}: {thought}")
                print(f"Action {i}: {action}")
            debug_string += f"Thought {i}: {thought}\nAction {i}: {action}\n"

            try:
                # Regex for matching what's between square brackets, or after the opening square bracket (sometimes the model forgets to close it).
                action_input = re.search(
                    "(?<=[\[(<{\"'])(.|\n)*(?=[\])>}\"'])|(?<=[\[(<{\"'])(.|\n)*",
                    action,
                ).group()
            except Exception:
                # In the case that the regex fails, we use the LLM for extracting the desired text
                action_input = self.message_extractor(action)

            if action.startswith(" Finalizar"):
                done = True
                answer = action_input
                break
            else:
                # If the action is not to finish, gets an observation
                observation = self.get_observation(
                    action_input, index, used_faq, latency_dict, api_key
                )

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
                f"{prompt}Pensamento Final: Máximo número de iteracões atingido. Devo responder com as informações que tenho até agora.\nAção: Finalizar["
            )
            if self.verbose:
                print(f"Finalizar Forçado: {action}")
            debug_string += f"Finalizar Forçado: {action}\n"

            try:
                # Regex for extracting the closing square brancket:
                answer = re.search("(.|\n)*(?=\])", action).group()
            except Exception:
                # In the case that the model might have forgotten of adding the closing square bracket:
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
            user_id,
            chatbot_id,
            index,
            f"Usuário: {user_message}\nAssistente: {answer}\n",
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

        Returns:
            - the reasoning for the message (str).
        """
        if stop is None:
            stop = ["\n"]
        # Returns the reasoning for the message
        body = {
            "service": "ChatBot",
            "prompt": [{"role": "user", "content": prompt}],
            "model": settings.reasoning_model,
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

    def get_observation(
        self,
        query: str,
        index: str,
        used_faq: list,
        latency_dict: Dict[str, float],
        api_key: str,
    ) -> str:
        """
        Returns the observation for the message.

        Args:
            - query: string with the query to be searched.
            - index: the index to be used for the search (FAQ and NSX).
            - used_faq: list of queries that have already been used.
            - latency_dict: dictionary containing the latency for each step.
            - api_key: the user's API key to be used for the NSX API.

        Returns:
            - information related to the query.
        """

        # Tries to find a similar query in the FAQ
        time_faq_answer = time.time()
        observation = self.get_faq_answer(query, index, used_faq, latency_dict)
        latency_dict["faq_answer"] = time.time() - time_faq_answer

        if observation == "irrespondível":
            # Get the first document from NSX
            time_nsx_answer = time.time()
            observation = self.get_nsx_answer(query, index, api_key)
            latency_dict["nsx_answer"] = time.time() - time_nsx_answer

            if self.verbose:
                print("NSX: ", observation)

        return observation

    def get_nsx_answer(self, query: str, index: str, api_key: str) -> str:
        """
        Gets the first document from NSX.

        Args:
            - query: the query to be sent to NSX.
            - index: the index to be used for the search.
            - api_key: the user's API key to be used for the NSX API.

        Returns:
            - the first document from NSX.
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
            "Authorization": f"APIKey {api_key}",
        }
        response = requests.get(settings.nsx_endpoint, params=params, headers=headers)
        if response.ok:
            response = response.json()
            if len(response["response_reranker"]) > 0:
                return response["response_reranker"][0]["paragraphs"][0]
            else:
                return "Não foi possível encontrar sobre isso na minha base de dados"
        raise Exception(f"Error in NSX: {response.json()['message']}")

    def get_faq_answer(
        self, query: str, index: str, used_faq: list, latency_dict: Dict[str, float]
    ) -> str:
        """
        Search for an answer in the FAQ.

        Args:
            - query: the query to be used in the search.
            - index: the FAQ to be used for the search.
            - used_faq: list containing queries from the faq that have already been used
            - latency_dict: dictionary containing the latency for each step.

        Returns:
            - the answer for the query.
        """

        # Gets the top questions from the FAQ that are similar to the query
        time_nsx_score = time.time()
        try:
            top_questions = self.get_top_faq_questions(query, self.faq[index])
        except Exception:
            return "irrespondível"
        latency_dict["nsx_score"] = time.time() - time_nsx_score

        queries = ""
        prompt_size = self.get_num_tokens(self.faq_prompt + query)

        for question in top_questions:
            question_size = self.get_num_tokens(question)
            if (
                question not in used_faq
                and (prompt_size + question_size) < settings.max_tokens_faq_prompt
            ):
                queries += question + "\n"
                prompt_size += question_size

        prompt = self.faq_prompt.format(
            queries=queries,
            search_input=query,
        )

        # Gets the reasoning for the prompt
        time_faq_selection = time.time()
        response = self.get_reasoning(prompt, stop=["\n"])
        latency_dict["faq_selection"] = time.time() - time_faq_selection

        # Returns the exact answer if the question is in the FAQ
        if response in self.faq[index]:
            used_faq.append(response)
            if self.verbose:
                print("Found the answer in the FAQ")
            return self.faq[index][response]

        # If the response does not match any question
        # tries to check if the responses has an unexpected format
        # Returns the answer of the first to_question that appears in the response
        for question in top_questions:
            if question in response:
                used_faq.append(question)
                if self.verbose:
                    print("Found the answer in the FAQ")
                return self.faq[index][question]

        return "irrespondível"

    def get_top_faq_questions(self, query: str, faq: Dict[str, str]) -> List[str]:
        """Get the top questions from the FAQ that are similar to the query using nsx inference route.
        Args:
            - query: the query to be used in the search.
            - faq: the FAQ to be used for the search.
        Returns:
            - the top questions from the FAQ that are similar to the query.
        """
        payload = {
            "query": query,
            "documents": [question for question in faq],
            "language": self.language,
        }
        try:
            response = requests.post(settings.nsx_score_endpoint, json=payload)
            response.raise_for_status()
            scores = [result["score"] for result in response.json()["results"]]
            top_questions = [
                question
                for _, question in sorted(zip(scores, faq), reverse=True)[
                    : settings.max_faq_questions
                ]
            ]
            return top_questions
        except requests.HTTPError as e:
            error_logger.error(
                json.dumps(
                    {
                        "error_msg": str(e),
                        "status_code": response.status_code,
                        "service": "nsx_score",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            )
            raise Exception("error when trying to rank faq questions")

    def get_chat_history(self, user_id: str, chatbot_id: str, index: str) -> str:
        """
        Gets the chat history for the user using the memory_handler.

        Args:
            - user_id: the id of the user.
            - chatbot_id: the id of the chatbot.
        Returns:
            - the chat history for the user (str).
        """
        chat_history = memory_handler.retrieve_history(user_id, chatbot_id, index)
        # If there is no history
        if chat_history is None:
            return ""

        # If the chat history is too long, makes a summary
        # TODO: Experiments to check if making a summary is a good idea
        if self.get_num_tokens(chat_history) > settings.max_tokens_chat_history:
            summary = self.make_summary(chat_history)
            memory_handler.clear_history(user_id, chatbot_id, index)
            memory_handler.save_history(
                user_id,
                chatbot_id,
                index,
                f"Resumo de conversas anteriores: {summary}\n",
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
