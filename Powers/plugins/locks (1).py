from asyncio import sleep
from datetime import datetime, timedelta
from traceback import format_exc

from pyrogram import filters
from pyrogram.enums import MessageEntityType as MET
from pyrogram.enums import MessageServiceType as MST
from pyrogram.errors import (ChatAdminRequired, ChatNotModified, RPCError,
                             UserAdminInvalid)
from pyrogram.types import CallbackQuery, ChatPermissions, Message

from Powers import LOGGER
from Powers.bot_class import Gojo
from Powers.database.approve_db import Approve
from Powers.database.locks_db import LOCKS
from Powers.supports import get_support_staff
from Powers.utils.caching import ADMIN_CACHE, admin_cache_reload
from Powers.utils.custom_filters import command, restrict_filter
from Powers.utils.kbhelpers import ikb

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WARNING LINE — shown when locked content is sent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOT_ALLOWED = "⚠️ <b>This is not allowed in this GC.</b>"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ALL LOCK TYPES (Rose style — full list)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Full lock types list — shown as buttons like Rose
ALL_LOCK_TYPES = [
    "all", "album", "anonchannel", "audio", "bot", "botlink",
    "button", "cashtag", "checklist", "cjk", "command", "comment",
    "contact", "cyrillic", "document", "email", "emoji", "emojicustom",
    "emojigame", "emojionly", "externalreply", "forward", "forwardbot",
    "forwardchannel", "forwardstory", "forwarduser", "game", "gif",
    "inline", "invitelink", "location", "phone", "photo", "poll",
    "rtl", "spoiler", "sticker", "stickeranimate", "stickerpremium",
    "text", "url", "video", "videonote", "voice", "zalgo",
    # Original types
    "msg", "media", "polls", "invite", "pin", "info",
    "webprev", "inlinebots", "animations", "games", "stickers",
    "forwardall", "forwardu", "forwardc", "links",
]

