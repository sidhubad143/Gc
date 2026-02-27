import re
import time
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, ChatMemberUpdated, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPermissions
)
from aiogram.filters import Command, ChatMemberUpdatedFilter
from aiogram.enums import ChatMemberStatus, ParseMode
from pymongo import MongoClient

router = Router()

@router.edited_message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def anti_edit(message: Message, bot: Bot):
    if not _feat(message.chat.id, "anti_edit"):
        return
    if not message.from_user or is_exempt(message.from_user.id):
        return
    if await is_admin_aiogram(bot, message.chat.id, message.from_user.id):
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
    except Exception:
        pass
        
