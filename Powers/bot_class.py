import asyncio
from platform import python_version
from threading import RLock
from time import gmtime, strftime
from time import time as t

from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from pyrogram.types import BotCommand

from Powers import (
    API_HASH, API_ID, BOT_TOKEN,
    LOG_DATETIME, LOGFILE, LOGGER,
    MESSAGE_DUMP, NO_LOAD, UPTIME, WORKERS,
    load_cmds, load_aiogram_routers, scheduler,
    aiogram_bot, aiogram_dp,
    tele_client,
)
from Powers.database import MongoDB
from Powers.plugins import all_plugins
from Powers.plugins.scheduled_jobs import *
from Powers.supports import *
from Powers.vars import Config

INITIAL_LOCK = RLock()


class Gojo(Client):
    """
    Main bot class.
    ✅ Pyrogram  — @Gojo.on_message plugins (auto loaded from plugins/)
    ✅ Telethon  — @bot.on(events...) plugins (auto loaded from plugins/)
    ✅ Aiogram   — router plugins (auto loaded — bas plugin vich router rakh do)
    
    Koi naya plugin banana ho:
    - Powers/plugins/myplugin.py banao
    - Pyrogram lyi: @Gojo.on_message use karo
    - Aiogram lyi: router = Router() banao + handlers likho — AUTO load hoga
    - Telethon lyi: @tele_client.on(events...) use karo
    - Bas! Kuch aur nahi karna
    """

    def __init__(self):
        super().__init__(
            "Gojo_Satoru",
            bot_token=BOT_TOKEN,
            plugins=dict(root="Powers.plugins", exclude=NO_LOAD),
            api_id=API_ID,
            api_hash=API_HASH,
            workers=WORKERS,
        )

    async def start(self, use_qr=False, except_ids=[]):

        # ── 1. PYROGRAM ───────────────────────────────────────────────────────
        await super().start(use_qr=use_qr, except_ids=except_ids)
        await self.set_bot_commands([
            BotCommand("start",  "Check if bot is alive"),
            BotCommand("help",   "Get help menu"),
            BotCommand("donate", "Buy me a coffee"),
            BotCommand("bug",    "Report a bug"),
        ])
        meh = await self.get_me()
        Config.BOT_ID       = meh.id
        Config.BOT_NAME     = meh.first_name
        Config.BOT_USERNAME = meh.username
        LOGGER.info(f"✅ Pyrogram v{__version__} (Layer {layer}) — @{meh.username}")

        startmsg = await self.send_message(MESSAGE_DUMP, "<i>⏳ Starting all clients...</i>")

        # ── 2. TELETHON ───────────────────────────────────────────────────────
        try:
            await tele_client.start(bot_token=BOT_TOKEN)
            tele_me = await tele_client.get_me()
            LOGGER.info(f"✅ Telethon started — @{tele_me.username}")
            tele_status = f"🟢 Telethon — @{tele_me.username}"
        except Exception as e:
            LOGGER.error(f"❌ Telethon failed: {e}")
            tele_status = f"🔴 Telethon — failed"

        # ── 3. AIOGRAM — auto load all routers from plugins/ ──────────────────
        # Koi manually include_router nahi karna — sab auto hoga
        load_aiogram_routers()
        try:
            self._aiogram_task = asyncio.create_task(
                aiogram_dp.start_polling(aiogram_bot, handle_signals=False)
            )
            LOGGER.info("✅ Aiogram polling started.")
            aiogram_status = "🟢 Aiogram — polling"
        except Exception as e:
            LOGGER.error(f"❌ Aiogram failed: {e}")
            aiogram_status = f"🔴 Aiogram — failed"

        # ── Load Pyrogram plugins + help menu ─────────────────────────────────
        cmd_list = await load_cmds(await all_plugins())
        await load_support_users()
        await cache_support()

        from Powers import SUPPORT_USERS
        LOGGER.info(f"Dev Users       : {SUPPORT_USERS['Dev']}")
        LOGGER.info(f"Sudo Users      : {SUPPORT_USERS['Sudo']}")
        LOGGER.info(f"Whitelist Users : {SUPPORT_USERS['White']}")
        LOGGER.info(f"Plugins Loaded  : {cmd_list}")

        # ── Scheduler ─────────────────────────────────────────────────────────
        if Config.BDB_URI:
            scheduler.add_job(send_wishish, "cron", [self], hour=0, minute=0, second=0)
            scheduler.start()

        # ── Startup message ───────────────────────────────────────────────────
        await startmsg.edit_text(
            f"<b>✅ Gojo Satoru Started!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>Bot:</b> @{meh.username}\n"
            f"🆔 <b>ID:</b> <code>{meh.id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Libraries:</b>\n"
            f"  🟢 Pyrogram v{__version__} (Layer {layer})\n"
            f"  {tele_status}\n"
            f"  {aiogram_status}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Python:</b> <code>{python_version()}</code>\n\n"
            f"<b>Loaded Plugins:</b>\n<i>{cmd_list}</i>",
        )
        LOGGER.info("✅ All clients started!\n")

    async def stop(self):
        runtime = strftime("%Hh %Mm %Ss", gmtime(t() - UPTIME))
        LOGGER.info("Stopping all clients...")
        scheduler.remove_all_jobs()

        # Stop Aiogram
        if hasattr(self, "_aiogram_task"):
            self._aiogram_task.cancel()
            try:
                await self._aiogram_task
            except asyncio.CancelledError:
                pass
        try:
            await aiogram_bot.session.close()
            LOGGER.info("✅ Aiogram stopped.")
        except Exception:
            pass

        # Stop Telethon
        try:
            if tele_client.is_connected():
                await tele_client.disconnect()
                LOGGER.info("✅ Telethon disconnected.")
        except Exception:
            pass

        # Upload logs + stop Pyrogram
        try:
            await self.send_document(
                MESSAGE_DUMP,
                document=LOGFILE,
                caption=(
                    f"🔴 <b>Bot Stopped!</b>\n"
                    f"⏱ Uptime: <code>{runtime}</code>\n"
                    f"📅 <code>{LOG_DATETIME}</code>"
                ),
            )
        except Exception:
            pass

        await super().stop()
        MongoDB.close()
        LOGGER.info(f"✅ Stopped cleanly. Runtime: {runtime}")