l_t = """
<b>🔒 Lock Types:</b>
- <code>all</code> = Everything
- <code>msg</code> = Messages
- <code>media</code> = Media (Photo, Video, Audio, Doc)
- <code>photo</code> = Photos
- <code>video</code> = Videos
- <code>audio</code> = Audio files
- <code>document</code> = Documents/Files
- <code>gif</code> = GIFs / Animations
- <code>sticker</code> = Stickers
- <code>stickeranimate</code> = Animated Stickers
- <code>stickerpremium</code> = Premium Stickers
- <code>voice</code> = Voice messages
- <code>videonote</code> = Video notes (round videos)
- <code>polls</code> / <code>poll</code> = Polls
- <code>invite</code> / <code>invitelink</code> = Add users / Invite links
- <code>pin</code> = Pin Messages
- <code>info</code> = Change Group Info
- <code>webprev</code> = Web Page Previews
- <code>inline</code> / <code>inlinebots</code> = Inline bots
- <code>animations</code> = Animations
- <code>games</code> / <code>game</code> = Game Bots
- <code>anonchannel</code> = Send as chat
- <code>forwardall</code> / <code>forward</code> = All forwarding
- <code>forwardu</code> / <code>forwarduser</code> = Forward from user
- <code>forwardc</code> / <code>forwardchannel</code> = Forward from channel
- <code>forwardbot</code> = Forward from bots
- <code>forwardstory</code> = Forward stories
- <code>links</code> / <code>url</code> = Links
- <code>bot</code> = Adding bots forbidden
- <code>botlink</code> = Bot links
- <code>emoji</code> = Any emoji
- <code>emojicustom</code> = Custom emoji
- <code>emojigame</code> = Game emoji
- <code>emojionly</code> = Emoji only messages
- <code>spoiler</code> = Spoiler text
- <code>cashtag</code> = Cashtags ($BTC etc)
- <code>email</code> = Email addresses
- <code>phone</code> = Phone numbers
- <code>contact</code> = Contact sharing
- <code>location</code> = Location sharing
- <code>rtl</code> = Right-to-left text
- <code>cjk</code> = Chinese/Japanese/Korean text
- <code>cyrillic</code> = Cyrillic (Russian) text
- <code>zalgo</code> = Zalgo/glitched text
- <code>command</code> = Bot commands
- <code>comment</code> = Comments
- <code>button</code> = Inline buttons
- <code>checklist</code> = Checklists
- <code>album</code> = Media albums
- <code>text</code> = Plain text messages
- <code>externalreply</code> = External replies
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER — build 3-column button grid like Rose
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_locktype_buttons():
    """Build Rose-style 3-column button grid for all lock types."""
    types = sorted(set(ALL_LOCK_TYPES))
    rows = []
    row = []
    for i, lt in enumerate(types):
        row.append((lt, f"LOCKTYPE_INFO_{lt}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    # Back button at bottom
    rows.append([("« Back to Help", "LOCK_TYPES_back")])
    return rows


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCK TYPE DESCRIPTIONS (for button popup like Rose)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOCK_DESCRIPTIONS = {
    "all": "Locks everything in the chat.",
    "msg": "No member can send any messages.",
    "media": "Blocks all media: photos, videos, audio, documents.",
    "photo": "Blocks photos.",
    "video": "Blocks video files.",
    "audio": "Blocks audio files.",
    "document": "Blocks documents and files.",
    "gif": "Blocks GIFs and animations.",
    "sticker": "Blocks all stickers.",
    "stickeranimate": "Blocks animated stickers.",
    "stickerpremium": "Blocks premium stickers.",
    "voice": "Blocks voice messages.",
    "videonote": "Blocks round video messages.",
    "polls": "Blocks polls.",
    "poll": "Blocks polls.",
    "invite": "Blocks adding users to the group.",
    "invitelink": "Blocks sharing invite links.",
    "pin": "Blocks pinning messages.",
    "info": "Blocks changing group info.",
    "webprev": "Blocks web page previews in links.",
    "inline": "Blocks inline bots.",
    "inlinebots": "Blocks inline bots.",
    "animations": "Blocks animations.",
    "games": "Blocks game bots.",
    "game": "Blocks game bots.",
    "anonchannel": "Blocks sending messages as a channel.",
    "forwardall": "Blocks all forwarded messages.",
    "forward": "Blocks all forwarded messages.",
    "forwardu": "Blocks messages forwarded from users.",
    "forwarduser": "Blocks messages forwarded from users.",
    "forwardc": "Blocks messages forwarded from channels.",
    "forwardchannel": "Blocks messages forwarded from channels.",
    "forwardbot": "Blocks messages forwarded from bots.",
    "forwardstory": "Blocks forwarded stories.",
    "links": "Blocks all links and URLs.",
    "url": "Blocks all links and URLs.",
    "bot": "Blocks adding new bots to the group.",
    "botlink": "Blocks bot links (t.me/botname).",
    "emoji": "Blocks messages containing any emoji.",
    "emojicustom": "Blocks custom emoji.",
    "emojigame": "Blocks game emoji.",
    "emojionly": "Blocks messages that are emoji only.",
    "spoiler": "Blocks spoiler text.",
    "cashtag": "Blocks cashtags like $BTC.",
    "email": "Blocks email addresses in messages.",
    "phone": "Blocks phone numbers in messages.",
    "contact": "Blocks contact sharing.",
    "location": "Blocks location sharing.",
    "rtl": "Blocks right-to-left text (Arabic, Hebrew etc).",
    "cjk": "Blocks Chinese, Japanese, Korean characters.",
    "cyrillic": "Blocks Cyrillic/Russian text.",
    "zalgo": "Blocks glitched/zalgo text.",
    "command": "Blocks bot commands.",
    "comment": "Blocks comments.",
    "button": "Blocks messages with inline buttons.",
    "checklist": "Blocks checklists.",
    "album": "Blocks media albums.",
    "text": "Blocks plain text messages.",
    "externalreply": "Blocks external reply previews.",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /locktypes — Rose style buttons
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _fwd_user(m):
    """_fwd_user(m) replacement"""
    try:
        return m.forward_origin.sender_user if m.forward_origin else None
    except AttributeError:
        return None

def _fwd_chat(m):
    """_fwd_chat(m) replacement"""
    try:
        return m.forward_origin.chat if m.forward_origin else None
    except AttributeError:
        return None


@Gojo.on_message(command("locktypes"))
async def lock_types(_, m: Message):
    kb = ikb(_build_locktype_buttons())
    await m.reply_text(
        "🔒 <b>The available lock types are:</b>\n"
        "<i>Tap any type to see what it does.</i>",
        reply_markup=kb
    )
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALLBACK — button tap shows description (like Rose popup)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_callback_query(filters.regex("^LOCKTYPE_INFO_"))
async def locktype_info_callback(_, q: CallbackQuery):
    lock_type = q.data.replace("LOCKTYPE_INFO_", "")
    desc = LOCK_DESCRIPTIONS.get(lock_type, "No description available.")
    await q.answer(
        f"{lock_type}:\n\n{desc}",
        show_alert=True
    )


@Gojo.on_callback_query(filters.regex("^LOCK_TYPES"))
async def lock_types_callback(_, q: CallbackQuery):
    data = q.data
    if data == "LOCK_TYPES":
        kb = ikb(_build_locktype_buttons())
        await q.edit_message_text(
            "🔒 <b>The available lock types are:</b>\n"
            "<i>Tap any type to see what it does.</i>",
            reply_markup=kb
        )
    else:
        kb = ikb([[("Lock Types 🔒", "LOCK_TYPES")]])
        await q.edit_message_text(
            __HELP__,
            reply_markup=kb
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /lock
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("lock") & restrict_filter)
async def lock_perm(c: Gojo, m: Message):
    if len(m.text.split()) < 2:
        await m.reply_text("Please enter a permission to lock!")
        return
    lock_type = m.text.split(None, 1)[1].lower().strip()
    chat_id = m.chat.id

    if not lock_type:
        await m.reply_text(text="Specify a permission to lock!")
        return

    get_perm = m.chat.permissions
    msg = get_perm.can_send_messages
    media = get_perm.can_send_media_messages
    webprev = get_perm.can_add_web_page_previews
    polls = get_perm.can_send_polls
    info = get_perm.can_change_info
    invite = get_perm.can_invite_users
    pin = get_perm.can_pin_messages
    stickers = animations = games = inlinebots = None
    lock = LOCKS()

    if lock_type == "all":
        try:
            await c.set_chat_permissions(chat_id, ChatPermissions())
            lock.insert_lock_channel(m.chat.id, "all")
        except ChatNotModified:
            pass
        except ChatAdminRequired:
            await m.reply_text(text="I don't have permission to do that")
            return
        await m.reply_text("🔒 Locked <b>all</b> permissions in this chat!\n\n" + NOT_ALLOWED)
        await prevent_approved(m)
        return

    # ── Telegram native permissions ───────────────────────────────────────────
    if lock_type == "msg":
        msg = False; perm = "messages"
    elif lock_type == "media":
        media = False; perm = "media"
    elif lock_type in ("stickers", "sticker"):
        stickers = False; perm = "stickers"
    elif lock_type in ("animations", "gif"):
        animations = False; perm = "animations/GIFs"
    elif lock_type in ("games", "game"):
        games = False; perm = "games"
    elif lock_type in ("inlinebots", "inline"):
        inlinebots = False; perm = "inline bots"
    elif lock_type == "webprev":
        webprev = False; perm = "web page previews"
    elif lock_type in ("polls", "poll"):
        polls = False; perm = "polls"
    elif lock_type == "info":
        info = False; perm = "group info changes"
    elif lock_type in ("invite", "invitelink"):
        invite = False; perm = "inviting users"
    elif lock_type == "pin":
        pin = False; perm = "pinning messages"

    # ── DB-based locks ────────────────────────────────────────────────────────
    elif lock_type == "bot":
        curr = lock.insert_lock_channel(m.chat.id, "bot")
        if not curr:
            await m.reply_text("Already locked!")
            return
        await m.reply_text("🔒 Adding bots is now restricted.\n\n" + NOT_ALLOWED)
        return
    elif lock_type in ("links", "url"):
        curr = lock.insert_lock_channel(m.chat.id, "anti_links")
        if not curr:
            await m.reply_text("Already locked!")
            return
        await m.reply_text("🔒 Links are now locked.\n\n" + NOT_ALLOWED)
        return
    elif lock_type == "anonchannel":
        curr = lock.insert_lock_channel(m.chat.id, "anti_c_send")
        if not curr:
            await m.reply_text("Already locked!")
            return
        await m.reply_text("🔒 Sending as channel is now locked.\n\n" + NOT_ALLOWED)
        return
    elif lock_type in ("forwardall", "forward"):
        curr = lock.insert_lock_channel(m.chat.id, "anti_fwd")
        if not curr:
            await m.reply_text("Already locked!")
            return
        await m.reply_text("🔒 All forwarding is now locked.\n\n" + NOT_ALLOWED)
        return
    elif lock_type in ("forwardu", "forwarduser"):
        curr = lock.insert_lock_channel(m.chat.id, "anti_fwd_u")
        if not curr:
            await m.reply_text("Already locked!")
            return
        await m.reply_text("🔒 Forwarding from users is now locked.\n\n" + NOT_ALLOWED)
        return
    elif lock_type in ("forwardc", "forwardchannel"):
        curr = lock.insert_lock_channel(m.chat.id, "anti_fwd_c")
        if not curr:
            await m.reply_text("Already locked!")
            return
        await m.reply_text("🔒 Forwarding from channels is now locked.\n\n" + NOT_ALLOWED)
        return
    elif lock_type in ("photo", "video", "audio", "document", "voice",
                       "videonote", "contact", "location", "phone",
                       "email", "cashtag", "spoiler", "rtl", "cjk",
                       "cyrillic", "zalgo", "command", "comment", "button",
                       "checklist", "album", "text", "emoji", "emojicustom",
                       "emojigame", "emojionly", "externalreply",
                       "forwardbot", "forwardstory", "botlink",
                       "stickeranimate", "stickerpremium"):
        curr = lock.insert_lock_channel(m.chat.id, lock_type)
        if not curr:
            await m.reply_text("Already locked!")
            return
        desc = LOCK_DESCRIPTIONS.get(lock_type, lock_type)
        await m.reply_text(f"🔒 Locked <b>{lock_type}</b>.\n<i>{desc}</i>\n\n{NOT_ALLOWED}")
        return
    else:
        await m.reply_text(
            "❌ Invalid Lock Type!\nUse /locktypes to see all available types."
        )
        return

    try:
        await c.set_chat_permissions(
            chat_id,
            ChatPermissions(
                can_send_messages=msg,
                can_send_media_messages=media,
                can_send_other_messages=any([stickers, animations, games, inlinebots]),
                can_add_web_page_previews=webprev,
                can_send_polls=polls,
                can_change_info=info,
                can_invite_users=invite,
                can_pin_messages=pin,
            ),
        )
    except ChatNotModified:
        pass
    except ChatAdminRequired:
        await m.reply_text(text="I don't have permission to do that")
        return
    await m.reply_text(f"🔒 Locked <b>{perm}</b> in this chat.\n\n{NOT_ALLOWED}")
    await prevent_approved(m)
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /locks — view current locks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("locks") & restrict_filter)
async def view_locks(_, m: Message):
    chkmsg = await m.reply_text(text="Checking Chat permissions...")
    v_perm = m.chat.permissions

    async def convert_to_emoji(val: bool):
        return "✅" if val else "❌"

    lock = LOCKS()
    anon    = lock.get_lock_channel(m.chat.id, "anti_c_send")
    anti_f  = lock.get_lock_channel(m.chat.id, "anti_fwd")
    anti_f_u = lock.get_lock_channel(m.chat.id, "anti_fwd_u")
    anti_f_c = lock.get_lock_channel(m.chat.id, "anti_fwd_c")
    antil   = lock.get_lock_channel(m.chat.id, "anti_links")
    bots    = lock.get_lock_channel(m.chat.id, "bot")

    vmsg     = await convert_to_emoji(v_perm.can_send_messages)
    vmedia   = await convert_to_emoji(v_perm.can_send_media_messages)
    vother   = await convert_to_emoji(v_perm.can_send_other_messages)
    vwebprev = await convert_to_emoji(v_perm.can_add_web_page_previews)
    vpolls   = await convert_to_emoji(v_perm.can_send_polls)
    vinfo    = await convert_to_emoji(v_perm.can_change_info)
    vinvite  = await convert_to_emoji(v_perm.can_invite_users)
    vpin     = await convert_to_emoji(v_perm.can_pin_messages)
    vanon    = await convert_to_emoji(anon)
    vanti    = await convert_to_emoji(anti_f)
    vantiu   = await convert_to_emoji(anti_f_u)
    vantic   = await convert_to_emoji(anti_f_c)
    vantil   = await convert_to_emoji(antil)
    vantibot = await convert_to_emoji(bots)

    if v_perm is not None:
        try:
            permission_view_str = f"""<b>🔒 Chat Permissions:</b>

  <b>Send Messages:</b> {vmsg}
  <b>Send Media:</b> {vmedia}
  <b>Send Stickers/Anim/Games:</b> {vother}
  <b>Webpage Preview:</b> {vwebprev}
  <b>Send Polls:</b> {vpolls}
  <b>Change Info:</b> {vinfo}
  <b>Invite Users:</b> {vinvite}
  <b>Pin Messages:</b> {vpin}
  <b>Send as Channel:</b> {vanon}
  <b>Forward (all):</b> {vanti}
  <b>Forward (from user):</b> {vantiu}
  <b>Forward (from channel):</b> {vantic}
  <b>Send Links:</b> {vantil}
  <b>Add Bots:</b> {vantibot}
