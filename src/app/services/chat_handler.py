import json
import time
import traceback
from datetime import datetime
from typing import Dict, Tuple

import requests

from app.prompts import base_prompt
from app.schemas.database_item import Item
from app.schemas.search import SearchTool
from app.services.database import DBManager
from app.services.dialog_360 import post_360_dialog_text_message
from app.services.faq_search import FAQSearchTool
from app.services.memory_handler import MemoryHandler
from app.services.nsx_search import NSXSearchTool, NSXSenseSearchTool
from app.utils import model_utils
from app.utils.exceptions import PromptAnswererError
from app.utils.model_utils import (
    chat_logger,
    error_logger,
    harmful_logger,
    latency_logger,
)
from settings import settings


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
        self.summary_prompt = prompts[self.language]["new_summary_prompt"]

        # Useful prompt snippets:
        self.forced_finish = prompts[self.language]["forced_finish"]

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

        self.faq_search = FAQSearchTool(self.language, self._model)
        self.nsx_search = NSXSearchTool(self.language, settings.api_key)
        self.nsx_sense_search = NSXSenseSearchTool(self.language, settings.api_key)

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

    def whatsapp_commands(
        self,
        user_message: str,
        user_id: str,
        chatbot_id: str,
        index: str,
    ) -> str:
        """Manage whatsapp commands
        Args:
            - user_message: message sent by the user
            - user_id: the user id
            - chatbot_id: the chatbot id
            - index: the index to search for answers
        Returns:
            - response for the user message
        """
        if "#reset" == user_message.strip():
            self._memory.reset_chatbot(user=user_id, chatbot_id=chatbot_id)
            return "Memória do chatbot limpa!"
        elif "#version" == user_message.strip():
            return f"Versão do chatbot: {settings.version}"
        elif "#debug" == user_message.strip():
            self._memory.set_user_configs(
                user=user_id,
                chatbot_id=chatbot_id,
                configs={
                    "whatsapp_verbose": 1,
                },
            )
            return "Modo verboso habilitado!"
        elif "#forget" == user_message.strip():
            self._memory.clear_history(user=user_id, chatbot_id=chatbot_id, index=index)
            return f"A memória no índice {index} foi apagada!"
        elif "#help" == user_message.strip():
            return (
                "Comandos disponíveis:\n"
                "#reset: Reinicia o chatbot\n"
                "#forget: Limpa a memória\n"
                "#version: Exibe a versão do chatbot\n"
                "#debug: Habilita o modo verboso\n"
            )
        else:
            return "Comando não reconhecido!"

    def get_response(
        self,
        user_message: str,
        user_id: str,
        chatbot_id: str = "",
        index: str = settings.search_index,
        api_key: str = settings.api_key,
        whatsapp_verbose: bool = False,
        bm25_only: bool = False,
    ) -> str:
        """
        Returns the response for the user message.
        Args:
            - user_message: the message sent by the user.
            - user_id: the id of the user (used to access the chat history).
            - chatbot_id: the id of the chatbot (used to access the chat history).
            - index: the index to be used for the search (FAQ and NSX).
            - api_key: the user's API key to be used for the NSX API.
            - whatsapp_verbose: if True, prints all the steps of the reasoning.
            - bm25_only: if True, only uses BM25 to search for answers.
        """
        debug_string = ""
        if user_message.startswith("#") and self.dev_mode:
            return self.dev_mode_action(user_message)
        elif user_message.startswith("#"):  # whatsapp commands
            return self.whatsapp_commands(
                user_message=user_message,
                user_id=user_id,
                chatbot_id=chatbot_id,
                index=index,
            )

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

        # Checks if there is enough tokens available to process the message:
        if (
            model_utils.get_num_tokens(user_message)
            + model_utils.get_num_tokens(chat_history)
        ) > settings.max_tokens_prompt:
            return "Sua mensagem é muito longa para que eu consiga processá-la adequadamente. Por favor, escreva-a de modo mais conciso."

        time_pre_reasoning = time.time()
        answer, debug_string = self.find_answer(
            user_message,
            chat_history,
            index,
            used_faq,
            latency_dict,
            api_key,
            debug_string,
            destinatary=user_id,
            d360_number=chatbot_id,
            whatsapp_verbose=whatsapp_verbose,
            bm25_only=bm25_only,
        )

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

        if not self.return_debug:
            return answer
        # If the debug is requested, returns the answer and the debug string
        return f"{debug_string}\nAnswer: {answer}"

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
        # If whatsapp_verbose is True, it is expected that the destinatary and d360_number are not None
        if whatsapp_verbose and (destinatary is None or d360_number is None):
            raise Exception(
                "If whatsapp_verbose is True, destinatary and d360_number must not be None"
            )

        index_domain = (
            self._db.get_index_information(index, "domain")
            or settings.default_index_domain
        )

        full_chat_prompt = self.chat_prompt.format(domain=index_domain)
        prompt = f"{full_chat_prompt}\n{chat_history}\nMensagem: {user_message}\n"

        # Stores all reasoning steps for debugging
        debug_string = ""

        # Starts the reasoning loop
        done = False
        for i in range(1, settings.max_num_reasoning + 1):
            # Adds the reasoning to the prompt
            reasoning_prompt = f"{prompt}Pensamento {i}:"
            reasoning = model_utils.get_reasoning(
                prompt=reasoning_prompt,
                model=self._model,
                stop=[f"Observação {i}:", "Mensagem:"],
            )

            try:
                thought, action = reasoning.split(f"\nAção {i}:")
            except Exception:
                # Occurs if there is no action
                thought = reasoning.split("\n")[0]
                action = model_utils.get_reasoning(
                    f"{reasoning_prompt}Pensamento {i}: {thought}\nAção {i}:",
                    model=self._model,
                    stop=[f"Observação {i}:", "Mensagem:"],
                )

            if whatsapp_verbose:
                post_360_dialog_text_message(
                    destinatary=destinatary,
                    message=f"Pensamento {i}: {thought}.\nAção {i}: {action}",
                    d360_number=d360_number,
                )

            try:
                action_type, action_input = action.split(f"\nTexto da ação {i}:")
            except Exception:
                # Occurs if there is no action input
                action_type = action.split("\n")[0]
                action_input = model_utils.get_reasoning(
                    f"{reasoning_prompt}Pensamento {i}: {thought}\nAção {i}:{action_type}\nTexto da Ação {i}:",
                    model=self._model,
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
                    action_input,
                    index,
                    used_faq,
                    latency_dict,
                    api_key,
                    searches_left,
                    settings.num_docs_search,
                    bm25_only,
                )

                if self.verbose:
                    print(f"Observation {i} (FROM {tool}): {observation}")

                if whatsapp_verbose:
                    post_360_dialog_text_message(
                        destinatary=destinatary,
                        message=f"Observação {i} (DE {tool}):\n{observation}",
                        d360_number=d360_number,
                    )

                debug_string += f"Observação {i} ({tool}): {observation}\n"

            # Adds the thought, action and observation to the iteration string
            iteration_string = f"Pensamento {i}: {thought}\nAção {i}: {action_type}\nTexto da Ação {i}: {action_input}\nObservação {i}: {observation}\n"

            # Checks if the number of tokens is under the limit
            total_tokens = model_utils.get_num_tokens(prompt + iteration_string)
            if total_tokens > settings.max_tokens_prompt:
                break

            # Adds the iteration string to the prompt
            prompt += iteration_string

        # If the reasoning is not done, forces the finish
        if not done:
            answer = model_utils.get_reasoning(
                self.forced_finish.format(prompt=prompt), self._model
            )
            if self.verbose:
                print(f"Finalizar Forçado: {answer}")
            debug_string += f"Finalizar Forçado: {answer}\n"

            if whatsapp_verbose:
                post_360_dialog_text_message(
                    destinatary=destinatary,
                    message=f"Finalizar Forçado: {answer}\n",
                    d360_number=d360_number,
                )

        return answer, debug_string

    def get_observation(
        self,
        query: str,
        index: str,
        used_faq: list,
        latency_dict: Dict[str, float],
        api_key: str,
        searches_left: int,
        num_docs: int,
        bm25_only: bool = False,
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
            - bm25_only: if True, only uses BM25 to search for answers.

        Returns:
            str: The answer to the query, if the query is in the FAQ, or
            List: A list with the top 5 documents from NSX, where the first document is used as the answer to the query.
        """

        if not self.disable_faq:
            time_faq_answer = time.time()
            observation = self.faq_search.search(query, index, used_faq, latency_dict)
            latency_dict["faq_answer"] = time.time() - time_faq_answer
            tool = SearchTool.FAQ
        else:
            observation = "irrespondível"

        if observation == "irrespondível":
            if self.use_nsx_sense:
                time_nsx_sense_answer = time.time()
                observation = self.nsx_sense_search.search(
                    query, index, api_key, searches_left, bm25_only
                )
                latency_dict["nsx_sense_answer"] = time.time() - time_nsx_sense_answer
                tool = SearchTool.SENSE
            else:
                # Get the first document from NSX
                time_nsx_answer = time.time()
                observation = self.nsx_search.search(
                    query, index, api_key, searches_left, num_docs, bm25_only
                )
                latency_dict["nsx_answer"] = time.time() - time_nsx_answer
                tool = SearchTool.NSX

        return observation, tool

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
        if model_utils.get_num_tokens(chat_history) > settings.max_tokens_chat_history:
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
        summary = model_utils.get_reasoning(prompt, model=self._model)

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
        try:
            response = requests.post(settings.moderation_endpoint, json=body)
            if response.ok:
                response = response.json()
                if response["results"][0]["flagged"]:
                    return True
                return False
            else:
                # TODO: improve logging error
                print("Error calling moderataion endpoint", response.content)
            # TODO: Log if the message comes from the user or the assistant
        except requests.exceptions.ConnectionError as ce:
            raise PromptAnswererError(f"Prompt answerer is down. Error: {str(ce)}")
        except Exception:
            pass
