# NSX-ChatBot

This repository contains the NSX-ChatBot code. This project uses LLM-based NeuralMind technologies (NSX, NSXSense and others) to implement an autonomous agent that answers user questions about a specific document base using a chat based approach.

The Fast API instance created in `whatsappbot/src/app/main.py` provides a webhook (`whatsappbot/src/app/routers/webhook.py`) for processing user interactions with the Whatsapp account registered in 360 Dialog.

All settings - such those related to Neural Search API requests or the time interval for a user to be considered inactive - can be found in `whatsappbot/src/settings.py`.

## Evaluation Pipeline

For automatic evaluation of NSX-ChatBot responses, the project contains a configurable evaluation pipeline script that evaluates a set of QA Dataset with chatbot responses to obtain NSX-ChatBot accuracy on each dataset.

The script is integrated with Bitbucket Pipelines, so it is possible to launch customizable pipelines, defining the behavior of NSX-ChatBot and the features enabled in the evaluation.

The available variables for the evaluation pipeline are as follows.

- `PIPELINE_NAME` (str): The name of the pipeline, used for saving results and in memory context
- `CHATBOT_MODEL` (str): The LLM model used in the chatbot reasoning. (gpt-3.5-turbo, gpt-4)
- `DISABLE_MEMORY` (bool): Disables the chatbot memory feature in the evaluation (Accepted values: false or true)
- `DISABLE_FAQ` (bool): Disable the chatbot FAQ feature in the review (Accepted values: false or true)
- `USE_NSX_SENSE` (bool): Use NSX-Sense in chatbot search feature (Accepted values: false or true)
- `MAX_DATASET_QUESTIONS` (int): Set the maximum number of questions from each Dataset to use in the evaluation (-1 to use all questions)
- `MAX_VARIANT_QUESTIONS` (int): Set the maximum number of variants of a question to use in the evaluation (-1 to use all variants)

## Run Chatbot evaluations in local environments

To run chatbot evaluations in a local environment, it is necessary to set the evaluation pipeline environment variables in a `.env` file in the `whatsappbot/src` directory. To access the evaluation datasets, you need to configure the `EVALCHATBOT_STORAGE_CS` environment variable with the Azure Blob Storage connection string containing the datasets. The connection string can be obtained by accessing the `evalchatbot` resource in the [Azure portal](https://portal.azure.com/). An example of the configuration file is shown below:

```bash
EVALCHATBOT_STORAGE_CS="Azure Blob Service Storage Connection String"
PIPELINE_NAME="chatbot_gpt-4_MEMORY_OFF_FAQ_OFF_SENSE_OFF_VARIANT_1"
CHATBOT_MODEL="gpt-4" # Reasoning model
DISABLE_MEMORY=true
DISABLE_FAQ=true
USE_NSX_SENSE=false # Don't use SENSE, use NSX first document instead
VERBOSE=false
MAX_DATASET_QUESTIONS=-1 # Use all dataset questions
MAX_VARIANT_QUESTIONS= # Use only one variant of each question
```

In the example above, we set up a Chatbot evaluation that uses `gpt-4` to answer questions. The `memory`, `FAQ` features will not be used, and the chatbot will not use `SENSE` to obtain search results. Additionally, in this experiment, only one variant of each question from the datasets will be evaluated.

To start the evaluation, simply run the following command:
```bash
cd whatasppbot/src
python validation/pipeline.py
```

> Remember that the prompt-answerer must be running at `localhost:7000` for the chatbot and evaluation to work correctly.

At the end of the experiment, a table with a summary of the results is displayed. The data and logs of the experiment will be available in the `validation/data` and `validation/logs` directories, respectively. The files are identified by the name defined in `PIPELINE_NAME`.

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
