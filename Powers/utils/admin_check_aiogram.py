from traceback import format_exc

from aiogram import Bot
from aiogram.types import (
    Message, CallbackQuery,
    ChatMemberAdministrator, ChatMemberOwner,
    ChatMemberMember, ChatMemberRestricted,
    ChatMemberLeft, ChatMemberBanned,
)

from Powers import LOGGER, OWNER_ID
from Powers.supports import get_support_staff


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTERNAL HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_user_chat(m: Message | CallbackQuery) -> tuple[int, int]:
    """Extract user_id and chat_id from Message or CallbackQuery."""
    if isinstance(m, Message):
        return m.from_user.id, m.chat.id
    if isinstance(m, CallbackQuery):
        return m.from_user.id, m.message.chat.id


async def _reply(m: Message | CallbackQuery, text: str):
    """Send reply to Message or CallbackQuery."""
    try:
        if isinstance(m, CallbackQuery):
            await m.answer(text, show_alert=True)
        else:
            await m.reply(text)
    except Exception as ef:
        LOGGER.error(ef)
        LOGGER.error(format_exc())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# is_admin_silent — no message, just True/False
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_admin_silent(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Silent admin check — no message sent.
    Use this inside handlers to check quietly.
    """
    try:
        SUDO_LEVEL = get_support_staff("sudo_level")
        if user_id in SUDO_LEVEL or user_id == OWNER_ID:
            return True
    except Exception:
        pass

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception as ef:
        LOGGER.error(f"[is_admin_silent] {ef}")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# admin_check — checks + replies if not admin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def admin_check(m: Message | CallbackQuery, bot: Bot) -> bool:
    """
    Checks if user is admin.
    If not — sends message and returns False.
    If yes — returns True.
    """
    user_id, chat_id = _get_user_chat(m)

    # ── Sudo/Owner bypass ─────────────────────────────────────────────────────
    try:
        SUDO_LEVEL = get_support_staff("sudo_level")
        if user_id in SUDO_LEVEL or user_id == OWNER_ID:
            return True
    except Exception as ef:
        LOGGER.error(format_exc())

    # ── Check admin status ────────────────────────────────────────────────────
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception as ef:
        LOGGER.error(f"[admin_check] get_chat_member failed: {ef}")
        return False

    if not isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
        await _reply(m, "🚫 Nigga, you're not admin, don't try this explosive shit.")
        return False

    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# check_rights — check specific admin permission
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def check_rights(m: Message | CallbackQuery, bot: Bot, rights: str) -> bool:
    """
    Check if admin has a specific right.
    rights = "can_ban_members" | "can_delete_messages" | "can_pin_messages" etc.

    Example:
        if not await check_rights(message, bot, "can_ban_members"):
            return
    """
    user_id, chat_id = _get_user_chat(m)

    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception as ef:
        LOGGER.error(f"[check_rights] {ef}")
        return False

    # Owner has all rights
    if isinstance(member, ChatMemberOwner):
        return True

    # Not admin at all
    if not isinstance(member, ChatMemberAdministrator):
        return False

    # Check specific right
    return bool(getattr(member, rights, False))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# owner_check — checks + replies if not owner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def owner_check(m: Message | CallbackQuery, bot: Bot) -> bool:
    """
    Checks if user is owner (or sudo level).
    If not — sends appropriate message and returns False.
    If yes — returns True.
    """
    user_id, chat_id = _get_user_chat(m)

    # ── Sudo/Owner bypass ─────────────────────────────────────────────────────
    try:
        SUDO_LEVEL = get_support_staff("sudo_level")
        if user_id in SUDO_LEVEL or user_id == OWNER_ID:
            return True
    except Exception:
        pass

    # ── Check member status ───────────────────────────────────────────────────
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception as ef:
        LOGGER.error(f"[owner_check] {ef}")
        return False

    if isinstance(member, ChatMemberOwner):
        return True

    # Not owner — send appropriate msg
    if isinstance(member, ChatMemberAdministrator):
        reply = "⚠️ Stay in your limits, or lose adminship too."
    else:
        reply = "🚫 You ain't even admin, what are you trying to do?"

    await _reply(m, reply)
    return False