"""
            await chkmsg.edit_text(permission_view_str)
        except RPCError as e_f:
            await chkmsg.edit_text(text="Something went wrong!")
            LOGGER.error(e_f)
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /unlock
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("unlock") & restrict_filter)
async def unlock_perm(c: Gojo, m: Message):
    if len(m.text.split()) < 2:
        await m.reply_text("Please enter a permission to unlock!")
        return
    unlock_type = m.text.split(None, 1)[1].lower().strip()
    chat_id = m.chat.id

    if not unlock_type:
        await m.reply_text(text="Specify a permission to unlock!")
        return

    lock = LOCKS()
    if unlock_type == "all":
        try:
            await c.set_chat_permissions(
                chat_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_send_polls=True,
                    can_change_info=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                ),
            )
            lock.remove_lock_channel(m.chat.id, "all")
        except ChatNotModified:
            pass
        except ChatAdminRequired:
            await m.reply_text(text="I don't have permission to do that")
            return
        await m.reply_text("🔓 Unlocked <b>all</b> permissions in this chat!")
        await prevent_approved(m)
        return

    get_uperm = m.chat.permissions
    umsg      = get_uperm.can_send_messages
    umedia    = get_uperm.can_send_media_messages
    uwebprev  = get_uperm.can_add_web_page_previews
    upolls    = get_uperm.can_send_polls
    uinfo     = get_uperm.can_change_info
    uinvite   = get_uperm.can_invite_users
    upin      = get_uperm.can_pin_messages
    ustickers = uanimations = ugames = uinlinebots = None

    if unlock_type == "msg":
        umsg = True; uperm = "messages"
    elif unlock_type == "media":
        umedia = True; uperm = "media"
    elif unlock_type in ("stickers", "sticker"):
        ustickers = True; uperm = "stickers"
    elif unlock_type in ("animations", "gif"):
        uanimations = True; uperm = "animations/GIFs"
    elif unlock_type in ("games", "game"):
        ugames = True; uperm = "games"
    elif unlock_type in ("inlinebots", "inline"):
        uinlinebots = True; uperm = "inline bots"
    elif unlock_type == "webprev":
        uwebprev = True; uperm = "web page previews"
    elif unlock_type in ("polls", "poll"):
        upolls = True; uperm = "polls"
    elif unlock_type == "info":
        uinfo = True; uperm = "group info changes"
    elif unlock_type in ("invite", "invitelink"):
        uinvite = True; uperm = "inviting users"
    elif unlock_type == "pin":
        upin = True; uperm = "pinning messages"

    # ── DB-based unlocks ──────────────────────────────────────────────────────
    elif unlock_type == "bot":
        curr = lock.remove_lock_channel(m.chat.id, "bot")
        if not curr:
            await m.reply_text("Adding bots is already allowed.")
            return
        await m.reply_text("🔓 Adding bots is now allowed.")
        return
    elif unlock_type == "anonchannel":
        curr = lock.remove_lock_channel(m.chat.id, "anti_c_send")
        if not curr:
            await m.reply_text("Send as channel is already allowed.")
            return
        await m.reply_text("🔓 Sending as channel is now allowed.")
        return
    elif unlock_type in ("links", "url"):
        curr = lock.remove_lock_channel(m.chat.id, "anti_links")
        if not curr:
            await m.reply_text("Links are already allowed.")
            return
        await m.reply_text("🔓 Links are now allowed.")
        return
    elif unlock_type in ("forwardall", "forward"):
        curr = lock.remove_lock_channel(m.chat.id, "anti_fwd")
        if not curr:
            await m.reply_text("Forwarding is already allowed.")
            return
        await m.reply_text("🔓 All forwarding is now allowed.")
        return
    elif unlock_type in ("forwardu", "forwarduser"):
        curr = lock.remove_lock_channel(m.chat.id, "anti_fwd_u")
        if not curr:
            await m.reply_text("Forwarding from users is already allowed.")
            return
        await m.reply_text("🔓 Forwarding from users is now allowed.")
        return
    elif unlock_type in ("forwardc", "forwardchannel"):
        curr = lock.remove_lock_channel(m.chat.id, "anti_fwd_c")
        if not curr:
            await m.reply_text("Forwarding from channels is already allowed.")
            return
        await m.reply_text("🔓 Forwarding from channels is now allowed.")
        return
    elif unlock_type in ("photo", "video", "audio", "document", "voice",
                         "videonote", "contact", "location", "phone",
                         "email", "cashtag", "spoiler", "rtl", "cjk",
                         "cyrillic", "zalgo", "command", "comment", "button",
                         "checklist", "album", "text", "emoji", "emojicustom",
                         "emojigame", "emojionly", "externalreply",
                         "forwardbot", "forwardstory", "botlink",
                         "stickeranimate", "stickerpremium"):
        curr = lock.remove_lock_channel(m.chat.id, unlock_type)
        if not curr:
            await m.reply_text(f"{unlock_type} is already allowed.")
            return
        await m.reply_text(f"🔓 Unlocked <b>{unlock_type}</b>.")
        return
    else:
        await m.reply_text(
            "❌ Invalid Lock Type!\nUse /locktypes to see all available types."
        )
        return

    try:
        await c.set_chat_permissions(
            chat_id,
            ChatPermissions(
                can_send_messages=umsg,
                can_send_media_messages=umedia,
                can_send_other_messages=any([ustickers, uanimations, ugames, uinlinebots]),
                can_add_web_page_previews=uwebprev,
                can_send_polls=upolls,
                can_change_info=uinfo,
                can_invite_users=uinvite,
                can_pin_messages=upin,
            ),
        )
    except ChatNotModified:
        pass
    except ChatAdminRequired:
        await m.reply_text(text="I don't have permission to do that")
        return
    await m.reply_text(f"🔓 Unlocked <b>{uperm}</b> in this chat.")
    await prevent_approved(m)
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DELETE LOCKED MESSAGES + NOT ALLOWED WARNING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def delete_messages(c: Gojo, m: Message, warn: bool = True):
    try:
        await m.delete()
        if warn and m.from_user:
            sent = await c.send_message(
                m.chat.id,
                f"{NOT_ALLOWED}",
                parse_mode="html"
            )
            await sleep(8)
            try:
                await sent.delete()
            except Exception:
                pass
    except RPCError as rp:
        LOGGER.error(rp)
        LOGGER.error(format_exc())


async def is_approved_user(c: Gojo, m: Message):
    approved_users = Approve(m.chat.id).list_approved()
    ul = [user[0] for user in approved_users]
    try:
        admins_group = {i[0] for i in ADMIN_CACHE[m.chat.id]}
    except KeyError:
        admins_group = await admin_cache_reload(m, "lock")

    SUDO_LEVEL = get_support_staff("sudo_level")

    if _fwd_user(m):
        return bool(
            m.from_user and (
                m.from_user.id in ul
                or m.from_user.id in SUDO_LEVEL
                or m.from_user.id in admins_group
                or m.from_user.id == c.me.id
            )
        )
    elif _fwd_chat(m):
        if m.from_user and (
            m.from_user.id in ul or m.from_user.id in SUDO_LEVEL
            or m.from_user.id in admins_group or m.from_user.id == c.me.id
        ):
            return True
        elif m.automatic_forward:
            return True
        else:
            return False
    elif m.from_user:
        return (
            m.from_user.id in ul
            or m.from_user.id in SUDO_LEVEL
            or m.from_user.id in admins_group
            or m.from_user.id == c.me.id
        )
    else:
        return False


@Gojo.on_message(filters.service & filters.group, 19)
async def servicess(c: Gojo, m: Message):
    if m.service != MST.NEW_CHAT_MEMBERS:
        return
    approved = await is_approved_user(c, m)
    if approved:
        return
    for i in m.new_chat_members:
        if i.is_bot:
            try:
                timee = datetime.now() + timedelta(minutes=5)
                await m.chat.ban_member(i.id, until_date=timee)
                sleep(1)
            except UserAdminInvalid:
                continue
            except Exception as ef:
                LOGGER.error(ef)
                LOGGER.error(format_exc())
    return


@Gojo.on_message(filters.group & ~filters.me, 3)
async def lock_del_mess(c: Gojo, m: Message):
    lock = LOCKS()
    chat_locks = lock.get_lock_channel(m.chat.id)
    if not chat_locks:
        return

    if (
        chat_locks.get("anti_channel")
        and m.sender_chat
        and not _fwd_chat(m)
        and not _fwd_user(m)
    ):
        if m.chat.is_admin:
            return
        await delete_messages(c, m)
        return

    is_approved = await is_approved_user(c, m)
    if is_approved:
        return

    entity = m.entities if m.text else m.caption_entities

    if entity and chat_locks.get("anti_links"):
        for i in entity:
            if i.type in [MET.URL, MET.TEXT_LINK]:
                await delete_messages(c, m)
                return

    elif any(chat_locks.get("anti_fwd", {}).values()) and (_fwd_user(m) or _fwd_chat(m)):
        if all(chat_locks["anti_fwd"].values()):
            await delete_messages(c, m)
            return
        elif chat_locks["anti_fwd"].get("user") and not _fwd_chat(m):
            await delete_messages(c, m)
            return
        elif chat_locks["anti_fwd"].get("chat") and _fwd_chat(m):
            await delete_messages(c, m)
            return


async def prevent_approved(m: Message):
    approved_users = Approve(m.chat.id).list_approved()
    ul = [user[0] for user in approved_users]
    for i in ul:
        try:
            await m.chat.unban_member(user_id=i)
        except (ChatAdminRequired, ChatNotModified, RPCError):
            continue
        await sleep(0.1)
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PLUGIN INFO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__PLUGIN__ = "locks"
__alt_name__ = ["grouplock", "lock", "grouplocks"]

__buttons__ = [[("Lock Types 🔒", "LOCK_TYPES")]]

__HELP__ = """
<b>🔒 Locks</b>

Lock group permissions to keep your GC clean.

<b>Commands:</b>
• /lock <code>&lt;type&gt;</code> — Lock a permission
• /unlock <code>&lt;type&gt;</code> — Unlock a permission
• /locks — View current permissions
• /locktypes — See all lock types with descriptions

<b>Example:</b>
<code>/lock sticker</code> — blocks all stickers
<code>/lock url</code> — blocks all links
<code>/lock photo</code> — blocks photos
"""
