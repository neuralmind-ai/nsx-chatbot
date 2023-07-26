import requests

from app.prompts import base_prompt
from app.utils.exceptions import (
    NSXAuthenticationError,
    NSXSearchError,
    SenseSearchError,
)
from app.utils.timeout_management import RequestMethod, retry_request_with_timeout
from settings import settings


class NSXSearchTool:
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

    name = "custom_search"
    description = "useful for when you need to answer questions about current events"

    index: str

    def __init__(self, language, api_key):
        prompts = base_prompt.prompts

        # self._index = index
        self.language = language
        self._api_key = api_key
        self.unanswerable_search = prompts[self.language]["unanswerable_search"]
        self.answer_not_found = prompts[self.language]["answer_not_found"]

    def search(
        self,
        query: str,
        index: str,
        api_key: str,
        searches_left: int,
        num_docs: int = 1,
        bm25_only: bool = False,
    ) -> str:
        """
        Gets the first document from NSX.

        Args:
            - query: the query to be sent to NSX.
            - index: the index to be used for the search.
            - api_key: the user's API key to be used for the NSX API.
            - searches_left: number of searches the model can still do for the current message.
            - num_docs: number of documents to be returned by NSX.
            - bm25_only: if True, returns only the bm25 list.

        Returns:
            str: The answer to the query (with concatenated num_docs from NSX) or
            str: A string telling the chatbot that the answer was not found on NSX.
        """
        # Parameters for the request
        assert num_docs > 0
        params = {
            "index": index,
            "query": query,
            "max_docs_to_return": settings.max_docs_to_return,
            "format_response": False,
        }

        # If bm25_only is True, returns only the bm25 list
        if bm25_only:
            params["return_reference"] = 1
            params["neural_ranking"] = False

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

            response.raise_for_status()

            response_json = response.json()

            if bm25_only:
                nsx_docs = response_json["response_reference"]
            else:
                nsx_docs = response_json["response_reranker"]

            nsx_docs_len = len(nsx_docs)

            if nsx_docs_len:
                docs = ""
                for doc_idx in range(min(num_docs, nsx_docs_len)):
                    docs += f"{nsx_docs[doc_idx]['paragraphs'][0]}\n"
                return docs.strip()
            elif searches_left == 0:
                return self.unanswerable_search
            else:
                return self.answer_not_found

        except requests.HTTPError as he:
            if he.response.status_code == 403:
                raise NSXAuthenticationError("Invalid API key.")
            raise NSXSearchError(f"Error in NSX: {he.response.json()['message']}.")
        except requests.exceptions.Timeout as te:
            raise te
        except Exception as e:
            raise e


class NSXSenseSearchTool:
    def __init__(self, language, api_key):
        prompts = base_prompt.prompts

        self.language = language
        self._api_key = api_key
        self.unanswerable_search = prompts[self.language]["unanswerable_search"]
        self.answer_not_found = prompts[self.language]["answer_not_found"]

    def search(
        self,
        query: str,
        index: str,
        api_key: str,
        searches_left: int,
        bm25_only: bool = False,
    ) -> str:
        """
        Gets a response using NSX sense.

        Args:
            - query: the query to be sent to NSX.
            - index: the index to be used for the search.
            - api_key: the user's API key to be used for the NSX API.
            - searches_left: number of searches the model can still do for the current message.
            - bm25_only: if True, returns only the bm25 list.

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

        # If bm25_only is True, returns only the bm25 list
        if bm25_only:
            params["return_reference"] = 1
            params["neural_ranking"] = False

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
            if response.status_code == 403:
                raise NSXAuthenticationError("Invalid API key.")
            raise NSXSearchError(f"Error in NSX: {response.json()['message']}.")

        response = response.json()

        if bm25_only:
            documents = [
                {"paragraphs": doc["paragraphs"][0]}
                for doc in response["response_reference"]
            ]

        else:
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
            r = response.json()
            if r.get("detail") is not None:
                raise SenseSearchError(f"Error in MultidocQA: {r.get('detail')}")
            else:
                raise SenseSearchError(
                    f"Error in MultidocQA: {r}, status: {response.status_code}"
                )

        response = response.json()["pred_answer"]

        if "irrespondível" in response.lower():
            if searches_left == 0:
                return self.unanswerable_search
            else:
                return self.answer_not_found
        else:
            return response
