# Fix for import errors
import json
import os
import sys

sys.path.append(os.getcwd())

from pathlib import Path
from typing import Union

import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from neval import Dataset, Question
from rich import print

from validation.pipeline_settings import GoogleCredentialsToken


def get_credentials(credentials: dict):
    """Get credentials from a dict"""
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_authorized_user_info(credentials, SCOPES)
    return creds


def update_evaluation_sheet(
    token: Union[GoogleCredentialsToken, None],
    spreadsheet_id: str,
    range_name: str,
    table_file: Path,
):
    """Update evaluation sheet with new data"""

    if not token:
        print("No Google API credentials found.")
        print("the evaluation will not be saved in the google sheet.")
        return

    if spreadsheet_id == "" or range_name == "":
        print("No google sheet id or range name found.")
        print("the evaluation will not be saved in the google sheet.")
        return

    try:

        print("Saving evaluation results in the google sheet...")
        creds = get_credentials(token.dict())
        service = build("sheets", "v4", credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()

        evaluation_df = pd.read_csv(table_file, encoding="utf-8")
        evaluation_table = evaluation_df.values.tolist()

        body = {"values": evaluation_table}

        result = (
            sheet.values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
            )
            .execute()
        )

        print(
            f"{(result.get('updates').get('updatedRows'))} evaluations appended in the google sheet."
        )
        print(
            f"The evaluation table is available at: https://docs.google.com/spreadsheets/d/{spreadsheet_id}\n"
        )

    except HttpError as err:
        print(err)


def get_datasets_from_sheet(
    token: Union[GoogleCredentialsToken, None],
    spreadsheet_id: str,
    range_name: str,
    datasets_dir: Path,
):
    """Get datasets from google sheet and save them in the datasets directory"""

    if not token:
        print("No Google API credentials found.")
        print("the datasets will not be downloaded from google sheet.")
        return

    if spreadsheet_id == "" or range_name == "":
        print("No google sheet id or range name found.")
        print("the datasets will not be downloaded from google sheet.")
        return

    try:
        print("Downloading datasets from google sheet...")
        creds = get_credentials(token.dict())
        service = build("sheets", "v4", credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()

        result = (
            sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        )

        values = result.get("values", None)

        if not values:
            print("No datasets found.")
            return

        datasets_questions = {}

        # Skip header
        for row in values[1:]:
            dataset_name = row[1]
            index = row[2]

            if dataset_name not in datasets_questions.keys():
                datasets_questions[dataset_name] = {"index": index, "questions": []}

            datasets_questions[dataset_name]["questions"].append(
                Question(
                    creator="NeuralMind",
                    index=index,
                    variants=[
                        row[4],
                    ],
                    answer=row[5],
                )
            )

        for dataset_name, dataset_info in datasets_questions.items():
            dataset = Dataset(
                index=dataset_info["index"],
                questions=dataset_info["questions"],
            )
            with open(datasets_dir / f"{dataset_name}.json", "w") as f:
                json.dump(dataset.dict(), f, ensure_ascii=False, indent=4)

    except HttpError as err:
        print("An error occurred while downloading datasets from google sheet.")
        print(err)
