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
