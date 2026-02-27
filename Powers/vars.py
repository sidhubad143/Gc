from os import getcwd, path

from prettyconf import Configuration
from prettyconf.loaders import EnvFile, Environment

env_file = f"{getcwd()}/.env"
config = Configuration(loaders=[Environment(), EnvFile(filename=env_file)])
is_env = path.isfile(env_file)


class Config:
    """Config class for variables."""

    LOGGER = True

    # ── Bot Credentials (same token for Pyrogram + Telethon + Aiogram) ────────
    BOT_TOKEN = config("BOT_TOKEN", default=None)
    API_ID    = int(config("API_ID", default="123"))
    API_HASH  = config("API_HASH", default=None)

    # ── Owner & Users ─────────────────────────────────────────────────────────
    OWNER_ID     = int(config("OWNER_ID", default=1344569458))
    MESSAGE_DUMP = int(config("MESSAGE_DUMP", default="0"))
    DEV_USERS = [
        int(i) for i in config("DEV_USERS", default="").split(None)
    ]
    SUDO_USERS = [
        int(i) for i in config("SUDO_USERS", default="").split(None)
    ]
    WHITELIST_USERS = [
        int(i) for i in config("WHITELIST_USERS", default="").split(None)
    ]

    # ── API Keys ──────────────────────────────────────────────────────────────
    GENIUS_API_TOKEN = config("GENIUS_API", default=None)
    RMBG_API         = config("RMBG_API", default=None)

    # ── Database ──────────────────────────────────────────────────────────────
    DB_URI  = config("DB_URI", default=None)
    DB_NAME = config("DB_NAME", default="gojo_satarou")
    BDB_URI = config("BDB_URI", default=None)

    # ── Bot Settings ──────────────────────────────────────────────────────────
    NO_LOAD         = config("NO_LOAD", default="").split()
    PREFIX_HANDLER  = config("PREFIX_HANDLER", default="/").split()
    SUPPORT_GROUP   = config("SUPPORT_GROUP", default="gojo_bots_network")
    SUPPORT_CHANNEL = config("SUPPORT_CHANNEL", default="SUPPORT_CHANNEL")
    WORKERS         = int(config("WORKERS", default=16))
    TIME_ZONE       = config("TIME_ZONE", default="Asia/Kolkata")

    # ── Auto-filled at runtime ────────────────────────────────────────────────
    BOT_USERNAME = ""
    BOT_ID       = ""
    BOT_NAME     = ""


class Development:
    """Development class — fill manually if not using .env"""

    LOGGER = True

    BOT_TOKEN = "YOUR_BOT_TOKEN"
    API_ID    = 12345
    API_HASH  = "YOUR_API_HASH"

    OWNER_ID     = 1344569458
    MESSAGE_DUMP = 0

    DEV_USERS       = []
    SUDO_USERS      = []
    WHITELIST_USERS = []

    GENIUS_API_TOKEN = ""
    RMBG_API         = ""

    DB_URI  = ""
    DB_NAME = "gojo_satarou"
    BDB_URI = ""

    NO_LOAD         = []
    PREFIX_HANDLER  = ["/", "!", "$"]
    SUPPORT_GROUP   = "SUPPORT_GROUP"
    SUPPORT_CHANNEL = "SUPPORT_CHANNEL"
    WORKERS         = 8
    TIME_ZONE       = "Asia/Kolkata"

    BOT_USERNAME = ""
    BOT_ID       = ""
    BOT_NAME     = ""
