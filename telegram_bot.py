from __future__ import annotations
import inspect
import json
import requests
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Union
from loguru import logger


class TelegramMessage:
    """
    Telegram message object.
    :attr chat_id: Chat ID of the message
    :attr msg_id: ID of the message
    :attr sender: Message sender dict
    :attr text: Message text
    """

    def __init__(self, message_dict: dict):
        """
        :param message_dict: Message dictionary from update
        """
        self.message_dict = message_dict
        try:
            self.msg_id = int(self.message_dict["message_id"])
        except KeyError:
            self.msg_id = None
        try:
            self.chat_id = int(self.message_dict["chat"]["id"])
        except KeyError:
            self.chat_id = None
        try:
            self.sender = self.message_dict["from"]
        except KeyError:
            self.sender = None
        try:
            self.text = self.message_dict["text"]
        except KeyError:
            self.text = None
        self.is_bot_command = False
        try:
            if self.message_dict["entities"][0]["type"] == "bot_command":
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
    arguments: list
    msg: TelegramMessage
    bot: TelegramBot

    def __init__(self):
        if self.msg and self.cmd_name.lower() in self.msg.text.lower() and self.msg.is_bot_command:
            self.arguments = self.msg.text.split(" ")[1:]
            from_string = ""
            if self.msg.sender:
                from_string += f" from {self.msg.sender['first_name']} (@{self.msg.sender['username']})"
            logger.debug(f"Executing command: '{self.cmd_name} {' '.join(self.arguments)}'" + from_string)
            self.execute()

    def execute(self):
        raise NotImplementedError


@dataclass
class CmdHelp(BotCommand):
    """
    Help command that returns list of commands from getMyCommands on /help.
    :attr command_list: Optional additional commands to add to /help command
    """
    command_list: list = List[Dict[str, str]]

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


@dataclass
class TelegramBot:
    """
    Telegram bot object.
    :attr bot_commands: List of BotCommand to execute
    :attr commands_to_run_on_loop: List of BotCommand to execute every on_loop()
    :attr commands_to_run_on_every_message: List of BotCommand to execute on every message
    :attr help_command: Help command to use
    """
    BotCommand: Callable[[TelegramBot, TelegramMessage], None]
    bot_commands: List[BotCommand] = None
    commands_to_run_on_loop: List[BotCommand] = None
    commands_to_run_on_every_message: List[BotCommand] = None
    help_command: CmdHelp = CmdHelp

    def __init__(self, access_token: str):
        if not self.bot_commands:
            self.bot_commands = []
        if not self.commands_to_run_on_loop:
            self.commands_to_run_on_loop = []
        if not self.commands_to_run_on_every_message:
            self.commands_to_run_on_every_message = []
        self.access_token = access_token
        self.api_url = f"https://api.telegram.org/bot{self.access_token}/"
        self.saved_data_path = Path("data.json")
        logger.remove()
        self.default_log_format = "<g>{time:MM/DD/YYYY HH:mm:ss}</g> | <lvl>{level}</lvl> | <lvl><b>{message}</b></lvl>"
        self.saved_data = None

    def enable_logging(self, log_level: str = "INFO", log_format: str = None) -> None:
        """
        Enables logging.
        :param log_level: Loguru log level.
        :param log_format: Set a Loguru log format other than default.
        :return: None
        """
        if not log_format:
            log_format = self.default_log_format
        logger.add(sys.stderr, format=log_format, level=log_level, colorize=True)

    def send_message(self, chat_id: str, text: str, parse_mode: str = None) -> requests.Response:
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

    def get_updates(self, offset: int = None, allowed_updates: str = None) -> requests.Response:
        """
        Retrieve Telegram updates.
        :param offset: ID of update to start from
        :param allowed_updates: Type of update allowed
        :return: Requests response object
        """
        params = {"offset": offset, "allowed_updates": allowed_updates}
        return requests.get(self.api_url + "getUpdates", params=params)

    def run_commands(self, commands_to_run: List[Callable[[TelegramBot, TelegramMessage], None]],
                     msg: TelegramMessage) -> None:
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

    @staticmethod
    def check_if_update_a_message(update_to_check: dict) -> Union[dict, bool]:
        """
        Check if Telegram update object is a message
        :param update_to_check: Update object to check
        :return: Message object or False
        """
        try:
            return update_to_check["message"]

        # if not a message
        except KeyError:
            return False

    def save_json_to_file(self, data_to_save: dict, file_to_save: Path = None) -> None:
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
        caller_name = inspect.stack()[1][3]
        logger.debug(f"{caller_name} | Saving to JSON file '{file_to_save.resolve()}'")
        with open(file_to_save, "w") as f:
            json.dump(data_to_save, f, indent=4)

    def read_json_from_file(self, file_to_read: Path = None) -> dict:
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

    def on_loop(self) -> None:
        """
        Code to run on each loop
        :return: None
        """
        self.run_commands(self.commands_to_run_on_loop, msg=None)

        saved_data = self.read_json_from_file()
        current_update_id = saved_data["current_update_id"]
        logger.info(f"Current update ID: {current_update_id}")

        updates = self.get_updates(current_update_id, allowed_updates="message").json()["result"]
        for update in updates:
            # set current_update_id to latest update_id
            saved_data["current_update_id"] = update["update_id"] + 1
            message = self.check_if_update_a_message(update)

            if not message:
                break
            message = TelegramMessage(message)
            logger.debug(f"New message from #{message.chat_id} "
                         f"{message.sender['first_name']} (@{message.sender['username']})")
            if message.is_bot_command:
                self.help_command(self, message)
                self.run_commands(self.bot_commands, message)
            else:
                self.run_commands(self.commands_to_run_on_every_message, message)
        if updates:
            self.save_json_to_file(saved_data)

    def start(self) -> None:
        """
        Starts main loop.
        :return: None
        """
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
                self.on_loop()
            except Exception as e:
                logger.error(e)
                logger.error(traceback.format_exc())
            time.sleep(10)
