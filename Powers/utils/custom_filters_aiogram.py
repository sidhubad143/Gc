"""
Powers/utils/custom_filters_aiogram.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Aiogram version of custom_filters.py (Pyrogram wala)

Usage:
    from Powers.utils.custom_filters_aiogram import (
        admin_filter, owner_filter, restrict_filter,
        promote_filter, can_change_filter, can_pin_filter,
        bot_admin_filter,
    )

    @router.message(Command("ban"), admin_filter)
    async def ban_cmd(message: Message, bot: Bot): ...
"""

from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import (
    Message, CallbackQuery,
    ChatMemberAdministrator, ChatMemberOwner,
)
from aiogram.enums import ChatType

from Powers import OWNER_ID
from Powers.supports import get_support_staff


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}


def _is_sudo(user_id: int) -> bool:
    try:
        SUDO_LEVEL = get_support_staff("sudo_level")
        return user_id == OWNER_ID or user_id in SUDO_LEVEL
    except Exception:
        return user_id == OWNER_ID


async def _get_member(bot: Bot, chat_id: int, user_id: int):
    try:
        return await bot.get_chat_member(chat_id, user_id)
    except Exception:
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AdminFilter — user must be admin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AdminFilter(BaseFilter):
    """
    Pass if user is admin/owner.
    Sudo/bot-owner always pass.
    Sends reply if fails.
    """
    async def __call__(self, m: Message | CallbackQuery, bot: Bot) -> bool:
        msg    = m.message if isinstance(m, CallbackQuery) else m
        if msg.chat.type not in GROUP_TYPES:
            return False

        user_id = m.from_user.id if m.from_user else None
        if not user_id:
            return False

        if _is_sudo(user_id):
            return True

        member = await _get_member(bot, msg.chat.id, user_id)
        if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            return True

        if isinstance(m, CallbackQuery):
            await m.answer("🚫 You cannot use an admin command!", show_alert=True)
        else:
            await m.reply("🚫 You cannot use an admin command!")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OwnerFilter — user must be chat owner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OwnerFilter(BaseFilter):
    """
    Pass if user is chat owner or sudo level.
    """
    async def __call__(self, m: Message | CallbackQuery, bot: Bot) -> bool:
        msg     = m.message if isinstance(m, CallbackQuery) else m
        if msg.chat.type not in GROUP_TYPES:
            return False

        user_id = m.from_user.id if m.from_user else None
        if not user_id:
            return False

        if _is_sudo(user_id):
            return True

        member = await _get_member(bot, msg.chat.id, user_id)
        if isinstance(member, ChatMemberOwner):
            return True

        if isinstance(member, ChatMemberAdministrator):
            reply = "⚠️ You're an admin only, stay in your limits!"
        else:
            reply = "🚫 Do you think you can execute owner commands?"

        if isinstance(m, CallbackQuery):
            await m.answer(reply, show_alert=True)
        else:
            await m.reply(reply)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RestrictFilter — can_restrict_members
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RestrictFilter(BaseFilter):
    async def __call__(self, m: Message | CallbackQuery, bot: Bot) -> bool:
        msg     = m.message if isinstance(m, CallbackQuery) else m
        if msg.chat.type not in GROUP_TYPES:
            return False

        user_id = m.from_user.id if m.from_user else None
        if not user_id:
            return False

        if _is_sudo(user_id):
            return True

        member = await _get_member(bot, msg.chat.id, user_id)
        if isinstance(member, ChatMemberOwner):
            return True
        if isinstance(member, ChatMemberAdministrator) and member.can_restrict_members:
            return True

        reply = "🚫 You don't have permission to restrict members!"
        if isinstance(m, CallbackQuery):
            await m.answer(reply, show_alert=True)
        else:
            await m.reply(reply)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PromoteFilter — can_promote_members
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PromoteFilter(BaseFilter):
    async def __call__(self, m: Message | CallbackQuery, bot: Bot) -> bool:
        msg     = m.message if isinstance(m, CallbackQuery) else m
        if msg.chat.type not in GROUP_TYPES:
            return False

        user_id = m.from_user.id if m.from_user else None
        if not user_id:
            return False

        if _is_sudo(user_id):
            return True

        member = await _get_member(bot, msg.chat.id, user_id)
        if isinstance(member, ChatMemberOwner):
            return True
        if isinstance(member, ChatMemberAdministrator) and member.can_promote_members:
            return True

        reply = "🚫 You don't have permission to promote members!"
        if isinstance(m, CallbackQuery):
            await m.answer(reply, show_alert=True)
        else:
            await m.reply(reply)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CanChangeFilter — can_change_info
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CanChangeFilter(BaseFilter):
    async def __call__(self, m: Message | CallbackQuery, bot: Bot) -> bool:
        msg     = m.message if isinstance(m, CallbackQuery) else m
        if msg.chat.type not in GROUP_TYPES:
            reply = "This command is made to be used in groups not in pm!"
            await (m.answer(reply, show_alert=True) if isinstance(m, CallbackQuery) else m.reply(reply))
            return False

        user_id = m.from_user.id if m.from_user else None
        if not user_id:
            return False

        if _is_sudo(user_id):
            return True

        member = await _get_member(bot, msg.chat.id, user_id)
        if isinstance(member, ChatMemberOwner):
            return True
        if isinstance(member, ChatMemberAdministrator) and member.can_change_info:
            return True

        reply = "🚫 You don't have: can_change_info permission!"
        if isinstance(m, CallbackQuery):
            await m.answer(reply, show_alert=True)
        else:
            await m.reply(reply)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CanPinFilter — can_pin_messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CanPinFilter(BaseFilter):
    async def __call__(self, m: Message | CallbackQuery, bot: Bot) -> bool:
        msg     = m.message if isinstance(m, CallbackQuery) else m
        if msg.chat.type not in GROUP_TYPES:
            reply = "This command is made to be used in groups not in pm!"
            await (m.answer(reply, show_alert=True) if isinstance(m, CallbackQuery) else m.reply(reply))
            return False

        user_id = m.from_user.id if m.from_user else None
        if not user_id:
            return False

        if _is_sudo(user_id):
            return True

        member = await _get_member(bot, msg.chat.id, user_id)
        if isinstance(member, ChatMemberOwner):
            return True
        if isinstance(member, ChatMemberAdministrator) and member.can_pin_messages:
            return True

        reply = "🚫 You don't have: can_pin_messages permission!"
        if isinstance(m, CallbackQuery):
            await m.answer(reply, show_alert=True)
        else:
            await m.reply(reply)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BotAdminFilter — bot must be admin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BotAdminFilter(BaseFilter):
    async def __call__(self, m: Message | CallbackQuery, bot: Bot) -> bool:
        msg = m.message if isinstance(m, CallbackQuery) else m
        if msg.chat.type not in GROUP_TYPES:
            return False

        bot_info = await bot.get_me()
        member   = await _get_member(bot, msg.chat.id, bot_info.id)
        if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            return True

        await msg.reply("🚫 I am not an admin here. Please promote me first!")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Instances — ready to use
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

admin_filter      = AdminFilter()
owner_filter      = OwnerFilter()
restrict_filter   = RestrictFilter()
promote_filter    = PromoteFilter()
can_change_filter = CanChangeFilter()
can_pin_filter    = CanPinFilter()
bot_admin_filter  = BotAdminFilter()
