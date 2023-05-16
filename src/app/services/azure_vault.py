import json
from datetime import datetime

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import EnvironmentCredential
from azure.keyvault.secrets import SecretClient

from app.services.build_timed_logger import build_timed_logger
from settings import settings

credential = EnvironmentCredential()
client = SecretClient(vault_url=settings.azure_vault_url, credential=credential)
vault_logger = build_timed_logger("vault_logger", "vault_log")


def read_secret(secret_name: str):
    try:
        secret = client.get_secret(secret_name)
        return secret.value
    except ResourceNotFoundError:
        vault_logger.error(
            json.dump(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "secret_name": secret_name,
                }
            )
        )
        raise Exception(f"Secret {secret_name} doesn't exist")
