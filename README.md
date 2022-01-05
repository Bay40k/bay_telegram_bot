# bay_telegram_bot

Simple object oriented Telegram HTTP API bot.

##### Installation:
```commandline
pip install -r requirements.txt
python example_bot.py
```

##### Usage:
```python
from telegram_bot import BotCommand, TelegramBot, TelegramMessage

class MyCommand(BotCommand):
    def __init__(self, **kwargs):
        self.cmd_name = "/command_name_here"
        super().__init__(**kwargs)

    def execute(self):
        # Code to execute when command is detected
        # Example: Send a message back to the chat where it was receieved
        self.bot.send_message(self.msg.chat_id, "Message")
        
        # List of arguments provided after command
        # self.arguments

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
from typing import BinaryIO

class MyBot(TelegramBot):
    def __init__(self, access_token: str):
        super().__init__(access_token)

    def send_document(self, chat_id: str, document: BinaryIO) -> requests.Response:
        data = {"chat_id": chat_id}
        return requests.post(self.api_url + "sendDocument", data=data, files={"document": document})
    
class MyCommand(BotCommand):
    def __init__(self, **kwargs):
        self.cmd_name = "/command_name_here"
        super().__init__(**kwargs)

    def execute(self):
        with open("a_file", "rb") as f:
            document = f.read()
        self.bot.send_document(self.msg.chat_id, document)

def main():
    access_token = "<access token>"
    telegram_bot = MyBot(access_token)
    telegram_bot.bot_commands = [MyCommand]
    telegram_bot.start()
```
##### Extending objects to include [Pyrogram](https://github.com/pyrogram) plugin, in order to access MTProto commands not available through the HTTP bot API. (Such as `get_history()`)

```python
from telegram_bot import TelegramBot, TelegramMessage, BotCommand
from pathlib import Path
from plugins.pyrogramplugin import PyrogramPlugin
from typing import List, Union


class MyBot(TelegramBot):
    def __init__(self, access_token: str, api_id: int, api_hash: str):
        super().__init__(access_token)
        self.pyrogram_client = PyrogramPlugin("telegram_mtproto", api_id, api_hash, phone_number="<phone_number>>")
        self.pyrogram_bot = PyrogramPlugin("telegram_mtproto_bot", api_id, api_hash, bot_token=access_token)

    def send_document(self, chat_id: int, document: Path):
        self.pyrogram_bot.send_document(chat_id, document)

    def get_history(self, chat_id: Union[int, str], offset: int = 0) -> List[TelegramMessage]:
        """
        Example usage in a BotCommand method:
        for message in self.bot.get_history(self.msg.chat_id):
            print(f"{message.sender.first_name}: {message.text}")
        """
        messages = []
        for message in self.pyrogram_client.get_history(int(chat_id), offset=offset):
            message["from"] = message["from_user"]
            message = TelegramMessage(message)
            messages.append(message)
        return messages


class MyCommand(BotCommand):
    def __init__(self, **kwargs):
        self.cmd_name = "/command_name_here"
        super().__init__(**kwargs)

    def execute(self):
        my_file = Path("/path/to/file")
        self.bot.send_document(self.msg.chat_id, my_file)


def main():
    access_token = "<access token>"
    api_id = 1234
    api_hash = "<api_hash>"
    telegram_bot = MyBot(access_token, api_id, api_hash)
    telegram_bot.bot_commands = [MyCommand]
    telegram_bot.start()
```
#### Extending objects to handle inline keyboard callbacks with Pyrogram and [PyKeyboard](https://github.com/pystorage/pykeyboard)

```python
from telegram_bot import TelegramBot, TelegramMessage, BotCommand, TelegramCallbackQuery
from plugins import PyrogramPlugin
from pykeyboard import InlineKeyboard
from pyrogram.types import InlineKeyboardButton


class OnCallbackQuery:
    def __init__(self, bot: TelegramBot, callback_query: TelegramCallbackQuery):
        # Access CallbackQuery data
        # Example: Send callback query data back to where it was received
        bot.send_message(callback_query.message.chat_id, callback_query.data)


class MyBot(TelegramBot):
    def __init__(self, access_token: str, api_id: int, api_hash: str):
        self.callback_query_handler = OnCallbackQuery  # Type: Callable[[TelegramBot, TelegramCallbackQuery], None]
        super().__init__(access_token)
        self.pyrogram_client = PyrogramPlugin("telegram_mtproto", api_id, api_hash, phone_number="<phone_number>")
        self.pyrogram_bot = PyrogramPlugin("telegram_mtproto_bot", api_id, api_hash, bot_token=access_token)


class MyCommand(BotCommand):
    def __init__(self, **kwargs):
        self.cmd_name = "/command_name_here"
        super().__init__(**kwargs)

    def execute(self):
        keyboard = InlineKeyboard(row_width=3)
        keyboard.row(InlineKeyboardButton("Button text", callback_data="callback data"))
        self.bot.pyrogram_bot.send_message(self.msg.chat_id, "Message text", reply_markup=keyboard)


def main():
    access_token = "<access token>"
    api_id = 1234
    api_hash = "<api_hash>"
    telegram_bot = MyBot(access_token, api_id, api_hash)
    telegram_bot.bot_commands = [MyCommand]
    telegram_bot.callback_query_handler = OnCallbackQuery
    telegram_bot.start()
```

More examples can be found in [example_bot.py](example_bot.py)
