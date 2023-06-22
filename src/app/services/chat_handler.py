import json
import time
import traceback
from datetime import datetime
from glob import glob
from typing import Dict, List, Tuple

import requests
import tiktoken

from app.schemas.database_item import Item
from app.schemas.search import SearchTool
from app.services.database import DBManager
from app.services.memory_handler import MemoryHandler
from app.utils.timeout_management import RequestMethod, retry_request_with_timeout
from settings import settings
from app.prompts import base_prompt

from .build_timed_logger import build_timed_logger

chat_logger = build_timed_logger("chat_logger", "chat.log")
error_logger = build_timed_logger("error_logger", "error.log")
harmful_logger = build_timed_logger("harmful_logger", "harmful.log")
latency_logger = build_timed_logger("latency_logger", "latency.log")


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

    def __init__(
        self,
        db: DBManager,
        memory: MemoryHandler,
        model: str = settings.reasoning_model,
        verbose: bool = False,
        return_debug: bool = False,
        dev_mode: bool = False,
        disable_faq: bool = True,
        disable_memory: bool = False,
        use_nsx_sense: bool = False,
    ):
        """
        Args:
            - db: The database manager. Used for storing the chat answers in a permanent database.
            - memory: The memory handler. Used for storing the chat history for each user.
            - verbose: if True, prints all the steps of the reasoning.
            - return_debug: if True, returns the debug string containing
            all reasoning steps.
            - dev_mode: With this flag, the chatbot can accept special messages to control its behavior
            - disable_faq: With this flag, the chatbot will bypass the FAQ search feature
            - disable_memory: With this flag, chatbot will not use chat_history feature
            - use_nsx_sense: With this flag, chatbot will use nsx_sense
            to get the answer instead of nsx_seach (EXPERIMENTAL)
        """
        # Loads all prompts
        prompts = base_prompt.prompts

        # TODO: add support for other languages
        self.language = "pt"

        # Base prompts
        self.chat_prompt = prompts[self.language]["chat_prompt"]
        self.faq_prompt = prompts[self.language]["faq_prompt"]
        self.summary_prompt = prompts[self.language]["new_summary_prompt"]

        # Useful prompt snippets:
        self.answer_not_found = prompts[self.language]["answer_not_found"]
        self.unanswerable_search = prompts[self.language]["unanswerable_search"]
        self.forced_finish = prompts[self.language]["forced_finish"]

        # Loads the FAQs
        self.faq = self.load_faqs("app/faqs")

        # Feature managers
        self._db = db
        self._memory = memory
        self._model = model

        # Verbose and debug
        self.verbose = verbose
        self.return_debug = return_debug
        self.disable_faq = disable_faq
        self.disable_memory = disable_memory
        self.dev_mode = dev_mode
        self.use_nsx_sense = use_nsx_sense

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

    def dev_mode_action(self, message: str) -> str:
        """Manage dev mode special actions
        Args:
            - message: message sent by the user
        Returns:
            - response for the user message
        """
        if "#model" in message:
            models_str = ", ".join(settings.available_models)
            return (
                "Digite o nome de um dos modelos disponíveis.\n"
                f"Modelos disponíves:\n{models_str}"
            )

        # Remove "#" to find the correct model
        model = message[1:].strip()
        if model in settings.available_models:
            self._model = model
            return (
                f"A partir de agora utilizarei o {self._model} "
                "para formular o meu raciocínio e respostas!"
            )

        if "#nsx_sense" in message:
            self.use_nsx_sense = not self.use_nsx_sense
            return f"NSX Sense: {('enabled' if self.use_nsx_sense else 'disabled')}"

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

        if user_message.startswith("#") and self.dev_mode:
            return self.dev_mode_action(user_message)

        # Stores all reasoning steps for debugging
        debug_string = ""

        time_begin = time.time()
        # Stores the latency for each step
        latency_dict = {}

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Restarts the used faq, as a new message is going to be processed
        used_faq = []

        # Checks if the user message is harmful
        if self.is_the_message_harmful(user_message):
            harmful_logger.info(
                json.dumps(
                    {"user_id": user_id, "message": user_message, "timestamp": date}
                )
            )
            return "Mensagem ignorada por conter conteúdo ofensivo."

        # Gets the chat history from memory
        if not self.disable_memory:
            time_pre_memory = time.time()
            chat_history = self.get_chat_history(user_id, chatbot_id, index)
            latency_dict["memory_get"] = time.time() - time_pre_memory
        else:
            chat_history = ""

        index_domain = self._db.get_index_information(index, "domain")
        if not index_domain:
            index_domain = "documentos em minha base de dados"
        full_chat_prompt = self.chat_prompt.format(domain=index_domain)
        prompt = f"{full_chat_prompt}\n{chat_history}\nMensagem: {user_message}\n"

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
                thought = reasoning.split("\n")[0]
                action = self.get_reasoning(
                    f"{reasoning_prompt}Pensamento {i}: {thought}\nAção {i}:",
                    stop=[f"Observação {i}:", "Mensagem:"],
                )

            try:
                action_type, action_input = action.split(f"\nTexto da ação {i}:")
            except Exception:
                # Occurs if there is no action input
                action_type = action.split("\n")[0]
                action_input = self.get_reasoning(
                    f"{reasoning_prompt}Pensamento {i}: {thought}\nAção {i}:{action_type}\nTexto da Ação {i}:",
                    stop=[f"Observação {i}:", "Mensagem:"],
                )

            thought, action_type, action_input = (
                thought.strip(),
                action_type.strip(),
                action_input.strip(),
            )

            # Prints the reasoning
            if self.verbose:
                print(f"Thought {i}: {thought}")
                print(f"Action {i}: {action_type}")
                print(f"Input of Action {i}: {action_input}")
            debug_string += f"Pensamento {i}: {thought}\nAção {i}: {action_type}\nTexto da Ação {i}: {action_input}\n"

            if action_type.startswith("Finalizar"):
                done = True
                answer = action_input
                break
            else:

                # In case the next observation fails to retrieve useful information,
                # we will induce the model to try again if there is still room for searches
                # The -1 accounts for the last Finish step after the searches
                searches_left = settings.max_num_reasoning - i - 1

                # If the action is not to finish, gets an observation
                observation, tool = self.get_observation(
                    action_input, index, used_faq, latency_dict, api_key, searches_left
                )

                if self.verbose:
                    print(f"Observation {i} (FROM {tool}): {observation}")

                debug_string += f"Observação {i} ({tool}): {observation}\n"

            # Adds the thought, action and observation to the iteration string
            iteration_string = f"Pensamento {i}: {thought}\nAção {i}: {action_type}\nTexto da Ação {i}: {action_input}\nObservação {i}: {observation}\n"

            # Checks if the number of tokens is under the limit
            total_tokens = self.get_num_tokens(prompt + iteration_string)
            if total_tokens > settings.max_tokens_prompt:
                break

            # Adds the iteration string to the prompt
            prompt += iteration_string

        # If the reasoning is not done, forces the finish
        if not done:
            answer = self.get_reasoning(self.forced_finish.format(prompt=prompt))
            if self.verbose:
                print(f"Finalizar Forçado: {answer}")
            debug_string += f"Finalizar Forçado: {answer}\n"

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
        if not self.disable_memory:
            time_pre_memory_history = time.time()
            self._memory.save_history(
                user_id,
                chatbot_id,
                index,
                f"Usuário: {user_message}\nAssistente: {answer}\n",
            )
            latency_dict["memory_set"] = time.time() - time_pre_memory_history

        chat_logger.info(
            json.dumps(
                {
                    "user_id": user_id,
                    "user_message": user_message,
                    "index": index,
                    "index_domain": index_domain,
                    "reasoning": debug_string,
                    "answer": answer,
                    "timestamp": date,
                },
                ensure_ascii=False,
            )
        )

        # Save user message and chatbot answer to database
        try:
            time_pre_chat_history_db = time.time()
            self._db.upsert_chat_history(
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
            latency_dict["chat_history_db"] = time.time() - time_pre_chat_history_db
        except Exception as e:
            if self.verbose:
                print("Error sending to database", e)
            error_logger.error(
                json.dumps(
                    {
                        "user_id": user_id,
                        "user_message": user_message,
                        "answer": answer,
                        "reasoning": debug_string,
                        "timestamp": date,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
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

    def get_reasoning(self, prompt: str, stop: List[str] = None) -> str:
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
            "model": self._model,
            "configurations": {
                "temperature": 0,
                "max_tokens": 512,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "stop": stop,
            },
        }
        try:
            response = retry_request_with_timeout(
                RequestMethod.POST,
                settings.completion_endpoint,
                body=body,
                request_timeout=settings.reasoning_timeout,
            )
            if not response.ok:
                error_logger.error(
                    json.dumps(
                        {
                            "prompt": prompt,
                            "stop": stop,
                            "status_code": response.status_code,
                            "service": "prompt_answerer",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        },
                        ensure_ascii=False,
                    )
                )
                raise Exception("Error in reasoning")
            return response.json()["text"].strip()
        except requests.exceptions.Timeout as te:
            raise te
        except Exception as e:
            raise e

    def get_observation(
        self,
        query: str,
        index: str,
        used_faq: list,
        latency_dict: Dict[str, float],
        api_key: str,
        searches_left: int,
    ) -> Tuple[str, SearchTool]:
        """
        Returns the observation for the message.

        Args:
            - query: string with the query to be searched.
            - index: the index to be used for the search (FAQ and NSX).
            - used_faq: list of queries that have already been used.
            - latency_dict: dictionary containing the latency for each step.
            - api_key: the user's API key to be used for the NSX API.
            - searches_left: number of searches the model can still do for the current message.

        Returns:
            str: The answer to the query, if the query is in the FAQ, or
            List: A list with the top 5 documents from NSX, where the first document is used as the answer to the query.
        """

        # Tries to find a similar query in the FAQ
        if not self.disable_faq:
            time_faq_answer = time.time()
            observation = self.get_faq_answer(query, index, used_faq, latency_dict)
            latency_dict["faq_answer"] = time.time() - time_faq_answer
            tool = SearchTool.FAQ
        else:
            observation = "irrespondível"

        if observation == "irrespondível":
            if self.use_nsx_sense:
                time_nsx_sense_answer = time.time()
                observation = self.get_nsx_sense_answer(
                    query, index, api_key, searches_left
                )
                latency_dict["nsx_sense_answer"] = time.time() - time_nsx_sense_answer
                tool = SearchTool.SENSE
            else:
                # Get the first document from NSX
                time_nsx_answer = time.time()
                observation = self.get_nsx_answer(query, index, api_key, searches_left)
                latency_dict["nsx_answer"] = time.time() - time_nsx_answer
                tool = SearchTool.NSX

        return observation, tool

    def get_nsx_answer(
        self,
        query: str,
        index: str,
        api_key: str,
        searches_left: int,
        num_docs: int = 1,
    ) -> str:
        """
        Gets the first document from NSX.

        Args:
            - query: the query to be sent to NSX.
            - index: the index to be used for the search.
            - api_key: the user's API key to be used for the NSX API.
            - searches_left: number of searches the model can still do for the current message.
            - num_docs: number of documents to be returned by NSX.

        Returns:
            str: The answer to the query (with concatenated num_docs from NSX) or
            str: A string telling the chatbot that the answer was not found on NSX.
        """
        # Parameters for the request
        params = {
            "index": index,
            "query": query,
            "max_docs_to_return": settings.max_docs_to_return,
            "format_response": False,
        }
        # Headers for the request
        headers = {
            "Authorization": f"APIKey {api_key}",
        }
        try:
            response = retry_request_with_timeout(
                RequestMethod.GET,
                settings.nsx_endpoint,
                params=params,
                headers=headers,
                request_timeout=settings.nsx_timeout,
            )
        except requests.exceptions.Timeout as te:
            raise te
        if response.ok:
            response = response.json()
            response_len = len(response["response_reranker"])
            if response_len > 0:
                docs = ""
                for i in range(min(num_docs, response_len)):
                    docs += f"{response['response_reranker'][i]['paragraphs'][0]}\n"
                return docs.strip()
            elif searches_left == 0:
                return self.unanswerable_search
            else:
                return self.answer_not_found
        raise Exception(f"Error in NSX: {response.json()['message']}")

    def get_nsx_sense_answer(
        self, query: str, index: str, api_key: str, searches_left: int
    ) -> str:
        """
        Gets a response using NSX sense.

        Args:
            - query: the query to be sent to NSX.
            - index: the index to be used for the search.
            - api_key: the user's API key to be used for the NSX API.
            - searches_left: number of searches the model can still do for the current message.

        Returns:
            - A response built with NSX Sense.
        """
        # Parameters for the request
        params = {
            "index": index,
            "query": query,
            "max_docs_to_return": settings.max_docs_to_return,
            "format_response": False,
        }
        # Headers for the request
        headers = {
            "Authorization": f"APIKey {api_key}",
        }
        try:
            response = retry_request_with_timeout(
                RequestMethod.GET,
                settings.nsx_endpoint,
                params=params,
                headers=headers,
                request_timeout=settings.nsx_sense_timeout,
            )
        except requests.exceptions.Timeout as te:
            raise te
        if not response.ok:
            raise Exception(f"Error in NSX: {response.json()['message']}")

        response = response.json()

        documents = [
            {"paragraphs": response_reranker["paragraphs"][0]}
            for response_reranker in response["response_reranker"]
        ]

        if len(documents) == 0:
            if searches_left == 0:
                return self.unanswerable_search
            else:
                return self.answer_not_found

        answer = self.answer_from_docs(query, index, documents, searches_left)

        return answer

    def answer_from_docs(
        self, query: str, index: str, documents: list, searches_left: int
    ):
        """
        Builds an answer for the query based on the documents, using MultidocQA.

        Args:
            - query: the query that is going to be answered
            - index: NSX index from which the documents were retrieved
            - documents: list of NSX response_reranker dicts
            - searches_left: number of searches the model can still do for the current message.

        Returns:
            - An answer for the query based on the documents
        """

        params = {
            "query": query,
            "documents": documents,
            "language": settings.chatbot_language,
            "index": index,
        }

        response = requests.post(settings.nsx_sense_endpoint, json=params)

        if not response.ok:
            raise Exception(f"Error in MultidocQA: {response.json()['msg']}")

        response = response.json()["pred_answer"]

        if "irrespondível" in response.lower():
            if searches_left == 0:
                return self.unanswerable_search
            else:
                return self.answer_not_found
        else:
            return response

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
            return self.faq[index][response]

        # If the response does not match any question
        # tries to check if the responses has an unexpected format
        # Returns the answer of the first to_question that appears in the response
        for question in top_questions:
            if question in response:
                used_faq.append(question)
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
                        "traceback": traceback.format_exc(),
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
        chat_history = self._memory.retrieve_history(user_id, chatbot_id, index)
        # If there is no history
        if chat_history is None:
            return ""

        # If the chat history is too long, makes a summary
        # TODO: Experiments to check if making a summary is a good idea
        if self.get_num_tokens(chat_history) > settings.max_tokens_chat_history:
            summary = self.make_summary(chat_history)
            self._memory.clear_history(user_id, chatbot_id, index)
            self._memory.save_history(
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
