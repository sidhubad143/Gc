import asyncio

from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode

from Powers import LOGGER, OWNER_ID
from Powers.supports import get_support_staff
from Powers.utils.parser import mention_html
from Powers.utils.admin_check_aiogram import is_admin_silent
from Powers.database.edit_db import EditSettings

router = Router()

VALID_MODES = ("off", "admin", "normal", "strict")

MODE_DESC = {
    "off":    "Disabled.",
    "admin":  "Admins safe, others deleted.",
    "normal": "Owner + admins safe.",
    "strict": "Only bot owner + approved safe.",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _name(user) -> str:
    return await mention_html(user.first_name or "User", user.id)


def _is_bot_owner(user_id: int) -> bool:
    try:
        SUDO = get_support_staff("sudo_level")
        return user_id == OWNER_ID or user_id in SUDO
    except Exception:
        return user_id == OWNER_ID


async def _is_owner(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        from aiogram.types import ChatMemberOwner
        member = await bot.get_chat_member(chat_id, user_id)
        return isinstance(member, ChatMemberOwner)
    except Exception:
        return False


async def _should_delete(bot: Bot, chat_id: int, user_id: int, mode: str) -> bool:
    """
    admin  — admins safe, baki delete
    normal — owner + admins safe
    strict — sirf bot owner + approved safe
    """
    if mode == "off":
        return False
    if _is_bot_owner(user_id):
        return False

    is_admin = await is_admin_silent(bot, chat_id, user_id)

    if mode == "admin":
        return not is_admin

    elif mode == "normal":
        if is_admin:
            return False
        if await _is_owner(bot, chat_id, user_id):
            return False
        return True

    elif mode == "strict":
        return True

    return False


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

    cfg  = EditSettings().get(message.chat.id)
    mode = cfg.get("anti_edit", "off")

    if not await _should_delete(bot, message.chat.id, message.from_user.id, mode):
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
    if not message.text or message.text.startswith("/"):
        return

    cfg        = EditSettings().get(message.chat.id)
    mode       = cfg.get("anti_long", "off")
    limit      = cfg.get("long_limit", 200)
    word_count = len(message.text.split())

    if word_count <= limit:
        return

    if not await _should_delete(bot, message.chat.id, message.from_user.id, mode):
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
# /antiedit [off|admin|normal|strict]
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.regexp(r"^/antiedit(\s+.*)?$") & F.chat.type.in_({"group", "supergroup"}))
async def cmd_antiedit(message: Message, bot: Bot):
    if not await is_admin_silent(bot, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Admins only!")

    args = message.text.split()
    db   = EditSettings()

    if len(args) < 2:
        cfg  = db.get(message.chat.id)
        mode = cfg.get("anti_edit", "off")
        return await message.reply(
            f"<b>✏️ Anti Edit</b>\n\n"
            f"Current: <code>{mode}</code>\n\n"
            f"<b>Modes (admin only):</b>\n"
            f"• <code>off</code> — Disabled\n"
            f"• <code>admin</code> — Admins safe, others deleted\n"
            f"• <code>normal</code> — Owner + admins safe\n"
            f"• <code>strict</code> — Only bot owner + approved safe\n\n"
            f"<b>Usage:</b> <code>/antiedit [off|admin|normal|strict]</code>",
            parse_mode=ParseMode.HTML
        )

    new_mode = args[1].lower()
    if new_mode not in VALID_MODES:
        return await message.reply(
            "❌ Use: <code>off | admin | normal | strict</code>",
            parse_mode=ParseMode.HTML
        )

    db.set_anti_edit(message.chat.id, new_mode)
    await message.reply(
        f"✏️ Anti Edit → <code>{new_mode}</code>\n"
        f"<i>{MODE_DESC[new_mode]}</i>",
        parse_mode=ParseMode.HTML
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /antilong [off|admin|normal|strict] [limit]
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.regexp(r"^/antilong(\s+.*)?$") & F.chat.type.in_({"group", "supergroup"}))
async def cmd_antilong(message: Message, bot: Bot):
    if not await is_admin_silent(bot, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Admins only!")

    args = message.text.split()
    db   = EditSettings()

    if len(args) < 2:
        cfg   = db.get(message.chat.id)
        mode  = cfg.get("anti_long", "off")
        limit = cfg.get("long_limit", 200)
        return await message.reply(
            f"<b>📝 Anti Long Message</b>\n\n"
            f"Current: <code>{mode}</code>\n"
            f"Word limit: <code>{limit}</code>\n\n"
            f"<b>Modes (admin only):</b>\n"
            f"• <code>off</code> — Disabled\n"
            f"• <code>admin</code> — Admins safe, others deleted\n"
            f"• <code>normal</code> — Owner + admins safe\n"
            f"• <code>strict</code> — Only bot owner + approved safe\n\n"
            f"<b>Usage:</b>\n"
            f"• <code>/antilong normal</code>\n"
            f"• <code>/antilong normal 150</code> — custom word limit",
            parse_mode=ParseMode.HTML
        )

    new_mode = args[1].lower()
    if new_mode not in VALID_MODES:
        return await message.reply(
            "❌ Use: <code>off | admin | normal | strict</code>",
            parse_mode=ParseMode.HTML
        )

    db.set_anti_long(message.chat.id, new_mode)

    # Optional custom limit
    if len(args) >= 3:
        try:
            limit = int(args[2])
            if limit < 10:
                return await message.reply("❌ Minimum limit is 10 words.")
            db.set_long_limit(message.chat.id, limit)
            return await message.reply(
                f"📝 Anti Long → <code>{new_mode}</code>\n"
                f"<i>{MODE_DESC[new_mode]}</i>\n"
                f"Word limit: <code>{limit}</code>",
                parse_mode=ParseMode.HTML
            )
        except ValueError:
            return await message.reply(
                "❌ Limit must be a number. e.g. <code>/antilong normal 150</code>",
                parse_mode=ParseMode.HTML
            )

    cfg   = db.get(message.chat.id)
    limit = cfg.get("long_limit", 200)
    await message.reply(
        f"📝 Anti Long → <code>{new_mode}</code>\n"
        f"<i>{MODE_DESC[new_mode]}</i>\n"
        f"Word limit: <code>{limit}</code>",
        parse_mode=ParseMode.HTML
            )
