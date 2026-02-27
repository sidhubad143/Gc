import asyncio
import gzip
import json
import base64
import os
import tempfile
from traceback import format_exc
from typing import Optional, Dict

import cv2
import imageio
import numpy as np
from PIL import Image

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus as CMS
from pyrogram.types import Message

from Powers import LOGGER, OWNER_ID
from Powers.bot_class import Gojo
from Powers.database.nsfw_db import NSFWSettings, NSFWApprove, NSFWViolations
from Powers.supports import get_support_staff
from Powers.utils.caching import ADMIN_CACHE, admin_cache_reload
from Powers.utils.custom_filters import command, owner_filter
from Powers.utils.extract_user import extract_user
from Powers.utils.parser import mention_html
from Powers.utils.predict import detect_nsfw

# ── Temp dir ──────────────────────────────────────────────────────────────────
MEDIA_DIR = "./nsfw_temp/"
os.makedirs(MEDIA_DIR, exist_ok=True)

# ── NSFW Thresholds ───────────────────────────────────────────────────────────
NSFW_THRESHOLDS = {
    "porn":   0.60,
    "hentai": 0.65,
    "sexy":   0.75,
}

# ── Dangerous file extensions ─────────────────────────────────────────────────
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".sh", ".apk", ".ipa",
    ".cmd", ".vbs", ".msi", ".dll", ".scr"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEDIA CONVERTERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MediaConverter:

    @staticmethod
    def webp_to_png(file_path: str) -> Optional[str]:
        try:
            out = f"{tempfile.mktemp()}.png"
            with Image.open(file_path) as img:
                img.convert("RGB").save(out, "PNG")
            return out
        except Exception as e:
            LOGGER.error(f"[nsfw] webp→png failed: {e}")
            return None

    @staticmethod
    def webm_first_frame(input_path: str) -> Optional[str]:
        try:
            out = f"{tempfile.mktemp()}.jpg"
            cap = cv2.VideoCapture(input_path)
            ok, frame = cap.read()
            cap.release()
            if ok:
                cv2.imwrite(out, frame)
                return out
            with imageio.get_reader(input_path, format="webm") as r:
                frame = r.get_next_data()
                imageio.imwrite(out, np.array(frame, dtype=np.uint8), format="JPEG")
            return out
        except Exception as e:
            LOGGER.error(f"[nsfw] webm frame failed: {e}")
            return None

    @staticmethod
    def tgs_to_png(file_path: str) -> Optional[str]:
        """TGS = gzip compressed lottie JSON."""
        try:
            out = f"{tempfile.mktemp()}.png"
            with gzip.open(file_path, "rb") as f:
                data = json.loads(f.read().decode("utf-8"))
            for asset in data.get("assets", []):
                if "p" in asset and isinstance(asset["p"], str) and "," in asset["p"]:
                    try:
                        img_data = base64.b64decode(asset["p"].split(",")[1])
                        with open(out, "wb") as ff:
                            ff.write(img_data)
                        return out
                    except Exception:
                        continue
            w, h = data.get("w", 512), data.get("h", 512)
            Image.new("RGB", (w, h), (255, 255, 255)).save(out)
            return out
        except Exception as e:
            LOGGER.error(f"[nsfw] tgs→png failed: {e}")
            return None


