# WhatsApp bot for NeuralSearchX Sense

This repository contains the code for integrating Whatsapp and [360 Dialog](https://www.360dialog.com/) with NeuralSearchX Sense.

The Fast API instance created in `whatsappbot/src/app/main.py` provides a webhook (`whatsappbot/src/app/routers/webhook.py`) for processing user interactions with the Whatsapp account registered in 360 Dialog.

NeuralSearchX Sense data that users might request after interacting with the bot is automatically stored in `.json` files in `whatsappbot/scr/app/search_data`, each for a different user. If necessary, this repository will be automatically created. The time of the last interaction of a user with the bot is also registered, making it possible to determine whether a user is active of not.

After a defined number of minutes, a cronjob running `whatsappbot/src/cronjobs/search_data_cleaner.py` is executed in order to clean search data from inactive users. The execution interval mentioned above is defined in the Dockerfile.

All settings - such those related to Neural Search API requests or the time interval for a user to be considered inactive - can be found in `whatsappbot/src/settings.py`.
