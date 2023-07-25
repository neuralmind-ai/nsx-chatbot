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

## [Version 1.0] 2023-07-20

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
