from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from pyarr import RadarrAPI
from pyrogram import Client
from telegram_bot import BotCommand, TelegramMessage, TelegramBot
import pandas as pd
import json
import os
import requests
import wikipedia
import youtube_dl


@dataclass
class RadarrCommand(BotCommand, ABC):
    radarr_url: str
    radarr_api_key: str

    def __init__(self):
        self.radarr_url = "<radarr_url>"
        self.radarr_api_key = "<radarr_api_key>"
        self.radarr = RadarrAPI(self.radarr_url, self.radarr_api_key)
        super().__init__()


class CmdRadarr(RadarrCommand):
    """
    /radarr <IMDB ID> | remove <IMDB ID> - Adds or removes a movie from Radarr
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/radarr"
        super().__init__()

    def remove_movie(self):
        try:
            query = self.arguments[1]
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "No IMDB ID given")
            return None

        movie_result = self.radarr.lookup_movie_by_imdb_id(query)
        try:
            movie_id = movie_result[0]['id']
        except KeyError:
            self.bot.send_message(self.msg.chat_id, "Movie is not added")
            return None

        try:
            self.radarr.del_movie(movie_id, delete_files=True)
        except json.JSONDecodeError:
            pass
        movie_title = movie_result[0]['title']
        movie_year = movie_result[0]['year']
        self.bot.send_message(self.msg.chat_id, f"Removed movie: {movie_title} ({movie_year})")

    def execute(self):
        try:
            query = self.arguments[0]
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "No query given")
            return None

        if query.lower() == "remove":
            self.remove_movie()
            return None

        movie_result = self.radarr.lookup_movie_by_imdb_id(query)
        if not movie_result:
            self.bot.send_message(self.msg.chat_id, f"No result found for: {query}")
            return None
        add_movie = self.radarr.add_movie(movie_result[0]['imdbId'], quality_profile_id=6,
                                          root_dir="/data/media/Movies", search_for_movie=True, tmdb=False)
        try:
            if "errorMessage" in add_movie[0]:
                self.bot.send_message(self.msg.chat_id, add_movie[0]["errorMessage"])
                return None
        except KeyError:
            pass

        self.bot.send_message(self.msg.chat_id, f"Added movie: {add_movie['title']} ({add_movie['year']})")


class CmdFindMovies(RadarrCommand):
    """
    /find_movies <search term> - Returns a table of movies and IMDB IDs matching search term
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/find_movies"
        super().__init__()

    def execute(self):
        query = " ".join(self.arguments)
        if not query:
            self.bot.send_message(self.msg.chat_id, "No query given")
            return None
        movie_search = self.radarr.lookup_movie(query)
        if not movie_search:
            self.bot.send_message(self.msg.chat_id, f"No result found for: {query}")
            return None
        results = []
        for movie in movie_search:
            try:
                imdb_id = movie['imdbId']
            except KeyError:
                imdb_id = "<none found>"
            results += [(f"{movie['title']}", f"{movie['year']}", f"{imdb_id}")]
        results_data = pd.DataFrame(results)
        results_data.columns = ["Movie Name", "Year", "IMDB ID"]
        sorted_results_data = results_data.sort_values(by=['Year'], ascending=False, ignore_index=True)
        pd.set_option('display.colheader_justify', 'center')
        self.bot.send_message(self.msg.chat_id,
                              f"```{sorted_results_data.to_string(max_colwidth=1)}```", parse_mode="MarkdownV2")


class CmdKanye(BotCommand):
    """
    /kanye - Returns a Kanye quote
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/kanye"
        super().__init__()

    def execute(self):
        response = requests.get("https://api.kanye.rest")
        quote = f'"{response.json()["quote"]}"\n-Kanye West'
        self.bot.send_message(self.msg.chat_id, quote)


class CmdYouTubeDL(BotCommand):
    """
    /youtube_dl <video URL> - Sends a video file from any website supported by youtube-dl
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/youtube_dl"
        self.download_path = Path(".ignore/downloads").resolve()
        super().__init__()

    def execute(self):
        try:
            link = self.arguments[0]
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "No link given")
            return None
        ydl = youtube_dl.YoutubeDL({'outtmpl': f'{self.download_path}/%(id)s.%(ext)s'})
        with ydl:
            result = ydl.extract_info(link, download=True)

        video_file_path = [Path(f).resolve() for f in self.download_path.iterdir()][0]

        self.bot.send_document(self.msg.chat_id, video_file_path)

        for f in self.download_path.iterdir():
            os.remove(Path(f))


class CmdWikipedia(BotCommand):
    """
    /wikipedia <search term> - Returns a Wikipedia page matching search term
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/wikipedia"
        super().__init__()

    def execute(self):
        query = " ".join(self.arguments)
        if not query:
            self.bot.send_message(self.msg.chat_id, "No query given")
            return None
        try:
            first_search_result = wikipedia.search(query)[0]
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "No results found for query")
            return None
        wiki_page = wikipedia.page(first_search_result, auto_suggest=False)
        wiki_summary = wikipedia.summary(wiki_page.title, sentences=2, auto_suggest=False)

        message_text = f"<b>{wiki_page.title}:</b>\n{wiki_summary}\n\n{wiki_page.url}"
        self.bot.send_message(self.msg.chat_id, message_text, parse_mode="html")


class ExampleBot(TelegramBot):

    def __init__(self, access_token: str, api_id: int, api_hash: str):
        super().__init__(access_token)
        self.pyrogram_client = Client("example_bot_MTProto", api_id, api_hash, phone_number="<phone_number>")
        self.pyrogram_bot = Client("example_bot", api_id, api_hash, bot_token=access_token)

    def delete_message(self, msg: TelegramMessage):
        with self.pyrogram_client:
            self.pyrogram_client.delete_messages(msg.chat_id, msg.msg_id)

    def send_document(self, chat_id: int, document: Path):
        with self.pyrogram_bot:
            self.pyrogram_bot.send_document(chat_id, document)


def main():
    api_id = 12345
    api_hash = "<api_hash>"
    access_token = "<access_token>"
    example_bot = ExampleBot(access_token, api_id, api_hash)
    example_bot.enable_logging("DEBUG")

    # example_bot.saved_data_path = Path("data.json") (default)

    example_bot.bot_commands = [
        CmdFindMovies,
        CmdKanye,
        CmdRadarr,
        CmdWikipedia,
        CmdYouTubeDL,
    ]

    example_bot.start()


if __name__ == "__main__":
    main()