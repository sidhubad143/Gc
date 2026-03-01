import asyncio
import re
from traceback import format_exc
from typing import Optional

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus as CMS
from pyrogram.types import Message

from Powers import LOGGER, OWNER_ID
from Powers.bot_class import Gojo
from Powers.database.biolink_db import BioLinkSettings, BioLinkApprove
from Powers.supports import get_support_staff
from Powers.utils.caching import ADMIN_CACHE, admin_cache_reload
from Powers.utils.custom_filters import command
from Powers.utils.extract_user import extract_user
from Powers.utils.parser import mention_html

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LINK REGEX — bio vich URL detect karne lyi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LINK_RE = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|@\w{5,})",
    re.IGNORECASE
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODE DESC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MODE_DESC = {
    "off":    "Disabled.",
    "admin":  "Admins safe, others checked.",
    "normal": "Owner + admins safe.",
    "strict": "Only bot owner + approved safe.",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _is_bot_owner(user_id: int) -> bool:
    try:
        SUDO = get_support_staff("sudo_level")
        return user_id == OWNER_ID or user_id in SUDO
    except Exception:
        return user_id == OWNER_ID


async def _get_admins(c: Gojo, chat_id: int) -> set:
    try:
        return {i[0] for i in ADMIN_CACHE[chat_id]}
    except KeyError:
        return {i[0] for i in await admin_cache_reload(None, "biolink")}


async def _is_group_owner(c: Gojo, chat_id: int, user_id: int) -> bool:
    try:
        member = await c.get_chat_member(chat_id, user_id)
        return member.status == CMS.OWNER
    except Exception:
        return False


async def _should_check(
    c: Gojo,
    chat_id: int,
    user_id: int,
    mode: str,
    approve_db: BioLinkApprove,
) -> bool:
    """
    Returns True if user's bio should be checked.
    admin  — admins safe
    normal — owner + admins safe
    strict — sirf bot owner + approved safe
    """
    if mode == "off":
        return False
    if _is_bot_owner(user_id):
        return False
    if approve_db.is_approved(chat_id, user_id):
        return False

    admins = await _get_admins(c, chat_id)

    if mode == "admin":
        return user_id not in admins

    elif mode == "normal":
        if user_id in admins:
            return False
        if await _is_group_owner(c, chat_id, user_id):
            return False
        return True

    elif mode == "strict":
        return True

    return False


async def _get_bio(c: Gojo, user_id: int) -> Optional[str]:
    """Fetch user bio."""
    try:
        user = await c.get_users(user_id)
        return user.bio or ""
    except Exception:
        return None


def _has_link(text: str) -> bool:
    """Check if text contains a URL/link."""
    return bool(LINK_RE.search(text))


async def _warn(c: Gojo, chat_id: int, text: str, delay: int = 15):
    try:
        msg = await c.send_message(chat_id, text)
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN MESSAGE HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(
    filters.group & (filters.text | filters.caption | filters.photo |
                     filters.video | filters.document | filters.sticker),
    group=8
)
async def biolink_check(c: Gojo, m: Message):
    if not m.from_user:
        return

    chat_id = m.chat.id
    user_id = m.from_user.id
    mode    = BioLinkSettings().get_mode(chat_id)

    if mode == "off":
        return

    approve_db = BioLinkApprove()

    if not await _should_check(c, chat_id, user_id, mode, approve_db):
        return

    # ── Fetch bio ─────────────────────────────────────────────────────────────
    bio = await _get_bio(c, user_id)
    if bio is None or not _has_link(bio):
        return

    # ── Delete message + send alert ───────────────────────────────────────────
    try:
        await m.delete()
    except Exception:
        pass

    mention = await mention_html(m.from_user.first_name, user_id)
    asyncio.create_task(_warn(
        c, chat_id,
        f"╭───────────────────\n"
        f"│ 🔗 <b>BIO LINK DETECTED</b>\n"
        f"╰───────────────────\n"
        f"👤 <b>User:</b> {mention}\n"
        f"📋 <b>Bio:</b> <i>Contains a link/username</i>\n"
        f"⚠️ <b>Action:</b> Message deleted.\n\n"
        f"<i>Remove the link from your bio to chat here.</i>"
    ))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /biolinkmode [off|admin|normal|strict]
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("biolinkmode") & filters.group)
async def set_biolink_mode(c: Gojo, m: Message):
    user_id = m.from_user.id
    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only <b>group owner</b> or bot owner can set this.")

    args = m.text.split()
    if len(args) < 2:
        mode = BioLinkSettings().get_mode(m.chat.id)
        return await m.reply_text(
            f"<b>🔗 Bio Link Mode</b>\n\n"
            f"Current: <code>{mode}</code>\n\n"
            f"<b>Modes (group owner / bot owner only):</b>\n"
            f"• <code>off</code> — Disabled\n"
            f"• <code>admin</code> — Admins safe, others checked\n"
            f"• <code>normal</code> — Owner + admins safe\n"
            f"• <code>strict</code> — Only bot owner + approved safe\n\n"
            f"<b>Usage:</b> <code>/biolinkmode [off|admin|normal|strict]</code>"
        )

    new_mode = args[1].lower()
    if new_mode not in ("off", "admin", "normal", "strict"):
        return await m.reply_text("❌ Use: <code>off | admin | normal | strict</code>")

    BioLinkSettings().set_mode(m.chat.id, new_mode)
    await m.reply_text(
        f"🔗 Bio Link Mode → <code>{new_mode}</code>\n"
        f"<i>{MODE_DESC[new_mode]}</i>"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /biolinkexempt — approve user (bypass check)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("biolinkexempt") & filters.group)
async def biolink_exempt(c: Gojo, m: Message):
    user_id = m.from_user.id
    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only group owner or bot owner can exempt users.")

    try:
        target_id, target_name, _ = await extract_user(c, m)
    except Exception:
        return await m.reply_text("❌ User not found.")
    if not target_id:
        return await m.reply_text("❌ User not found.")

    db = BioLinkApprove()
    if db.approve(m.chat.id, target_id):
        mention = await mention_html(target_name, target_id)
        await m.reply_text(f"✅ {mention} exempted — bio link check skipped.")
    else:
        await m.reply_text("⚠️ User already exempted.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /biolinkremove — remove exemption
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("biolinkremove") & filters.group)
async def biolink_remove(c: Gojo, m: Message):
    user_id = m.from_user.id
    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only group owner or bot owner can remove exemptions.")

    try:
        target_id, target_name, _ = await extract_user(c, m)
    except Exception:
        return await m.reply_text("❌ User not found.")

    db = BioLinkApprove()
    if db.unapprove(m.chat.id, target_id):
        mention = await mention_html(target_name, target_id)
        await m.reply_text(f"✅ {mention} removed from exemption list.")
    else:
        await m.reply_text("⚠️ User was not exempted.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PLUGIN INFO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__PLUGIN__ = "biolink"
__alt_name__ = ["biolinkmode", "biolinkexempt"]

__HELP__ = """
<b>🔗 Bio Link Filter</b>

Jado koi user message kare aur uski bio vich link/username howe,
message auto-delete ho janda hai.

<b>Modes (group owner / bot owner only):</b>
• <code>off</code> — Disabled
• <code>admin</code> — Admins safe, others checked
• <code>normal</code> — Owner + admins safe
• <code>strict</code> — Only bot owner + approved safe

<b>Commands:</b>
• /biolinkmode <code>[off|admin|normal|strict]</code> — Set mode
• /biolinkexempt — Exempt user (reply/@user)
• /biolinkremove — Remove exemption
"""
