from __future__ import annotations
import asyncio
from abc import abstractmethod
from dataclasses import dataclass
from loguru import logger
from pathlib import Path
from typing import Callable, Dict, List, NewType, Optional
import inspect
import json
import requests
import sys
import threading
import traceback


@dataclass
class TelegramUser:
    """
    Telegram user object.

    :attr user_id: ID of the user
    :attr is_bot: If user is a bot
    :attr first_name: User's first name
    :attr username: User's username
    """
    user_id: Optional[int] = None
    is_bot: Optional[bool] = None
    first_name: Optional[str] = None
    username: Optional[str] = None

    def __init__(self, user_dict: dict):
        """
        :param user_dict: User dictionary (usually ["message"]["from"])
        """
        attributes = {
            "user_id:": "id",
            "is_bot": "is_bot",
            "first_name": "first_name",
            "username": "username"
        }
        for key in attributes:
            try:
                setattr(self, key, user_dict[attributes[key]])
            except KeyError:
                setattr(self, key, None)
        if self.user_id:
            self.user_id = int(self.user_id)


@dataclass
class TelegramCallbackQuery:
    """
    Telegram CallbackQuery object.

    :attr callback_id: ID of the CallbackQuery
    :attr sender: User object of the sender
    :attr message: Message attached to the callback_query
    :attr data: Callback data
    """
    callback_id: Optional[int] = None
    sender: Optional[TelegramUser] = None
    message: Optional[TelegramMessage] = None
    data: Optional[str] = None

    def __init__(self, callback_query_dict: dict):
        """
        :param callback_query_dict: Callback query dictionary from update
        """
        attributes = {
            "callback_id:": "id",
            "sender": "from",
            "message": "message",
            "data": "data"
        }
        for key in attributes:
            try:
                setattr(self, key, callback_query_dict[attributes[key]])
            except KeyError:
                setattr(self, key, None)
        if self.callback_id:
            self.callback_id = int(self.callback_id)
        if self.sender:
            self.sender = TelegramUser(self.sender)
        if self.message:
            self.message = TelegramMessage(self.message)


@dataclass
class TelegramUpdate:
    """
    Telegram update object.

    :attr update_id: ID of the update
    :attr callback_query: CallbackQuery object if it exists
    :attr message: Message object if it exists
    """
    update_id: Optional[int] = None
    message: Optional[TelegramMessage] = None
    callback_query: Optional[TelegramCallbackQuery] = None

    def __init__(self, update_dict: dict):
        """
        :param update_dict: Update object dict
        """
        attributes = {
            "update_id": "update_id",
            "message": "message",
            "callback_query": "callback_query"
        }
        for key in attributes:
            try:
                setattr(self, key, update_dict[attributes[key]])
            except KeyError:
                setattr(self, key, None)
        if self.update_id:
            self.callback_id = int(self.update_id)
        if self.message:
            self.message = TelegramMessage(self.message)
        if self.callback_query:
            self.callback_query = TelegramCallbackQuery(self.callback_query)


@dataclass
class TelegramMessage:
    """
    Telegram message object.

    :attr is_bot_command: Bool of if message is bot command
    :attr chat_id: Chat ID of the message
    :attr msg_id: ID of the message
    :attr sender: Message sender User
    :attr text: Message text
    """
    is_bot_command: bool
    msg_id: Optional[int] = None
    chat_dict: Optional[dict] = None
    chat_id: Optional[int] = None
    sender: Optional[TelegramUser] = None
    text: Optional[str] = None

    def __init__(self, message_dict: dict):
        """
        :param message_dict: Message dictionary from update
        """
        attributes = {
            "msg_id": "message_id",
            "chat_dict": "chat",
            "sender": "from",
            "text": "text"
        }
        for key in attributes:
            try:
                setattr(self, key, message_dict[attributes[key]])
            except KeyError:
                setattr(self, key, None)
        if self.msg_id:
            self.msg_id = int(self.msg_id)
        if self.chat_dict:
            self.chat_id = int(self.chat_dict["id"])
        if self.sender:
            self.sender = TelegramUser(self.sender)
        self.is_bot_command = False
        try:
            if message_dict["entities"][0]["type"] == "bot_command":
                self.is_bot_command = True
        except TypeError:
            pass
        except KeyError:
            pass


