FROM python:3.10.12 as builder

WORKDIR /nsx-chatbot

RUN pip install poetry

COPY pyproject.toml poetry.lock poetry.toml README.md /nsx-chatbot/

RUN poetry install --without dev --no-root --no-directory

FROM python:3.10.12-slim

ARG API_KEY
ARG AZURE_CHATBOT_ACCESS_KEY
ARG AZURE_CLIENT_ID
ARG AZURE_CLIENT_SECRET
ARG AZURE_TENANT_ID
ARG COSMOS_KEY
ARG ENVIRONMENT
ARG TOKEN

ENV API_KEY=${API_KEY} \
    AZURE_CHATBOT_ACCESS_KEY=${AZURE_CHATBOT_ACCESS_KEY} \
    AZURE_CLIENT_ID=${AZURE_CLIENT_ID} \
    AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET} \
    AZURE_TENANT_ID=${AZURE_TENANT_ID} \
    COSMOS_KEY=${COSMOS_KEY} \
    ENVIRONMENT=${ENVIRONMENT} \
    PATH="/nsx-chatbot/.venv/bin:$PATH" \
    TOKEN=${TOKEN} \
    TZ=America/Sao_Paulo

EXPOSE 9000

COPY --from=builder /nsx-chatbot /nsx-chatbot

WORKDIR /nsx-chatbot/src

COPY ./src /nsx-chatbot/src

CMD uvicorn main:app --host 0.0.0.0 --port 9000
