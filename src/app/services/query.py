from time import sleep

import requests

from settings import settings


def build_msg(query, content):
    message = f'Resultados de pesquisa para "{query}"\n\n'
    for item in content:
        message += f"{item['title']}\n"
        if item["source_url"]:
            message += f"{item['source_url']}\n"
        message += "\n"
        for p in item["paragraphs"]:
            message += p[:900]
            message += "\n\n"
        message += "\n"
    return message


def query(user_query: str):
    response = requests.get(
        f"{settings.base_url}/api/search",
        params={"index": "demo_sebrae", "query": user_query},
    )
    query_id = response.json()["query_id"]
    while True:
        sleep(2)
        response = requests.get(
            f"{settings.base_url}/api/search/result",
            params={"query_id": query_id},
        )
        if response.status_code == 200:
            break
    content = response.json()["response_reranker"][:1]
    message = build_msg(user_query, content)

    return message
