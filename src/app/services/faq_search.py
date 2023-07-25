import datetime
import json
import time
import traceback
from glob import glob
from typing import Dict, List

import requests

from app.prompts import base_prompt
from app.utils import model_utils
from app.utils.model_utils import error_logger
from settings import settings


class FAQSearchTool:
    def __init__(self, language, model):
        prompts = base_prompt.prompts

        self.language = language
        self.model = model
        self.faq_prompt = prompts[self.language]["faq_prompt"]
        # Loads the FAQs
        self.faq = self.load_faqs("app/faqs")

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

    def search(
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
        prompt_size = model_utils.get_num_tokens(self.faq_prompt + query)

        for question in top_questions:
            question_size = model_utils.get_num_tokens(question)
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
        response = model_utils.get_reasoning(prompt, stop=["\n"], model=self.model)
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
