import json
import os
import sys
from datetime import datetime
from os.path import exists

sys.path.append(os.getcwd())
from settings import settings

with open("/whatsappbot/teste", "w") as file:

    data = {"time": datetime.utcnow().isoformat()}
    json.dump(data, file)

if exists(settings.search_data_base_path):

    files_names = os.listdir(settings.search_data_base_path)

    current_date = datetime.utcnow()

    for name in files_names:

        file_path = settings.search_data_base_path + f"{name}"

        with open(file_path, "r") as file:
            data = json.load(file)

        data_last_update = datetime.fromisoformat(data["last_interaction_time"])

        time_delta = current_date - data_last_update

        if time_delta.total_seconds() / 60 > settings.storing_duration_in_minutes:
            os.remove(file_path)
