import shutil
from datetime import datetime
from importlib import import_module as imp_mod
from logging import (INFO, WARNING, FileHandler, StreamHandler, basicConfig,
                     getLogger)
from os import environ, listdir, mkdir, path
from platform import python_version
from sys import exit as sysexit
from sys import stdout, version_info
from time import time
from traceback import format_exc

import lyricsgenius
import pyrogram
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Aiogram ───────────────────────────────────────────────────────────────────
from aiogram import Bot as AiogramBot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode as AiogramParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# ── Telethon ──────────────────────────────────────────────────────────────────
from telethon import TelegramClient

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGGING SETUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOG_DATETIME = datetime.now().strftime("%d_%m_%Y-%H_%M_%S")
LOGDIR = f"{__name__}/logs"

if path.isdir(LOGDIR):
    shutil.rmtree(LOGDIR)
mkdir(LOGDIR)
LOGFILE = f"{LOGDIR}/{__name__}_{LOG_DATETIME}_log.txt"

file_handler   = FileHandler(filename=LOGFILE)
stdout_handler = StreamHandler(stdout)

basicConfig(
    format="%(asctime)s - [Gojo_Satoru] - %(levelname)s - %(message)s",
    level=INFO,
    handlers=[file_handler, stdout_handler],
)

getLogger("pyrogram").setLevel(WARNING)
getLogger("telethon").setLevel(WARNING)
getLogger("aiogram").setLevel(WARNING)

