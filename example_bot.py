from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from pyarr import RadarrAPI, SonarrAPI
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
    /radarr <IMDB ID> | queue | remove <IMDB ID> - Adds or removes a movie from to/from Radarr
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/radarr"
        super().__init__()

    def get_queue(self):
        try:
            queue_records = self.radarr.get_queue()["records"]
        except TypeError:
            queue_records = []
        dls = []
        for dl in queue_records:
            if dl["status"] == "downloading":
                print(dl['title'])
                dls.append({"title": dl["title"], "time left HH:MM:SS": dl["timeleft"], "status": dl["status"]})
        self.bot.send_message(self.msg.chat_id, json.dumps(dls, indent=4))

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

        if query.lower() == "queue":
            self.get_queue()
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

@dataclass
class SonarrCommand(BotCommand, ABC):
    sonarr_url: str
    sonarr_api_key: str

    def __init__(self):
        self.sonarr_url = "<sonarr_url>"
        self.sonarr_api_key = "<sonarr_api_key>"
        self.sonarr = SonarrAPI(self.sonarr_url, self.sonarr_api_key)
        super().__init__()


class CmdSonarr(SonarrCommand):
    """
    /sonarr <TVDB ID> | queue | remove <TVDB ID> | monitor/unmonitor <TVDB ID> <season>
    - Adds/removes a series or monitor/unmonitor a series' season
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/sonarr"
        super().__init__()

    def get_series_from_tvdb_id(self, tvdb_id: int) -> dict:
        try:
            tvdb_id = int(tvdb_id)
        except ValueError:
            self.bot.send_message(self.msg.chat_id, "TVDB ID must be int")
            return None
        series = {}
        for s in self.sonarr.get_series():
            if s['tvdbId'] == tvdb_id:
                series = s
        if not series:
            self.bot.send_message(self.msg.chat_id, "Series not found")
            return None
        return series

    def update_show_season_monitored_status(self, tvdb_id: int, season: int, monitored: bool, sendmsg: bool = True):
        series = self.get_series_from_tvdb_id(tvdb_id)
        if not series:
            return None
        show_id = series['id']
        try:
            series = self.sonarr.get_series(show_id)
            series['seasons'][season]['monitored'] = monitored
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "Season not found")
            return None
        except TypeError:
            return None

        self.sonarr.upd_series(series)
        if sendmsg:
            self.bot.send_message(self.msg.chat_id,
                                  f"Set {series['title']} ({series['year']}) "
                                  f"season {season} monitored status to {monitored}")

    def unmonitor_all_seasons(self, tvdb_id: int):
        series = self.get_series_from_tvdb_id(tvdb_id)
        if not series:
            return None
        for season in self.sonarr.lookup_series_by_tvdb_id(series['tvdbId'])[0]['seasons']:
            self.update_show_season_monitored_status(tvdb_id, season['seasonNumber'], False, sendmsg=False)

    def remove_show(self):
        try:
            query = self.arguments[1]
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "No TVDB ID given")
            return None

        show_result = self.sonarr.lookup_series_by_tvdb_id(query)[0]
        series = self.get_series_from_tvdb_id(show_result['tvdbId'])
        if not series:
            return None
        show_id = series['id']

        del_series = None
        try:
            del_series = self.sonarr.del_series(show_id, delete_files=True)
        except json.JSONDecodeError:
            pass
        try:
            if del_series['message']:
                self.bot.send_message(self.msg.chat_id, del_series['message'])
                return None
        except KeyError:
            pass
        show_title = show_result['title']
        show_year = show_result['year']
        self.bot.send_message(self.msg.chat_id, f"Removed show: {show_title} ({show_year})")

    def get_queue(self):
        try:
            queue_records = self.sonarr.get_queue()["records"]
        except TypeError:
            queue_records = []
        dls = []
        for dl in queue_records:
            if dl["status"] == "downloading":
                print(dl['title'])
                dls.append({"title": dl["title"], "time left HH:MM:SS": dl["timeleft"], "status": dl["status"]})
        self.bot.send_message(self.msg.chat_id, json.dumps(dls, indent=4))

    def execute(self):
        try:
            query = self.arguments[0]
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "No query given")
            return None

        if query.lower() == "remove":
            self.remove_show()
            return None

        if query.lower() == "queue":
            self.get_queue()
            return None

        def get_season():
            try:
                s = self.arguments[2]
            except IndexError:
                self.bot.send_message(self.msg.chat_id, "No season specified")
                return None
            try:
                int(s)
            except ValueError:
                self.bot.send_message(self.msg.chat_id, "Season must be int")
                return None
            return int(s)

        if query.lower() == "monitor" or "unmonitor":
            season = get_season()
            if not season:
                return None
            if query.lower() == "monitor":
                set_monitor = True
            else:
                set_monitor = False

            self.update_show_season_monitored_status(self.arguments[1], season, set_monitor)

        show_result = self.sonarr.lookup_series_by_tvdb_id(query)[0]
        if not show_result:
            self.bot.send_message(self.msg.chat_id, f"No result found for: {query}")
            return None
        show_id = show_result['tvdbId']
        add_show = self.sonarr.add_series(show_id, quality_profile_id=6, root_dir="<root_dir>")
        try:
            if add_show[0]["errorMessage"]:
                self.bot.send_message(self.msg.chat_id, add_show[0]["errorMessage"])
                return None
        except KeyError:
            pass
        # Optional: Unmonitor all seasons after adding
        self.unmonitor_all_seasons(show_id)
        self.bot.send_message(self.msg.chat_id, f"Added show: {add_show['title']} ({add_show['year']})")


class CmdFindShows(SonarrCommand):
    """
    /find_shows <search term> - Returns a table of shows and TVDB IDs matching search term
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/find_shows"
        super().__init__()

    def execute(self):
        query = " ".join(self.arguments)
        if not query:
            self.bot.send_message(self.msg.chat_id, "No query given")
            return None
        show_search = self.sonarr.lookup_series(query)
        if not show_search:
            self.bot.send_message(self.msg.chat_id, f"No result found for: {query}")
            return None
        results = []
        for show in show_search:
            try:
                tvdb_id = str(show['tvdbId'])
            except KeyError:
                tvdb_id = "<none found>"
            results += [(f"{show['title']}", f"{str(show['year'])}", f"{tvdb_id}")]
        results_data = pd.DataFrame(results[:20])
        results_data.columns = ["Show Name", "Year", "TVDB ID"]
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
    /ytdl <video URL> | mp3 <video URL> - Sends a video or mp3 file from any website supported by youtube-dl
    """
    def __init__(self, bot: TelegramBot, msg: TelegramMessage):
        self.bot = bot
        self.msg = msg
        self.cmd_name = "/ytdl"
        self.download_path = Path("./downloads").resolve()
        super().__init__()

    def execute(self):
        getmp3 = False
        try:
            link = self.arguments[0]
            if link.lower() == "mp3":
                getmp3 = True
                link = self.arguments[1]
        except IndexError:
            self.bot.send_message(self.msg.chat_id, "No link given")
            return None

        ydl_opts = {
            'outtmpl': f'{self.download_path}/%(id)s.%(ext)s'
        }

        if getmp3:
            ydl_opts.update({
                # 'ffmpeg_location': '',
                'format'        : 'bestaudio/best',
                'postprocessors': [{
                    'key'             : 'FFmpegExtractAudio',
                    'preferredcodec'  : 'mp3',
                    'preferredquality': '192',
                }]
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
        CmdFindShows,
        CmdKanye,
        CmdRadarr,
        CmdSonarr,
        CmdWikipedia,
        CmdYouTubeDL,
    ]

    example_bot.start()


if __name__ == "__main__":
    main()
