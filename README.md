# bay_telegram_bot

Simple object oriented Telegram REST API bot.

##### Installation:
```python
pip install -r requirements.txt
```

##### Usage:
```python
from telegram_bot import BotCommand, TelegramBot, TelegramMessage

class MyCommand(BotCommand):
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/command_name_here"
        super().__init__()

    def execute(self):
        # Code to execute when command is detected
        # Example: Send a message back to the chat where it was receieved
        self.bot.send_message(self.msg.chat_id, "Message")

def main():
    # Set access token and initialize
    access_token = "<access token>"
    telegram_bot = TelegramBot(access_token)
    
    # Enable logging and set Loguru log level. Log format can also be defined with log_format=.
    # https://loguru.readthedocs.io/en/stable/api/logger.html#levels
    telegram_bot.enable_logging(log_level="DEBUG")
    telegram_bot.bot_commands = [MyCommand]

    # Start main loop
    telegram_bot.start()


if __name__ == "__main__":
    main()
```
##### Extending objects
```python
from telegram_bot import TelegramBot, TelegramMessage, BotCommand
import requests
from loguru import logger
from typing import BinaryIO

class MyBot(TelegramBot):
    def __init__(self, access_token: str):
        super().__init__(access_token)

    def send_file(self, chat_id: str, document: BinaryIO) -> requests.Response:
        logger.debug(f"Sending file to chat '{chat_id}'")
        data = {"chat_id": chat_id}
        return requests.post(self.api_url + "sendDocument", data=data, files={"document": document})
    
class MyCommand(BotCommand):
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/command_name_here"
        super().__init__()

    def execute(self):
        with open("a_file", "rb") as f:
            document = f.read()
        self.bot.send_file(self.msg.chat_id, document)

def main():
    access_token = "<access token>"
    telegram_bot = MyBot(access_token)
    telegram_bot.enable_logging(log_level="DEBUG")
    telegram_bot.bot_commands = [MyCommand]
    telegram_bot.start()
```