@dataclass
class BotCommand:
    """
    Bot command object.

    :attr cmd_name: Slash command that triggers the bot command
    :attr msg: TelegramMessage object to read from
    """
    cmd_name: str
    msg: TelegramMessage
    bot: TelegramBot
    arguments: Optional[list]

    def __init__(self):
        if self.msg and self.cmd_name.lower() in self.msg.text.lower() and self.msg.is_bot_command:
            self.arguments = self.msg.text.split(" ")[1:]
            from_string = ""
            if self.msg.sender:
                from_string += f" from {self.msg.sender.first_name} (@{str(self.msg.sender.username)})"
            logger.debug(f"Executing command: '{self.cmd_name} {' '.join(self.arguments)}'" + from_string)
            self.execute()
        else:
            self.arguments = None

    @abstractmethod
    def execute(self):
        raise NotImplementedError


@dataclass
class CmdHelp(BotCommand):
    """
    Help command that returns list of commands from getMyCommands on /help.

    :attr command_list: Optional additional commands to add to /help command
    """
    command_list: List[Dict[str, str]] = None

    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/help"
        super().__init__()

    def execute(self):
        if not self.command_list:
            self.command_list = []
        command_list_string = ""
        self.command_list += self.bot.get_my_commands()["result"]
        for command in self.command_list:
            command_list_string += f"/{command['command']} {command['description']}\n"
        self.bot.send_message(self.msg.chat_id, command_list_string)


