import asyncio
import gzip
import json
import base64
import os
import tempfile
from traceback import format_exc
from typing import Optional

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
from Powers.utils.custom_filters import command
from Powers.utils.extract_user import extract_user
from Powers.utils.parser import mention_html
from Powers.utils.predict import detect_nsfw, get_media_path, clean_media_folder

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NSFW_THRESHOLDS = {
    "porn":   0.60,
    "hentai": 0.65,
    "sexy":   0.75,
}

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
            LOGGER.error(f"[nsfw] webp→png: {e}")
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
            LOGGER.error(f"[nsfw] webm frame: {e}")
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
            LOGGER.error(f"[nsfw] tgs→png: {e}")
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
        LOGGER.error(f"[nsfw] video frame: {e}")
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
    soft   — Admins' stickers safe, baki sab scan
    normal — Owner + admins + approved safe
    strict — Sirf bot owner + approved safe
    """
    if mode == "off":
        return False
    if _is_bot_owner(user_id):
        return False
    if nsfw_db.is_approved(chat_id, user_id):
        return False

    admins = await _get_admins(c, chat_id)

    if mode == "soft":
        if is_sticker and user_id in admins:
            return False
        return True
    elif mode == "normal":
        if user_id in admins:
            return False
        if await _is_group_owner(c, chat_id, user_id):
            return False
        return True
    elif mode == "strict":
        return True

    return False


async def _warn(c: Gojo, chat_id: int, text: str, delay: int = 15):
    """Send warning and auto-delete after delay seconds."""
    try:
        msg = await c.send_message(chat_id, text)
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


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

    # ── Block dangerous file extensions ───────────────────────────────────────
    if m.document and m.document.file_name:
        ext = os.path.splitext(m.document.file_name)[1].lower()
        if ext in BLOCKED_EXTENSIONS:
            if await _should_delete(c, chat_id, user_id, mode, False, nsfw_app):
                try:
                    await m.delete()
                    mention = await mention_html(m.from_user.first_name, user_id)
                    asyncio.create_task(_warn(
                        c, chat_id,
                        f"🚫 {mention} — <b>Dangerous file blocked!</b> (<code>{ext}</code>)",
                        delay=8
                    ))
                except Exception:
                    pass
            return

    is_sticker = bool(m.sticker)

    if not await _should_delete(c, chat_id, user_id, mode, is_sticker, nsfw_app):
        return

    original_path  = None
    processed_path = None

    try:
        # ── Determine file + extension ────────────────────────────────────────
        if m.photo:
            file = m.photo
            ext  = ".jpg"
        elif m.video or m.video_note:
            file = m.video or m.video_note
            ext  = ".mp4"
        elif m.sticker:
            file = m.sticker
            ext  = ".tgs" if file.is_animated else (".webm" if file.is_video else ".webp")
        elif m.animation:
            file = m.animation
            ext  = ".mp4"
        elif m.document:
            file = m.document
            ext  = os.path.splitext(file.file_name or "")[1] or ".bin"
        else:
            return

        # ── Download using get_media_path (scrapped/ folder) ─────────────────
        original_path = get_media_path(user_id, f"{file.file_id}{ext}")
        await c.download_media(file.file_id, file_name=original_path)

        if not os.path.exists(original_path):
            return

        # ── Convert to scannable image ────────────────────────────────────────
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

        # ── Full Detection: NSFW + Weapon + Drug ──────────────────────────────
        result = detect_nsfw(processed_path)  # auto-deletes processed_path
        processed_path = None  # already deleted by detect_nsfw

        if not result:
            return

        mention  = await mention_html(m.from_user.first_name, user_id)
        content  = "STICKER 🎭" if is_sticker else "MEDIA 🖼"
        deleted  = False

        # ── 1. NSFW ───────────────────────────────────────────────────────────
        triggered = None
        nsfw_scores = result.get("nsfw", {})
        for cat, threshold in NSFW_THRESHOLDS.items():
            if nsfw_scores.get(cat, 0) >= threshold:
                triggered = cat
                break

        if triggered:
            try:
                await m.delete()
                deleted = True
            except Exception:
                pass
            NSFWViolations().add_violation(chat_id, user_id, triggered)
            score = nsfw_scores.get(triggered, 0)
            asyncio.create_task(_warn(
                c, chat_id,
                f"╭───────────────────\n"
                f"│ 🔞 <b>NSFW {content} DETECTED</b>\n"
                f"╰───────────────────\n"
                f"👤 <b>User:</b> {mention}\n"
                f"📊 <b>Category:</b> <code>{triggered}</code> ({score:.0%})\n"
                f"⚠️ <b>Action:</b> Message deleted."
            ))

        # ── 2. Weapon ─────────────────────────────────────────────────────────
        if result.get("has_weapon"):
            if not deleted:
                try:
                    await m.delete()
                    deleted = True
                except Exception:
                    pass
            NSFWViolations().add_violation(chat_id, user_id, "weapon")
            det_str = ", ".join(
                f"{d['label']} ({d['confidence']:.0%})"
                for d in result.get("detections", [])
                if d.get("type") == "weapon"
            )
            asyncio.create_task(_warn(
                c, chat_id,
                f"╭───────────────────\n"
                f"│ 🔫 <b>WEAPON DETECTED</b>\n"
                f"╰───────────────────\n"
                f"👤 <b>User:</b> {mention}\n"
                f"🔍 <b>Detected:</b> <code>{det_str or 'weapon'}</code>\n"
                f"⚠️ <b>Action:</b> Message deleted."
            ))

        # ── 3. Drugs ──────────────────────────────────────────────────────────
        if result.get("has_drugs"):
            if not deleted:
                try:
                    await m.delete()
                    deleted = True
                except Exception:
                    pass
            NSFWViolations().add_violation(chat_id, user_id, "drugs")
            det_str = ", ".join(
                f"{d['label']} ({d['confidence']:.0%})"
                for d in result.get("detections", [])
                if d.get("type") == "drug"
            )
            asyncio.create_task(_warn(
                c, chat_id,
                f"╭───────────────────\n"
                f"│ 💊 <b>DRUGS DETECTED</b>\n"
                f"╰───────────────────\n"
                f"👤 <b>User:</b> {mention}\n"
                f"🔍 <b>Detected:</b> <code>{det_str or 'drug-related'}</code>\n"
                f"⚠️ <b>Action:</b> Message deleted."
            ))

    except Exception as ef:
        LOGGER.error(f"[nsfw_handler] {ef}")
        LOGGER.error(format_exc())
    finally:
        # Cleanup original (processed already deleted by detect_nsfw)
        try:
            if original_path and os.path.exists(original_path):
                os.remove(original_path)
        except Exception:
            pass



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROFILE PIC NSFW HANDLER — new member join pe check
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(filters.group & filters.new_chat_members, group=8)
async def nsfw_pfp_check(c: Gojo, m: Message):
    """
    Jado koi user join kare — uski profile pic NSFW check karo.
    NSFW howe toh user nu kick karo + alert bhejo.
    """
    nsfw_cfg = NSFWSettings()
    nsfw_app = NSFWApprove()
    chat_id  = m.chat.id
    mode     = nsfw_cfg.get_mode(chat_id)

    if mode == "off":
        return

    for new_user in m.new_chat_members:
        if not new_user or new_user.is_bot:
            continue

        user_id = new_user.id

        if not await _should_delete(c, chat_id, user_id, mode, False, nsfw_app):
            continue

        pfp_path = None
        try:
            # Download profile photo
            photos = await c.get_chat_photos(user_id, limit=1)
            if not photos:
                continue

            photo    = photos[0]
            pfp_path = get_media_path(user_id, f"pfp_{photo.file_id}")
            await c.download_media(photo.file_id, file_name=pfp_path)

            if not os.path.exists(pfp_path):
                continue

            result = detect_nsfw(pfp_path)  # auto-deletes pfp_path
            pfp_path = None

            if not result:
                continue

            triggered = None
            for cat, threshold in NSFW_THRESHOLDS.items():
                if result.get("nsfw", {}).get(cat, 0) >= threshold:
                    triggered = cat
                    break

            if not triggered:
                continue

            # Kick user
            try:
                await c.ban_chat_member(chat_id, user_id)
                await c.unban_chat_member(chat_id, user_id)  # kick (ban+unban)
            except Exception:
                pass

            NSFWViolations().add_violation(chat_id, user_id, f"pfp_{triggered}")
            mention = await mention_html(new_user.first_name, user_id)
            score   = result["nsfw"].get(triggered, 0)

            warn_txt = (
                "╭───────────────────\n"
                "│ 🔞 <b>NSFW PROFILE PIC</b>\n"
                "╰───────────────────\n"
                f"👤 <b>User:</b> {mention}\n"
                f"📊 <b>Category:</b> <code>{triggered}</code> ({score:.0%})\n"
                "⚠️ <b>Action:</b> User kicked."
            )
            asyncio.create_task(_warn(c, chat_id, warn_txt))

        except Exception as ef:
            LOGGER.error(f"[nsfw_pfp] {ef}")
            LOGGER.error(format_exc())
        finally:
            try:
                if pfp_path and os.path.exists(pfp_path):
                    os.remove(pfp_path)
            except Exception:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwmode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwmode") & filters.group)
async def set_nsfw_mode(c: Gojo, m: Message):
    user_id = m.from_user.id
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
        return await m.reply_text("❌ Use: <code>off | soft | normal | strict</code>")

    NSFWSettings().set_mode(m.chat.id, new_mode)
    mode_desc = {
        "off":    "NSFW detection <b>disabled</b>.",
        "soft":   "Admins' stickers safe, others' NSFW deleted.",
        "normal": "Owner + admins + approved safe.",
        "strict": "Only bot owner + approved safe.",
    }
    await m.reply_text(
        f"✅ NSFW mode → <code>{new_mode}</code>\n<i>{mode_desc[new_mode]}</i>"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwapprove
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwapprove") & filters.group)
async def nsfw_approve(c: Gojo, m: Message):
    user_id = m.from_user.id
    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only group owner or bot owner can approve users.")
    try:
        target_id, target_name, _ = await extract_user(c, m)
    except Exception:
        return await m.reply_text("❌ User not found.")
    if not target_id:
        return await m.reply_text("❌ User not found.")
    db = NSFWApprove()
    if db.approve(m.chat.id, target_id, user_id):
        mention = await mention_html(target_name, target_id)
        await m.reply_text(f"✅ {mention} approved — NSFW filter skips this user.")
    else:
        await m.reply_text("⚠️ Already approved.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwunapprove
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwunapprove") & filters.group)
async def nsfw_unapprove(c: Gojo, m: Message):
    user_id = m.from_user.id
    if not _is_bot_owner(user_id) and not await _is_group_owner(c, m.chat.id, user_id):
        return await m.reply_text("🚫 Only group owner or bot owner can unapprove.")
    try:
        target_id, target_name, _ = await extract_user(c, m)
    except Exception:
        return await m.reply_text("❌ User not found.")
    db = NSFWApprove()
    if db.unapprove(m.chat.id, target_id):
        mention = await mention_html(target_name, target_id)
        await m.reply_text(f"✅ {mention} removed from approved list.")
    else:
        await m.reply_text("⚠️ User was not approved.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwapproved
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwapproved") & filters.group)
async def nsfw_approved_list(c: Gojo, m: Message):
    approved = NSFWApprove().list_approved(m.chat.id)
    if not approved:
        return await m.reply_text("No approved users in this chat.")
    lines = []
    for u in approved:
        try:
            user    = await c.get_users(u["user_id"])
            mention = await mention_html(user.first_name, user.id)
        except Exception:
            mention = f"<code>{u['user_id']}</code>"
        lines.append(f"• {mention}")
    await m.reply_text(
        f"✅ <b>NSFW Approved</b> ({len(lines)})\n\n" + "\n".join(lines)
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwstats
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
        return await m.reply_text(f"✅ {mention} has no violations in this chat.")

    lines = [
        f"🔸 <code>{v['category']}</code> — {v['count']}x "
        f"(last: {str(v.get('last_seen','')).split('.')[0]})"
        for v in violations
    ]
    await m.reply_text(f"📊 <b>Violations:</b> {mention}\n\n" + "\n".join(lines))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /nsfwclean — bot owner manually saaf kare
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("nsfwclean") & filters.group)
async def nsfw_clean_cmd(c: Gojo, m: Message):
    if not _is_bot_owner(m.from_user.id):
        return
    ok = clean_media_folder()
    await m.reply_text("✅ Media folder cleaned!" if ok else "❌ Failed.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PLUGIN INFO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__PLUGIN__ = "nsfw"
__alt_name__ = ["nsfwmode", "nsfwapprove"]

__HELP__ = """
<b>🔞 NSFW Filter</b>

Auto-detects and deletes NSFW content, weapons 🔫, and drugs 💊.

<b>Modes (group owner / bot owner only):</b>
• <code>off</code> — Disabled
• <code>soft</code> — Admins' stickers safe, others deleted
• <code>normal</code> — Owner + admins + approved safe
• <code>strict</code> — Only bot owner + approved safe

<b>Commands:</b>
• /nsfwmode <code>[off|soft|normal|strict]</code> — Set mode
• /nsfwapprove — Approve user (reply/@user)
• /nsfwunapprove — Remove approval
• /nsfwapproved — List approved users
• /nsfwstats — View violation history
• /nsfwstats <code>[reply/@user]</code> — Someone's history
"""