def _video_first_frame(path: str) -> Optional[str]:
    try:
        out = f"{tempfile.mktemp()}.jpg"
        cap = cv2.VideoCapture(path)
        ok, frame = cap.read()
        cap.release()
        if ok:
            cv2.imwrite(out, frame)
            return out
        return None
    except Exception as e:
        LOGGER.error(f"[nsfw] video frame failed: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _get_admins(c: Gojo, chat_id: int) -> set:
    try:
        return {i[0] for i in ADMIN_CACHE[chat_id]}
    except KeyError:
        return {i[0] for i in await admin_cache_reload(None, "nsfw")}


async def _is_group_owner(c: Gojo, chat_id: int, user_id: int) -> bool:
    try:
        member = await c.get_chat_member(chat_id, user_id)
        return member.status == CMS.OWNER
    except Exception:
        return False


def _is_bot_owner(user_id: int) -> bool:
    SUDO = get_support_staff("sudo_level")
    return user_id == OWNER_ID or user_id in SUDO


async def _should_delete(
    c: Gojo,
    chat_id: int,
    user_id: int,
    mode: str,
    is_sticker: bool,
    nsfw_db: NSFWApprove,
) -> bool:
    """
    Returns True if message should be deleted based on mode.

    soft   — Admins' sticker safe, baki sab delete
    normal — Group owner + admins + approved safe, baki delete
    strict — Bot owner + approved sirf safe, baaki sab delete
    """
    if mode == "off":
        return False

    # Bot owner always safe
    if _is_bot_owner(user_id):
        return False

    # Approved user always safe
    if nsfw_db.is_approved(chat_id, user_id):
        return False

    admins = await _get_admins(c, chat_id)

    if mode == "soft":
        # Admins ke stickers safe — normal media nahi
        if is_sticker and user_id in admins:
            return False
        return True

    elif mode == "normal":
        # Group owner + admins safe
        if user_id in admins:
            return False
        if await _is_group_owner(c, chat_id, user_id):
            return False
        return True

    elif mode == "strict":
        # Sirf bot owner + approved (already handled above)
        return True

    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN MEDIA HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(
    filters.group
    & (filters.photo | filters.video | filters.sticker |
       filters.document | filters.video_note | filters.animation),
    group=7
)
async def nsfw_media_handler(c: Gojo, m: Message):
    if not m.from_user:
        return

    nsfw_cfg = NSFWSettings()
    nsfw_app = NSFWApprove()
    chat_id  = m.chat.id
    user_id  = m.from_user.id
    mode     = nsfw_cfg.get_mode(chat_id)

    if mode == "off":
        return

    # ── Block dangerous files ─────────────────────────────────────────────────
    if m.document and m.document.file_name:
        ext = os.path.splitext(m.document.file_name)[1].lower()
        if ext in BLOCKED_EXTENSIONS:
            should_del = await _should_delete(c, chat_id, user_id, mode, False, nsfw_app)
            if should_del:
                try:
                    await m.delete()
                    mention = await mention_html(m.from_user.first_name, user_id)
                    warn = await c.send_message(
                        chat_id,
                        f"🚫 {mention} — <b>Dangerous file blocked!</b>",
                    )
                    await asyncio.sleep(8)
                    await warn.delete()
                except Exception:
                    pass
            return

    # ── Determine if sticker ──────────────────────────────────────────────────
    is_sticker = bool(m.sticker)

    # ── Check if should be scanned ────────────────────────────────────────────
    should_del = await _should_delete(c, chat_id, user_id, mode, is_sticker, nsfw_app)
    if not should_del:
        return

    original_path  = None
    processed_path = None

    try:
        # ── Get file ──────────────────────────────────────────────────────────
        if m.photo:
            file = m.photo; ext = ".jpg"
        elif m.video or m.video_note:
            file = m.video or m.video_note; ext = ".mp4"
        elif m.sticker:
            file = m.sticker
            ext = ".tgs" if file.is_animated else (".webm" if file.is_video else ".webp")
        elif m.animation:
            file = m.animation; ext = ".mp4"
        elif m.document:
            file = m.document
            ext  = os.path.splitext(file.file_name or "")[1] or ".bin"
        else:
            return

        original_path = os.path.join(MEDIA_DIR, f"{user_id}_{file.file_id}{ext}")
        await c.download_media(file.file_id, file_name=original_path)

        if not os.path.exists(original_path):
            return

        # ── Convert to image ──────────────────────────────────────────────────
        if m.sticker:
            if file.is_animated:
                processed_path = MediaConverter.tgs_to_png(original_path)
            elif file.is_video:
                processed_path = MediaConverter.webm_first_frame(original_path)
            else:
                processed_path = MediaConverter.webp_to_png(original_path)
        elif m.video or m.video_note or m.animation:
            processed_path = _video_first_frame(original_path)
        else:
            processed_path = original_path

        if not processed_path or not os.path.exists(processed_path):
            return

        # ── NSFW Detection ────────────────────────────────────────────────────
        result = detect_nsfw(processed_path)
        if not result:
            return

        triggered = None
        for cat, threshold in NSFW_THRESHOLDS.items():
            if result.get(cat, 0) >= threshold:
                triggered = cat
                break

        if not triggered:
            return

        # ── Delete + warn ─────────────────────────────────────────────────────
        try:
            await m.delete()
        except Exception:
            pass

        NSFWViolations().add_violation(chat_id, user_id, triggered)
        mention = await mention_html(m.from_user.first_name, user_id)
        content = "sticker 🎭" if is_sticker else "media 🖼"

        warn = await c.send_message(
            chat_id,
            f"╭───────────────────\n"
            f"│ 🔞 <b>NSFW {content.upper()} DETECTED</b>\n"
            f"╰───────────────────\n"
            f"👤 <b>User:</b> {mention}\n"
            f"📊 <b>Category:</b> <code>{triggered}</code> "
            f"({result.get(triggered, 0):.0%})\n"
            f"⚠️ <b>Action:</b> Message deleted.",
        )
        await asyncio.sleep(15)
        try:
            await warn.delete()
        except Exception:
            pass

    except Exception as ef:
        LOGGER.error(f"[nsfw_handler] {ef}")
        LOGGER.error(format_exc())
    finally:
        for path in {original_path, processed_path}:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwmode — Group owner / bot owner set kar sakda
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwmode") & filters.group)
async def set_nsfw_mode(c: Gojo, m: Message):
    user_id = m.from_user.id

    # Only group owner or bot owner
    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only <b>group owner</b> or bot owner can set NSFW mode.")

    args = m.text.split()
    if len(args) < 2:
        mode = NSFWSettings().get_mode(m.chat.id)
        return await m.reply_text(
            f"<b>🔞 NSFW Mode</b>\n\n"
            f"Current: <code>{mode}</code>\n\n"
            f"<b>Modes:</b>\n"
            f"• <code>off</code> — Disabled\n"
            f"• <code>soft</code> — Admins' stickers safe, baki delete\n"
            f"• <code>normal</code> — Owner + admins + approved safe\n"
            f"• <code>strict</code> — Only bot owner + approved safe\n\n"
            f"<b>Usage:</b> <code>/nsfwmode [off|soft|normal|strict]</code>"
        )

    new_mode = args[1].lower()
    if new_mode not in ("off", "soft", "normal", "strict"):
        return await m.reply_text("❌ Invalid mode! Use: <code>off | soft | normal | strict</code>")

    NSFWSettings().set_mode(m.chat.id, new_mode)

    mode_desc = {
        "off":    "NSFW detection <b>disabled</b>.",
        "soft":   "Admins' stickers safe, other users' NSFW deleted.",
        "normal": "Group owner + admins + approved users safe.",
        "strict": "Only bot owner + approved users safe.",
    }
    await m.reply_text(
        f"✅ NSFW mode set to <code>{new_mode}</code>\n"
        f"<i>{mode_desc[new_mode]}</i>"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwapprove — Group owner / bot owner approve kar sakda
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwapprove") & filters.group)
async def nsfw_approve(c: Gojo, m: Message):
    user_id = m.from_user.id

    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only <b>group owner</b> or bot owner can approve users.")

    try:
        target_id, target_name, _ = await extract_user(c, m)
    except Exception:
        return await m.reply_text("❌ User not found. Reply to user or give username.")

    if not target_id:
        return await m.reply_text("❌ User not found.")

    db = NSFWApprove()
    if db.approve(m.chat.id, target_id, user_id):
        mention = await mention_html(target_name, target_id)
        await m.reply_text(f"✅ {mention} approved — NSFW filter will skip this user.")
    else:
        await m.reply_text("⚠️ User is already approved.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwunapprove
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwunapprove") & filters.group)
async def nsfw_unapprove(c: Gojo, m: Message):
    user_id = m.from_user.id

    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only <b>group owner</b> or bot owner can unapprove users.")

    try:
        target_id, target_name, _ = await extract_user(c, m)
    except Exception:
        return await m.reply_text("❌ User not found.")

    db = NSFWApprove()
    if db.unapprove(m.chat.id, target_id):
        mention = await mention_html(target_name, target_id)
        await m.reply_text(f"✅ {mention} removed from NSFW approved list.")
    else:
        await m.reply_text("⚠️ User was not in approved list.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwapproved — list all approved users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwapproved") & filters.group)
async def nsfw_approved_list(c: Gojo, m: Message):
    approved = NSFWApprove().list_approved(m.chat.id)
    if not approved:
        return await m.reply_text("No users approved for NSFW bypass in this chat.")

    lines = []
    for u in approved:
        try:
            user = await c.get_users(u["user_id"])
            mention = await mention_html(user.first_name, user.id)
        except Exception:
            mention = f"<code>{u['user_id']}</code>"
        lines.append(f"• {mention}")

    await m.reply_text(
        f"✅ <b>NSFW Approved Users</b> ({len(lines)})\n\n"
        + "\n".join(lines)
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwstats — violation history
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwstats") & filters.group)
async def nsfw_stats(c: Gojo, m: Message):
    if m.reply_to_message and m.reply_to_message.from_user:
        target_id   = m.reply_to_message.from_user.id
        target_name = m.reply_to_message.from_user.first_name
    elif len(m.command) > 1:
        try:
            target_id, target_name, _ = await extract_user(c, m)
        except Exception:
            return await m.reply_text("❌ User not found.")
    else:
        target_id   = m.from_user.id
        target_name = m.from_user.first_name

    violations = NSFWViolations().get_violations(m.chat.id, target_id)
    mention    = await mention_html(target_name, target_id)

    if not violations:
        return await m.reply_text(f"✅ {mention} has no NSFW violations in this chat.")

    lines = []
    for v in violations:
        last = str(v.get("last_seen", "")).split(".")[0]
        lines.append(
            f"🔸 <code>{v['category']}</code> — "
            f"{v['count']}x (last: {last})"
        )

    await m.reply_text(
        f"📊 <b>NSFW Violations:</b> {mention}\n\n"
        + "\n".join(lines)
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PLUGIN INFO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__PLUGIN__ = "nsfw"
__alt_name__ = ["nsfwmode", "nsfwapprove"]

__HELP__ = """
<b>🔞 NSFW Filter</b>

Automatically detects and deletes NSFW content in the group.

<b>Modes (set by group owner / bot owner only):</b>
• <code>off</code> — Disabled
• <code>soft</code> — Admins' stickers are safe, everyone else's NSFW deleted
• <code>normal</code> — Group owner + admins + approved safe
• <code>strict</code> — Only bot owner + approved users safe, everyone else deleted

<b>Commands:</b>
• /nsfwmode <code>[off|soft|normal|strict]</code> — Set NSFW mode <i>(owner only)</i>
• /nsfwapprove — Approve user (reply/username) <i>(owner only)</i>
• /nsfwunapprove — Remove approval <i>(owner only)</i>
• /nsfwapproved — List approved users
• /nsfwstats — View your violation history
• /nsfwstats <code>[reply/@user]</code> — View someone's violation history
"""