class CmdStart(BotCommand):
    """
    Start command that welcomes users when they send /start
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/start"
        super().__init__()

    def execute(self):
        self.bot.send_message(self.msg.chat_id, f"Hello {self.msg.sender.first_name}")
        self.msg.text = "/help"
        self.bot.help_command(self.bot, self.msg)


@dataclass
class TelegramBot:
    """
    Telegram bot object.

    :attr bot_commands: List of BotCommand to execute
    :attr commands_to_run_on_loop: List of BotCommand to execute every on_loop()
    :attr commands_to_run_on_every_message: List of BotCommand to execute on every message
    :attr help_command: Help command to use
    :attr start_command: Start command to use
    """
    BotCommand = NewType("BotCommand", Callable[["TelegramBot", TelegramMessage], None])
    bot_commands: List[BotCommand] = None
    commands_to_run_on_loop: List[BotCommand] = None
    commands_to_run_on_every_message: List[BotCommand] = None
    help_command: CmdHelp = CmdHelp
    start_command: CmdStart = CmdStart
    CallbackQueryHandler = NewType("CallbackQueryHandler", Callable[["TelegramBot", TelegramCallbackQuery], None])
    callback_query_handler: CallbackQueryHandler = None
    event_loop: asyncio.BaseEventLoop = None

    def __init__(self, access_token: str):
        if not self.bot_commands:
            self.bot_commands = []
        if not self.commands_to_run_on_loop:
            self.commands_to_run_on_loop = []
        if not self.commands_to_run_on_every_message:
            self.commands_to_run_on_every_message = []
        self.builtin_commands = [self.help_command, self.start_command]
        self.access_token = access_token
        self.api_url = f"https://api.telegram.org/bot{self.access_token}/"
        self.saved_data_path = Path("data.json")
        logger.remove()
        self.default_log_format = "<g>{time:MM/DD/YYYY HH:mm:ss}</g> | <lvl>{level}</lvl> | <lvl><b>{message}</b></lvl>"
        self.saved_data = None

    def enable_logging(self, log_level: str = "INFO", log_format: Optional[str] = None):
        """
        Enables logging.

        :param log_level: Loguru log level.
        :param log_format: Set a Loguru log format other than default.
        :return: None
        """
        if not log_format:
            log_format = self.default_log_format
        logger.add(sys.stderr, format=log_format, level=log_level, colorize=True)

    def send_message(self, chat_id: str, text: str, parse_mode: Optional[str] = None) -> requests.Response:
        """
        Sends Telegram message.

        :param chat_id: Chat ID
        :param text: Message text
        :param parse_mode: Message parsing mode
        :return: Requests response object
        """
        logger.debug(f"Sending message '{text}' to chat '{chat_id}'")
        data = {"chat_id": chat_id, "text": text}
        if parse_mode:
            data.update({"parse_mode": parse_mode})
        return requests.post(self.api_url + "sendMessage", data=data)

    def get_my_commands(self) -> list:
        """
        Sends Telegram message.

        :return: List of bot commands
        """
        return requests.get(self.api_url + "getMyCommands").json()

    def get_updates(self, offset: Optional[int] = None, allowed_updates: Optional[str] = None) -> List[TelegramUpdate]:
        """
        Retrieve Telegram updates.

        :param offset: ID of update to start from
        :param allowed_updates: Type of update allowed
        :return: Requests response object
        """
        params = {"offset": offset, "allowed_updates": allowed_updates}
        raw_updates = requests.get(self.api_url + "getUpdates", params=params).json()["result"]
        updates = []
        for update in raw_updates:
            updates.append(TelegramUpdate(update))
        return updates

    def save_json_to_file(self, data_to_save: Optional[dict] = None, file_to_save: Optional[Path] = None):
        """
        Save JSON data to file

        :param data_to_save: Dict to save
        :param file_to_save: Path to file to save
        :return: None
        """
        if not file_to_save:
            file_to_save = self.saved_data_path
        if self.saved_data:
            data_to_save = self.saved_data
        if not data_to_save:
            raise Exception("No data provided to save")
        caller_name = inspect.stack()[1][3]
        # Only save if data has changed
        self.saved_data = None
        if data_to_save != self.read_json_from_file():
            logger.debug(f"{caller_name} | Saving to JSON file '{file_to_save.resolve()}'")
            with open(file_to_save, "w") as f:
                json.dump(data_to_save, f, indent=4)
        self.saved_data = data_to_save

    def read_json_from_file(self, file_to_read: Optional[Path] = None) -> dict:
        """
        Read JSON from saved file

        :param file_to_read: Path to file to read
        :return: Dict from json
        """
        if self.saved_data:
            return self.saved_data
        if not file_to_read:
            file_to_read = self.saved_data_path
        caller_name = inspect.stack()[1][3]
        logger.debug(f"{caller_name} | Reading from JSON file '{file_to_read.resolve()}'")
        with open(file_to_read, "r") as f:
            self.saved_data = json.load(f)
            return self.saved_data

    def run_all_commands(self, commands_to_run: List[BotCommand], msg: TelegramMessage):
        """
        Run all command functions

        :param commands_to_run: List of functions to run
        :param msg: Telegram message object
        :return: None
        """
        try:
            for command in commands_to_run:
                command(self, msg)
        except Exception as e:
            if msg:
                self.send_message(msg.chat_id,
                                  f"There was an error running the command:\n{e}")
            raise e

    def run_all_commands_thread(self, commands_to_run: List[BotCommand], message: TelegramMessage):
        """
        Runs self.run_all_commands() in a thread

        :param commands_to_run: List of BotCommand
        :param message: TelegramMessage object
        :return: None
        """
        thread = threading.Thread(target=self.run_all_commands, args=(commands_to_run, message))
        thread.start()

    async def on_update(self, update: TelegramUpdate):
        """
        Code to run on every update

        :param update: TelegramUpdate object
        :return: None
        """
        self.saved_data["current_update_id"] = update.update_id + 1

        if update.callback_query:
            if self.callback_query_handler:
                self.callback_query_handler(self, update.callback_query)
            return None

        if not update.message:
            return None

        message = update.message
        logger.debug(f"New message from #{message.chat_id} "
                     f"{message.sender.first_name} (@{str(message.sender.username)})")
        if message.is_bot_command:
            self.run_all_commands_thread(self.builtin_commands + self.bot_commands, message)
        else:
            self.run_all_commands_thread(self.commands_to_run_on_every_message, message)

    async def on_loop(self):
        """
        Code to run on each loop

        :return: None
        """
        self.read_json_from_file()
        self.run_all_commands_thread(self.commands_to_run_on_loop, message=None)
        current_update_id = self.saved_data["current_update_id"]
        logger.info(f"Current update ID: {current_update_id}")

        updates = self.get_updates(current_update_id, allowed_updates="message")
        if not updates:
            return None

        for update in updates:
            await self.on_update(update)

        self.save_json_to_file()

    async def main(self):
        """
        Starts main loop.

        :return: None
        """
        self.event_loop = asyncio.get_running_loop()
        logger.info(f"Starting bot <{sys.argv[0].split('/')[-1]}>")
        enabled_commands = {
            "Commands enabled"                : [x.__name__ for x in self.bot_commands],
            "Commands to run on every message": [x.__name__ for x in self.commands_to_run_on_every_message],
            "Commands to run on loop"         : [x.__name__ for x in self.commands_to_run_on_loop]
        }
        for key, value in enabled_commands.items():
            logger.info(f"{key}: {value}")
        while True:
            try:
                await self.on_loop()
            except Exception as e:
                logger.error(e)
                logger.error(traceback.format_exc())
            await asyncio.sleep(10)

    def start(self):
        """
        Entry point function

        :return: None
        """
        asyncio.get_event_loop().run_until_complete(self.main())
