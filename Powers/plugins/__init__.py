from sys import exit as exiter


async def all_plugins():
    """
    Auto-detects all .py files in this folder (except __init__.py)
    and returns them as a sorted list for the plugin loader.
    """
    from glob import glob
    from os.path import basename, dirname, isfile

    mod_paths = glob(f"{dirname(__file__)}/*.py")
    all_plugs = [
        basename(f)[:-3]
        for f in mod_paths
        if isfile(f) and f.endswith(".py") and not f.endswith("__init__.py")
    ]
    return sorted(all_plugs)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BIRTHDAY DB (optional — only if BDB_URI is set)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from Powers import BDB_URI, LOGGER

if BDB_URI:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    try:
        BIRTHDAY_DB  = MongoClient(BDB_URI)
        Birth_main_db = BIRTHDAY_DB["birthdays"]
        bday_info    = Birth_main_db["users_bday"]
        bday_cinfo   = Birth_main_db["chat_bday"]
        LOGGER.info("✅ Birthday DB connected.")
    except PyMongoError as f:
        LOGGER.error(f"❌ Birthday DB error: {f}")
        exiter(1)


# ── Utility ───────────────────────────────────────────────────────────────────

from datetime import datetime


def till_date(date: str) -> datetime:
    """Convert date string to datetime object."""
    return datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
