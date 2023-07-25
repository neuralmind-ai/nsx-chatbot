# NSX-ChatBot

This repository contains the NSX-ChatBot code. This project uses LLM-based NeuralMind technologies (NSX, NSXSense and others) to implement an autonomous agent that answers user questions about a specific document base using a chat based approach.

The Fast API instance created in `whatsappbot/src/app/main.py` provides a webhook (`whatsappbot/src/app/routers/webhook.py`) for processing user interactions with the Whatsapp account registered in 360 Dialog.

All settings - such those related to Neural Search API requests or the time interval for a user to be considered inactive - can be found in `whatsappbot/src/settings.py`.

## Installing the project and manage its dependencies

This project uses [poetry](https://python-poetry.org/) as dependency manager, so to install its dependencies we recommend that you install poetry and use it to managing the NSX-Chatbot dependencies.

There are many ways to install poetry on your system, you can use your system's package manager, install using pip, conda or other python package managers.

For example, to install poetry you can use one of the follow commands.

```bash
# Installing with pip
pip install poetry

# Installing with conda
conda install poetry

# With the official installer (Linux, macOS, Windows (WSL))
curl -sSL https://install.python-poetry.org | python3 -

# Windowns (Powershell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

```

For more details about poetry installation, you can read its [documentation](https://python-poetry.org/docs/#installing-with-the-official-installer).


With poetry installed in your environment, you can use the following commands to install the project dependencies.

```bash
# Install project dependencies (main and dev dependencies)
poetry install
# Enter in the project virtual environment
poetry shell
```

If you want only install the project dependencies, you can use the `requirements*.txt` files. The `requirements.txt`, in the project root folder, has all runtime (main) dependencies needed to run the NSX-Chatbot. You can install it using pip, we recommend that you install the dependencies in a virtual environment to avoid conflits with depedencies versions in your system. On linux you can use the following commands.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

As a developer, we endorce that you also install the *dev dependencies* of this project. They include, the code formatter, the linter and test tools, used in this project. If you are using poetry, it will install the *dev dependencies* automatically with the command `poetry install`. To install the *dev dependencies* with pip, you can use the `requirements-dev.txt` file.

If you want use the **Evaluation Pipeline**, you need install the evaluation dependencies. You can install these dependencies with one of the following commands.

```bash
# With poetry
poetry install --with eval

# With pip
pip install -r requirements-eval.txt
```

## Development Guidelines

To improve collaborative work on this project, we strongly recommend that you use the code formatting and linting tools.

In the NSX-Chatbot, we use the [pre-commit](https://pre-commit.com/) tool to apply code formatting and linting before each git commit. if you installed the developer dependencies the pre-commit is already available in your environment. To install the pre-commit hooks on git, you can use the `pre-commit install` command. If you have modifications in the git staging, you can manually run pre-commit with the `pre-commit run` command, with this command, pre-commit will run [black](https://black.readthedocs.io/en/stable/), [isort](https://pycqa.github.io/isort/), [flake8](https://flake8.pycqa.org/en/latest/) and other tools in the staging modifications.


## Evaluation Pipeline

For automatic evaluation of NSX-ChatBot responses, the project contains a configurable evaluation pipeline script that evaluates a set of QA Dataset with chatbot responses to obtain NSX-ChatBot accuracy on each dataset.

The script is integrated with Bitbucket Pipelines, so it is possible to launch customizable pipelines, defining the behavior of NSX-ChatBot and the features enabled in the evaluation.

The available variables for the evaluation pipeline are as follows.

- `PIPELINE_NAME` (str): The name of the pipeline, used for saving results and in memory context
- `CHATBOT_MODEL` (str): The LLM model used in the chatbot reasoning. (gpt-3.5-turbo, gpt-4)
- `DISABLE_MEMORY` (bool): Disables the chatbot memory feature in the evaluation (Accepted values: false or true)
- `DISABLE_FAQ` (bool): Disable the chatbot FAQ feature in the review (Accepted values: false or true)
- `USE_NSX_SENSE` (bool): Use NSX-Sense in chatbot search feature (Accepted values: false or true)
- `BM25_ONLY` (bool): Use only BM25 results list in NSX/SENSE search
- `MAX_DATASET_QUESTIONS` (int): Set the maximum number of questions from each Dataset to use in the evaluation (-1 to use all questions)
- `MAX_VARIANT_QUESTIONS` (int): Set the maximum number of variants of a question to use in the evaluation (-1 to use all variants)

In order for the evaluation data to be saved in the google spreadsheet, it is necessary to configure 3 environment variables:

- `GOOGLE_OAUTH2_TOKEN`: This variable is needed to authenticate in the google sheets api, it follows the format of a JSON-encoded string and contains information about the Google API access token. For more details on how google authentication works see this link. To get this variable you need to create new credentials in NSX Chatbot Evaluations project in Google Cloud Console. This project is under the NeuralMind organization on the Google Workspace. So, you need to login to the platform with your NeuralMind account to have access to the project.

```bash
GOOGLE_OAUTH2_TOKEN='{"token": "", "refresh_token": "", "token_uri": "", "client_id": "", "client_secret": "", "scopes": [""], "expiry": ""}'
```

- `SPREADSHEET_ID`: This script information variable which is the id of the google spreadsheet that the api will manipulate during the evaluation. Remembering again that the project is linked to NeuralMind's google workspace, so the spreadsheet needs to be in that environment. The spreadsheet id can be obtained from its url in the browser as shown below.

```bash
URL=https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/
SPREADSHEET_ID=$(echo $URL | grep -oP '(?<=/d/)[^/]+')
```

- `RAW_SHEET_NAME`: This variable indicates to the script which sheet page the evaluation data will be added to. As a default setting, the `raw` page is used to store the evaluations.

Datasets can also be obtained from a Google spreadsheet. To do this, simply define the following environment variables:

- `DATASET_SPREADSHEET_ID`: Indicates to the script the ID of the Google spreadsheet where the datasets are stored.

- `DATASET_SHEET_NAME`: Name of the page in the spreadsheet with `DATASET_SPREADSHEET_ID` where the datasets are stored.

## Run Chatbot evaluations in local environments

To run chatbot evaluations in a local environment, it is necessary to set the evaluation pipeline environment variables in a `.env` file in the `whatsappbot/src` directory. To access the evaluation datasets, you need to configure the `EVALCHATBOT_STORAGE_CS` environment variable with the Azure Blob Storage connection string containing the datasets. The connection string can be obtained by accessing the `evalchatbot` resource in the [Azure portal](https://portal.azure.com/). An example of the configuration file is shown below:

```bash
EVALCHATBOT_STORAGE_CS="Azure Blob Service Storage Connection String"
PIPELINE_NAME="chatbot_gpt-4_MEMORY_OFF_FAQ_OFF_SENSE_OFF_VARIANT_1"
CHATBOT_MODEL="gpt-4" # Reasoning model
DISABLE_MEMORY=true
DISABLE_FAQ=true
USE_NSX_SENSE=false # Don't use SENSE, use NSX first document instead
BM25_ONLY=false
VERBOSE=false
MAX_DATASET_QUESTIONS=-1 # Use all dataset questions
MAX_VARIANT_QUESTIONS=1 # Use only one variant of each question
```

In the example above, we set up a Chatbot evaluation that uses `gpt-4` to answer questions. The `memory`, `FAQ` features will not be used, and the chatbot will not use `SENSE` to obtain search results. Additionally, in this experiment, only one variant of each question from the datasets will be evaluated.

To start the evaluation, simply run the following command:
```bash
cd whatasppbot/src
python validation/pipeline.py
```

> Remember that the prompt-answerer must be running at `localhost:7000` for the chatbot and evaluation to work correctly.

At the end of the experiment, a table with a summary of the results is displayed. The data and logs of the experiment will be available in the `validation/data` and `validation/logs` directories, respectively. The files are identified by the name defined in `PIPELINE_NAME`.

## Special evaluation Settings

It is possible to select a list of indexes/datasets that will be evaluated in the pipeline. To do this, just set the environment variable `EVALUATION_INDEXES`. This variable accepts a list of names of **existing** NSX indexes in JSON String format. An example of how to configure this variable is shown below.

```bash
EVALUATION_INDEXES='["FUNDEP_Cardiologia", "FUNDEP_Ciencias", "FUNDEP_Medicina", "FUNDEP_Pneumologia", "FUNDEP_Paraopeba"]'
```

It is also possible to map the names of the indexes defined in the dataset to other indexes in the same database but indexed in a different configuration. To do this, simply set the environment variable `INDEX_MAPPING` to the desired mapping. The `INDEX_MAPPING` variable follows the format of a JSON String where the keys are the original names of the indexes in the evaluation dataset and the value is the name of the index that should be used in the evaluation. An example of how to configure this variable is shown below.

```bash
INDEX_MAPPING='{"FUNDEP_Cardiologia": "FUNDEP_Cardiologia_2", "FUNDEP_Ciencias": "FUNDEP_Ciencias_Modified", "FUNDEP_Medicina": "Medicina_FIXED"}'
```

## Debug Chat

Para testar o chat, recomendamos usar o script `debug_chat` (deve ser invocado a partir do diretorio `src`):
To test chat handler, you can use the `debug_chat.py` script, which should be launched from the `src` folder:

```
> cd src
> python debug_chat.py
```

You can feed the script parameters, like:

```
> python debug_chat --help
> python debug_chat.py --user fulano --index FUNDEP_Ciencias  --disable-faq --disable-mem --use-nsx --verbose --dev
```

You can also pass in the first question as a parameter:

```
> python debug_chat.py --user fulano --index FUNDEP_Ciencias  --disable-faq --disable-mem --use-nsx --verbose --dev \
    "Qual a data da prova?"
```
