import asyncio

from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode

from Powers import LOGGER
from Powers.utils.parser import mention_html
from Powers.utils.admin_check_aiogram import is_admin_silent
from Powers.database import MongoDB

router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB — per chat settings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EditSettings(MongoDB):
    db_name = "edit_settings"

    def __init__(self):
        super().__init__(self.db_name)

    def get(self, chat_id: int) -> dict:
        doc = self.find_one({"chat_id": chat_id})
        return doc or {"anti_edit": False, "anti_long": False, "long_limit": 200}

    def _save(self, chat_id: int, key: str, value):
        existing = self.find_one({"chat_id": chat_id})
        if existing:
            self.update({"chat_id": chat_id}, {"$set": {key: value}})
        else:
            data = {"chat_id": chat_id, "anti_edit": False, "anti_long": False, "long_limit": 200}
            data[key] = value
            self.insert_one(data)

    def set_anti_edit(self, chat_id: int, val: bool):
        self._save(chat_id, "anti_edit", val)

    def set_anti_long(self, chat_id: int, val: bool):
        self._save(chat_id, "anti_long", val)

    def set_long_limit(self, chat_id: int, limit: int):
        self._save(chat_id, "long_limit", limit)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _name(user) -> str:
    return await mention_html(user.first_name or "User", user.id)


async def _warn_delete(bot: Bot, chat_id: int, text: str, delay: int = 10):
    try:
        m = await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
        await asyncio.sleep(delay)
        await m.delete()
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ANTI EDIT HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.edited_message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def anti_edit(message: Message, bot: Bot):
    if not message.from_user:
        return

    cfg = EditSettings().get(message.chat.id)
    if not cfg.get("anti_edit", False):
        return

    if await is_admin_silent(bot, message.chat.id, message.from_user.id):
        return

    try:
        await message.delete()
        asyncio.create_task(_warn_delete(
            bot, message.chat.id,
            f"✏️ {await _name(message.from_user)} ᴇᴅɪᴛᴇᴅ ᴍꜱɢ ᴅᴇʟᴇᴛᴇᴅ 🚫"
        ))
    except Exception as ef:
        LOGGER.error(f"[anti_edit] {ef}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ANTI LONG MESSAGE HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def anti_long_msg(message: Message, bot: Bot):
    if not message.from_user:
        return
    if not message.text:
        return
    if message.text.startswith("/"):
        return

    cfg = EditSettings().get(message.chat.id)
    if not cfg.get("anti_long", False):
        return

    limit = cfg.get("long_limit", 200)
    word_count = len(message.text.split())

    if word_count <= limit:
        return

    if await is_admin_silent(bot, message.chat.id, message.from_user.id):
        return

    try:
        await message.delete()
        asyncio.create_task(_warn_delete(
            bot, message.chat.id,
            f"🚫 {await _name(message.from_user)} — ʟᴏɴɢ ᴍꜱɢ ᴅᴇʟᴇᴛᴇᴅ\n"
            f"<i>Max {limit} words allowed. Your message had {word_count} words.</i>"
        ))
    except Exception as ef:
        LOGGER.error(f"[anti_long] {ef}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /antiedit on/off
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.regexp(r"^/antiedit(\s+(on|off))?$") & F.chat.type.in_({"group", "supergroup"}))
async def cmd_antiedit(message: Message, bot: Bot):
    if not await is_admin_silent(bot, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Admins only!")

    args = message.text.split()
    db = EditSettings()

    if len(args) < 2:
        cfg = db.get(message.chat.id)
        status = "✅ ON" if cfg.get("anti_edit") else "❌ OFF"
        return await message.reply(
            f"<b>✏️ Anti Edit:</b> {status}\n\n"
            f"<b>Usage:</b> <code>/antiedit on</code> or <code>/antiedit off</code>"
        )

    val = args[1].lower() == "on"
    db.set_anti_edit(message.chat.id, val)
    status = "✅ Enabled" if val else "❌ Disabled"
    await message.reply(f"✏️ Anti Edit: <b>{status}</b>")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /antilong on/off [limit]
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.regexp(r"^/antilong(\s+.*)?$") & F.chat.type.in_({"group", "supergroup"}))
async def cmd_antilong(message: Message, bot: Bot):
    if not await is_admin_silent(bot, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Admins only!")

    args = message.text.split()
    db = EditSettings()

    if len(args) < 2:
        cfg = db.get(message.chat.id)
        status = "✅ ON" if cfg.get("anti_long") else "❌ OFF"
        limit  = cfg.get("long_limit", 200)
        return await message.reply(
            f"<b>📝 Anti Long Message:</b> {status}\n"
            f"<b>Word limit:</b> {limit}\n\n"
            f"<b>Usage:</b>\n"
            f"<code>/antilong on</code>\n"
            f"<code>/antilong off</code>\n"
            f"<code>/antilong on 150</code> — custom limit"
        )

    val = args[1].lower()

    if val == "off":
        db.set_anti_long(message.chat.id, False)
        return await message.reply("📝 Anti Long Message: <b>❌ Disabled</b>")

    if val == "on":
        db.set_anti_long(message.chat.id, True)
        # Optional custom limit
        if len(args) >= 3:
            try:
                limit = int(args[2])
                if limit < 10:
                    return await message.reply("❌ Minimum limit is 10 words.")
                db.set_long_limit(message.chat.id, limit)
                return await message.reply(
                    f"📝 Anti Long Message: <b>✅ Enabled</b>\n"
                    f"Word limit set to <b>{limit}</b>"
                )
            except ValueError:
                return await message.reply("❌ Limit must be a number. e.g. <code>/antilong on 150</code>")
        cfg = db.get(message.chat.id)
        limit = cfg.get("long_limit", 200)
        return await message.reply(
            f"📝 Anti Long Message: <b>✅ Enabled</b>\n"
            f"Current word limit: <b>{limit}</b>"
        )

    await message.reply("❌ Use: <code>/antilong on</code> or <code>/antilong off</code>")
