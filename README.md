# bay_telegram_bot

Simple object-oriented Telegram HTTP API bot.

##### Installation:
```commandline
git clone https://github.com/Bay40k/bay_telegram_bot
cd bay_telegram_bot
pip install -r requirements.txt
python example_bot.py
```

##### Usage:

```python
from telegram_bot import BotCommand, TelegramBot


class MyCommand(BotCommand):
    cmd_name = "/command_name_here"

    async def execute(self):
        # Code to execute when command is detected
        # Example: Send a message back to the chat where it was receieved
        await self.bot.send_message(self.msg.chat_id, "Message")

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
from telegram_bot import TelegramBot, BotCommand
import requests
from typing import BinaryIO

class MyBot(TelegramBot):
    def __init__(self, access_token: str):
        super().__init__(access_token)

    async def send_document(self, chat_id: str, document: BinaryIO) -> requests.Response:
        data = {"chat_id": chat_id}
        return requests.post(self.api_url + "sendDocument", data=data, files={"document": document})
    
class MyCommand(BotCommand):
    cmd_name = "/command_name_here"

    async def execute(self):
        with open("a_file", "rb") as f:
            document = f.read()
        await self.bot.send_document(self.msg.chat_id, document)

def main():
    access_token = "<access token>"
    telegram_bot = MyBot(access_token)
    telegram_bot.bot_commands = [MyCommand]
    telegram_bot.start()
```
##### Extending objects to include [Pyrogram](https://github.com/pyrogram), in order to access MTProto commands not available through the HTTP bot API. (Such as `get_history()`)

```python
from telegram_bot import TelegramBot, TelegramMessage, BotCommand
from pathlib import Path
from pyrogram import Client
from typing import List, Union


class MyBot(TelegramBot):
    def __init__(self, access_token: str, api_id: int, api_hash: str):
        super().__init__(access_token)
        self.pyrogram_client = Client("telegram_mtproto", api_id, api_hash, phone_number="<phone_number>>")
        self.pyrogram_bot = Client("telegram_mtproto_bot", api_id, api_hash, bot_token=access_token)

    async def send_document(self, chat_id: int, document: Path):
        async with self.pyrogram_bot:
            await self.pyrogram_bot.send_document(chat_id, document)

    async def get_history(self, chat_id: Union[int, str], offset: int = 0) -> List[TelegramMessage]:
        """
        Example usage in a BotCommand method:
        for message in self.bot.get_history(self.msg.chat_id):
            print(f"{message.sender.first_name}: {message.text}")
        """
        messages = []
        async with self.pyrogram_client:
            async for message in self.pyrogram_client.get_history(int(chat_id), offset=offset):
                # Convert Pyrogram objects into bay_telegram_bot objects
                message["from"] = message.from_user.__dict__
                message = message.__dict__
                messages.append(TelegramMessage(message))
        return messages


class MyCommand(BotCommand):
    cmd_name = "/command_name_here"

    async def execute(self):
        my_file = Path("/path/to/file")
        await self.bot.send_document(self.msg.chat_id, my_file)


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
from telegram_bot import TelegramBot, BotCommand, TelegramCallbackQuery
from pyrogram import Client
from pykeyboard import InlineKeyboard
from pyrogram.types import InlineKeyboardButton


class OnCallbackQuery:
    def __init__(self, bot: TelegramBot, callback_query: TelegramCallbackQuery):
        self.bot = bot
        bot.event_loop.create_task(
            self.handle_callback_query(callback_query)
        )
    def handle_callback_query(self, callback_query: TelegramCallbackQuery):
        # Access CallbackQuery data
        # Example: Send callback query data back to where it was received
        await self.bot.send_message(callback_query.message.chat_id, callback_query.data)


class MyBot(TelegramBot):
    def __init__(self, access_token: str, api_id: int, api_hash: str):
        super().__init__(access_token)
        self.callback_query_handler = OnCallbackQuery  # Type: Callable[[TelegramBot, TelegramCallbackQuery], None]
        self.pyrogram_client = Client("telegram_mtproto", api_id, api_hash, phone_number="<phone_number>")
        self.pyrogram_bot = Client("telegram_mtproto_bot", api_id, api_hash, bot_token=access_token)


class MyCommand(BotCommand):
    cmd_name = "/command_name_here"

    async def execute(self):
        keyboard = InlineKeyboard(row_width=3)
        keyboard.row(InlineKeyboardButton("Button text", callback_data="callback data"))
        await self.bot.pyrogram_bot.send_message(self.msg.chat_id, "Message text", reply_markup=keyboard)


def main():
    access_token = "<access token>"
    api_id = 1234
    api_hash = "<api_hash>"
    telegram_bot = MyBot(access_token, api_id, api_hash)
    telegram_bot.bot_commands = [MyCommand]
    telegram_bot.start()
```
