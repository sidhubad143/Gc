"""
edit.py — Anti Edit Plugin (Aiogram)
"""

import asyncio

from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode

from Powers import LOGGER
from Powers.utils.parser import mention_html
from Powers.utils.admin_check_aiogram import is_admin_silent

router = Router()


def _name(user) -> str:
    return mention_html(user.first_name or "User", user.id)


@router.edited_message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def anti_edit(message: Message, bot: Bot):
    if not message.from_user:
        return
    if await is_admin_silent(bot, message.chat.id, message.from_user.id):
        return
    try:
        await message.delete()
        m = await bot.send_message(
            message.chat.id,
            f"✏️ {_name(message.from_user)} ᴇᴅɪᴛᴇᴅ ᴍꜱɢ ᴅᴇʟᴇᴛᴇᴅ 🚫",
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(10)
        await m.delete()
    except Exception as ef:
        LOGGER.error(f"[anti_edit] {ef}")
