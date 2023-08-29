# ChangeLog

All notable changes to this project will be documented in this file.

The format is based on Keep a [Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased] yyyy-mm-dd

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

### Enabled Features

---

## [Version 1.2.0] 2023-08-29

### Added
- Added more interrogative queries
- Added custom recommendation for when the chatbot does not know how to answer a user’s question
- Added custom contact information to the chatbot (based on cosmosDB information)
- Added new summary system in the chatbot memory

### Removed
- Removed search retries

### Enabled Features
- ChatHandler using the React method
- User history (Memory)
- Searches using NeuralSearch and NeuralSearch Sense
- Developer commands, introduction and disclaimer messages in the WhatsApp chatbot
- Possibility of sending custom recommendation and contact information in the chatbot


## [Version 1.1.0] 2023-08-02

### Added
- Created a ChatHandler class based on function calls
- Created a ChatHandler factory strategy to enable choice of ChatHandler implementation. We have two implementations available:
    - Using the React method
    - Using function calls
- Add option for custom accounts in the whatsapp chatbot

### Fixed
- Fixed error when searching in NSX did not return documents due to a bug when passing num_docs and bm25_only parameters
- Fixed error in JSONMemoryHandler where when the memory was used the first message was duplicated in the chat history
- Fixed error in automatic evaluation where when there was an error in the chatbot response, the evaluation would break because the evaluation flag was not defined
- Fixed incorrect action string split that caused the chatbot to make two calls to the same reasoning step

### Enabled Features
- ChatHandler using the React method
- User history (Memory)
- Searches using NeuralSearch and NeuralSearch Sense
- Developer commands, introduction and disclaimer messages in the WhatsApp chatbot.

---

## [Version 1.0.0] 2023-07-20

### Added
- Integrated NeuralSearch Sense to the Chatbot.
- Created a Chat Handler to manage the chatbot logic
- Created a Memory Handler to store the user conversation history in Redis.
- Added a playground for function testing and debugging.
- Send chatbot logs to Azure Tables.
- Add commands to the whatsapp chatbot, with options to debug, select other indexes, and other features.
- Add a validation pipeline for quality control and evaluation of the chatbot.
- Various updates improving debugging and making logs more readable.

### Changed
- The chatbot is now conversational, and uses ReAct to manage the conversation flow and chatbot logic.
- Updated chatbot code for smoother operation.
- Updated the prompt to be more generalizable and robust.
- Changed the overall structure of the project, including folders, files, and code.

### Fixed
- Fixed inconsistencies and errors in chatbot logic.

### Enabled Features
- User history (Memory)
- Searches using NeuralSearch and NeuralSearch Sense
- Developer commands, introduction and disclaimer messages in the WhatsApp chatbot.
