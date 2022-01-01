from pyrogram import Client
import warnings


class PyrogramPlugin(Client):
    # Decorator/wrapper that makes sure Pyrogram bot is connected before running any functions
    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        ignore_commands = ["connect", "authorize", "stop", "disconnect", "terminate", "start", "initialize"]
        if name in ignore_commands or not hasattr(attr, "__call__"):
            return attr

        if not self.is_connected:
            # Ignore RuntimeWarning self.connect() wasn't awaited
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.connect()

        def call_wrapper(*args, **kwargs):
            return attr(*args, **kwargs)
        return call_wrapper
