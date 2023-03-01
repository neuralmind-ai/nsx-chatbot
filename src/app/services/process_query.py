import json
from datetime import datetime
from os.path import exists
from typing import Tuple
import time

import requests
from fastapi import HTTPException

from settings import settings


def build_explanation(query: str, user_id: str) -> str:

    """Builds an explanation using the query data stored"""

    search_data_file = settings.search_data_base_path + f"{user_id}.json"

    if exists(search_data_file):

        with open(search_data_file, "r") as file:

            data = json.load(file)

        current_date = datetime.utcnow().isoformat()

        data["last_interaction_time"] = current_date

        with open(search_data_file, "w") as file:

            json.dump(data, file)

        explanation = f"""Referências utilizadas para a elaboração da resposta à pesquisa por "{query}":

{data["search_data"][query]["explanation"]}

Links para acesso:\n\n"""

        for index, document in enumerate(
            data["search_data"][query]["documents"], start=1
        ):

            document_link = document["source_url"]
            explanation += f"{index}: {document_link}\n\n"

        return explanation

    else:

        explanation = (
            "As referências solicitadas não encontram-se disponíveis \U0001F641."
        )
        explanation += f"Informações de pesquisas passadas são automaticamente excluídas após {settings.storing_duration_in_minutes} minutos de inatividade."
        explanation += "\n\nCaso deseje, realize a pesquisa novamente."

        return explanation


def get_multidoc_answer(user_query: str, documents) -> Tuple[str, str]:

    """
    Gets a MultidocQA answer based on a user query and a list of documents retrieved by NSX.
    Returns a 2D tuple that contains the predicted answer and its explanation, respectively.
    """

    try:
        response = requests.post(
            f"{settings.base_url}/api/multidocqa",
            json={
                "query": user_query,
                "documents": documents,
                "language": settings.language,
                "index": settings.search_index,
            },
        )

        response = response.json()

        return response["pred_answer"], response["explanation"]

    except Exception:

        raise HTTPException(
            status_code=503, detail="Request to NSX MultidocQA API failed"
        )

def get_keycloak_token() -> str:

    """Makes a request to NSX client token api in order to obtain a keycloak token to be used for
       acessing private indexes.
    """

    try:
        response = requests.post(
            f"{settings.base_url}/api/client/token",
            json={
                "client_id": settings.keycloak_login,
                "client_secret": settings.keycloak_password
            }
        )

        response = response.json()

        return response["token"]

    except:

        raise HTTPException(
            status_code=503, detail="Request to NSX Keycloak token API failed"
        )

def nsx_search_request(user_query: str, auth_token: str = None):

    """
        Uses the NSX search API to obtain relevant information for answering the given query.
        If no authentication token is provided, the search will only be able to acess public indexes.
    """

    try:

        url = f"{settings.base_url}/api/search"

        body = {
            "index": settings.search_index,
            "max_docs_to_return": 15,
            "query": user_query,
        }

        if auth_token != None:
            response = requests.get(
                url,
                headers={
                    "Authorization": "Client " + auth_token
                },
                params = body
            )
        else:
            response = requests.get(
                url,
                params = body
            )

        return response

    except Exception:

        raise HTTPException(status_code=503, detail="Request to NSX Search API failed")

def get_documents(user_query: str) -> dict:

    """Receives a query and make a request to NSX for retrieving relevant documents"""

    if settings.search_index == "central_solucoes":

        for i in range(settings.nsx_auth_requests_attempts):

            auth_token = get_keycloak_token()
        
            search_response = nsx_search_request(user_query, auth_token)

            if search_response.status_code != 403:
                break

            time.sleep(1)
    
    else:

        search_response = nsx_search_request(user_query)
    
    content = search_response.json()["response_reranker"]

    return content
    
def process_query(user_query: str, user_id: str) -> str:

    """Receives a query, processes it and returns the message that will be posted to the user"""

    # Firstly, documents related to the query are retrieved from the NSX search endpoint:
    documents = get_documents(user_query)

    # Then, those documents are used for creating a MultidocQA answer and explanation:
    answer, explanation = get_multidoc_answer(user_query, documents)

    data_file_path = settings.search_data_base_path + f"{user_id}.json"

    current_date = datetime.utcnow().isoformat()

    if exists(data_file_path):
        with open(data_file_path, "r") as file:
            data = json.load(file)

        data["search_data"][user_query] = {
            "documents": documents,
            "explanation": explanation,
        }
        data["last_interaction_time"] = current_date

        with open(data_file_path, "w") as file:
            json.dump(data, file)
    else:
        with open(data_file_path, "w") as file:
            data = {}
            data["search_data"] = {}
            data["search_data"][user_query] = {
                "documents": documents,
                "explanation": explanation,
            }
            data["last_interaction_time"] = current_date
            json.dump(data, file)

    return answer