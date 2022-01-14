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
        if item["content_is_formated"]:
            for p in item["paragraphs"]:
                message += f"{p}\n"
        else:
            for p, h in zip(item["paragraphs"], item["highlights"]):
                if h == []:
                    message += f"{p}\n"
                else:
                    for start, end in h:
                        message += f"{p[start:end]}\n"
        message += "\n"
    return message


def query(user_query: str):
    response = requests.get(
        f"{settings.base_url}/api/search",
        params={"index": "demo_sebrae", "query": user_query},
    )
    content = response.json()["response_reranker"][:1]
    message = build_msg(user_query, content)

    return message
