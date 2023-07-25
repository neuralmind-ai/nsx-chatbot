import json
import traceback
import uuid
from logging import Handler

from azure.data.tables import TableServiceClient

from settings import settings


class AzureTableLoggerHandler(Handler):
    def __init__(self, table_name):
        Handler.__init__(self)
        account_name = settings.account_name
        azure_key = settings.azure_chatbot_access_key
        connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={azure_key};EndpointSuffix=core.windows.net"

        service = None
        if azure_key is not None:
            service = TableServiceClient.from_connection_string(
                conn_str=connection_string
            )

        self.table_client = None
        if service is not None:
            self.table_client = service.get_table_client(table_name=table_name)

    def emit(self, record):
        if self.table_client is not None:
            msg = json.loads(record.getMessage())
            msg["PartitionKey"] = str(uuid.uuid4())
            msg["RowKey"] = str(uuid.uuid4())
            msg["Environment"] = settings.environment
            try:
                entity = self.table_client.create_entity(entity=msg)
                return entity
            except Exception:
                print(f"Could not save log in Azure Table: {msg}")
                traceback.print_exc()

    def createLock(self):
        """No need to create log to write to this table."""
        self.lock = None

    def _at_fork_reinit(self):
        pass