LOGGER = getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PYTHON VERSION CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if version_info[0] < 3 or version_info[1] < 7:
    LOGGER.error(
        "You MUST have a Python Version of at least 3.7!\n"
        "Multiple features depend on this. Bot quitting."
    )
    sysexit(1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOAD CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

try:
    from Powers.vars import is_env

    if is_env or environ.get("ENV"):
        from Powers.vars import Config
    else:
        from Powers.vars import Development as Config
except Exception as ef:
    LOGGER.error(ef)
    LOGGER.error(format_exc())
    sysexit(1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIMEZONE + VERSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIME_ZONE = pytz.timezone(Config.TIME_ZONE)

Vpath = "./Version"
version = [
    i for i in listdir(Vpath) if i.startswith("version") and i.endswith("md")
]
VERSION          = sorted(version)[-1][8:-3]
PYTHON_VERSION   = python_version()
PYROGRAM_VERSION = pyrogram.__version__

LOGGER.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
LOGGER.info("         Gojo_Satoru Bot           ")
LOGGER.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
LOGGER.info(f"Version   : {VERSION}")
LOGGER.info(f"Owner     : {Config.OWNER_ID}")
LOGGER.info(f"TimeZone  : {Config.TIME_ZONE}")
LOGGER.info(f"Pyrogram  : v{PYROGRAM_VERSION}")
LOGGER.info(f"Python    : {PYTHON_VERSION}")
LOGGER.info("Source    : https://github.com/Gojo-Bots/Gojo_Satoru\n")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GENIUS LYRICS API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOGGER.info("Checking Lyrics Genius API...")
if Config.GENIUS_API_TOKEN:
    LOGGER.info("Genius API token found — initialising client...")
    genius_lyrics = lyricsgenius.Genius(
        Config.GENIUS_API_TOKEN,
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)"],
        remove_section_headers=True,
    )
    is_genius_lyrics      = True
    genius_lyrics.verbose = False
    LOGGER.info("✅ Genius client ready.")
else:
    LOGGER.info("Genius API not found — /lyrics won't work.")
    is_genius_lyrics = False
    genius_lyrics    = False

# ── RMBG API ──────────────────────────────────────────────────────────────────
is_rmbg = False
RMBG    = None
if Config.RMBG_API:
    is_rmbg = True
    RMBG    = Config.RMBG_API

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BOT CREDENTIALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BOT_TOKEN = Config.BOT_TOKEN
API_ID    = Config.API_ID
API_HASH  = Config.API_HASH

MESSAGE_DUMP    = Config.MESSAGE_DUMP or Config.OWNER_ID
SUPPORT_GROUP   = Config.SUPPORT_GROUP
SUPPORT_CHANNEL = Config.SUPPORT_CHANNEL
OWNER_ID        = Config.OWNER_ID

SUPPORT_USERS = {
    "Owner" : [Config.OWNER_ID],
    "Dev"   : set(Config.DEV_USERS),
    "Sudo"  : set(Config.SUDO_USERS),
    "White" : set(Config.WHITELIST_USERS),
}

DB_URI         = Config.DB_URI
DB_NAME        = Config.DB_NAME
NO_LOAD        = Config.NO_LOAD
WORKERS        = Config.WORKERS
BDB_URI        = Config.BDB_URI
PREFIX_HANDLER = Config.PREFIX_HANDLER

HELP_COMMANDS = {}
UPTIME        = time()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ── 1. AIOGRAM CLIENT (Bot Token) ─────────────────
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOGGER.info("Initialising Aiogram bot...")
aiogram_bot = AiogramBot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=AiogramParseMode.HTML),
)
aiogram_dp = Dispatcher(storage=MemoryStorage())
LOGGER.info("✅ Aiogram ready.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ── 2. TELETHON CLIENT (Bot Token — no session) ───
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOGGER.info("Initialising Telethon bot client...")
tele_client = TelegramClient(
    "telethon_bot",          # session file name (bot session, auto-created)
    api_id=API_ID,
    api_hash=API_HASH,
)
LOGGER.info("✅ Telethon client ready (bot token mode).")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEMP DIRECTORIES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

youtube_dir = "./Youtube/"
if path.isdir(youtube_dir):
    shutil.rmtree(youtube_dir)
mkdir(youtube_dir)

scrap_dir = "./scrapped/"
if path.isdir(scrap_dir):
    shutil.rmtree(scrap_dir)
mkdir(scrap_dir)

scheduler = AsyncIOScheduler(timezone=TIME_ZONE)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PLUGIN LOADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def load_cmds(all_plugins):
    """Load all plugins and register them in HELP_COMMANDS."""
    for single in all_plugins:
        if single.lower() in [i.lower() for i in Config.NO_LOAD]:
            LOGGER.warning(f"Skipping '{single}' — in NO_LOAD list.")
            continue

        imported_module = imp_mod(f"Powers.plugins.{single}")
        if not hasattr(imported_module, "__PLUGIN__"):
            continue

        plugin_name      = imported_module.__PLUGIN__.lower()
        plugin_dict_name = f"plugins.{plugin_name}"
        plugin_help      = imported_module.__HELP__

        if plugin_dict_name in HELP_COMMANDS:
            raise Exception(
                f"Two plugins with same name detected!\n"
                f"Error while importing '{imported_module.__name__}'"
            )

        HELP_COMMANDS[plugin_dict_name] = {
            "buttons"    : [],
            "disablable" : [],
            "alt_cmds"   : [],
            "help_msg"   : plugin_help,
        }

        if hasattr(imported_module, "__buttons__"):
            HELP_COMMANDS[plugin_dict_name]["buttons"] = imported_module.__buttons__
        if hasattr(imported_module, "_DISABLE_CMDS_"):
            HELP_COMMANDS[plugin_dict_name]["disablable"] = imported_module._DISABLE_CMDS_
        if hasattr(imported_module, "__alt_name__"):
            HELP_COMMANDS[plugin_dict_name]["alt_cmds"] = imported_module.__alt_name__

        HELP_COMMANDS[plugin_dict_name]["alt_cmds"].append(plugin_name)

    if NO_LOAD:
        LOGGER.warning(f"Skipped Plugins — {NO_LOAD}")

    return (
        ", ".join((i.split(".")[1]).capitalize() for i in list(HELP_COMMANDS.keys())) + "\n"
    )
