from asyncio import sleep
from html import escape
from os import remove
from traceback import format_exc

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus as CMS
from pyrogram.enums import ChatType
from pyrogram.errors import (BotChannelsNa, ChatAdminInviteRequired,
                             ChatAdminRequired, FloodWait, RightForbidden,
                             RPCError, UserAdminInvalid)
from pyrogram.types import (ChatPrivileges, Message, CallbackQuery,
                            InlineKeyboardMarkup, InlineKeyboardButton)

from Powers import LOGGER, OWNER_ID
from Powers.bot_class import Gojo
from Powers.database.approve_db import Approve
from Powers.database.reporting_db import Reporting
from Powers.supports import get_support_staff
from Powers.utils.caching import ADMIN_CACHE, admin_cache_reload
from Powers.utils.custom_filters import admin_filter, command, promote_filter
from Powers.utils.extract_user import extract_user
from Powers.utils.parser import mention_html


@Gojo.on_message(command("adminlist"))
async def adminlist_show(_, m: Message):
    global ADMIN_CACHE
    if m.chat.type not in [ChatType.SUPERGROUP, ChatType.GROUP]:
        return await m.reply_text(
            text="This command is made to be used in groups only!",
        )
    try:
        try:
            admin_list = ADMIN_CACHE[m.chat.id]
            note = "<i>Note:</i> These are cached values!"
        except KeyError:
            admin_list = await admin_cache_reload(m, "adminlist")
            note = "<i>Note:</i> These are up-to-date values!"
        adminstr = f"Admins in <b>{m.chat.title}</b>:" + "\n\n"
        bot_admins = [i for i in admin_list if (i[1].lower()).endswith("bot")]
        user_admins = [i for i in admin_list if not (i[1].lower()).endswith("bot")]
        # format is like: (user_id, username/name,anonyamous or not)
        mention_users = [
            (
                admin[1]
                if admin[1].startswith("@")
                else (await mention_html(admin[1], admin[0]))
            )
            for admin in user_admins
            if not admin[2]  # if non-anonyamous admin
        ]
        mention_users.sort(key=lambda x: x[1])
        mention_bots = [
            (
                admin[1]
                if admin[1].startswith("@")
                else (await mention_html(admin[1], admin[0]))
            )
            for admin in bot_admins
        ]
        mention_bots.sort(key=lambda x: x[1])
        adminstr += "<b>User Admins:</b>\n"
        adminstr += "\n".join(f"- {i}" for i in mention_users)
        adminstr += "\n\n<b>Bots:</b>\n"
        adminstr += "\n".join(f"- {i}" for i in mention_bots)
        await m.reply_text(adminstr + "\n\n" + note)

    except Exception as ef:
        if str(ef) == str(m.chat.id):
            await m.reply_text(text="Use /admincache to reload admins!")
        else:
            ef = f"{str(ef)}{admin_list}\n"
            await m.reply_text(
                text=f"Some error occured, report it using `/bug` \n <b>Error:</b> <code>{ef}</code>"
            )
        LOGGER.error(ef)
        LOGGER.error(format_exc())
    return


@Gojo.on_message(command("zombies") & admin_filter)
async def zombie_clean(c: Gojo, m: Message):
    zombie = 0
    wait = await m.reply_text("Searching ... and banning ...")
    failed = 0
    async for member in c.get_chat_members(m.chat.id):
        if member.user.is_deleted:
            zombie += 1
            try:
                await c.ban_chat_member(m.chat.id, member.user.id)
            except UserAdminInvalid:
                failed += 1
            except FloodWait as e:
                await sleep(e.value)
                try:
                    await c.ban_chat_member(m.chat.id, member.user.id)
                except Exception:
                    pass
    if zombie == 0:
        return await wait.edit_text("Group is clean!")
    await wait.delete()
    txt = f"<b>{zombie}</b> Zombies found and {zombie - failed} has been banned!\n{failed} zombies' are immune to me",
    await m.reply_animation("https://graph.org/file/02a1dcf7788186ffb36cb.mp4", caption=txt)
    return


@Gojo.on_message(command("admincache"))
async def reload_admins(_, m: Message):
    global TEMP_ADMIN_CACHE_BLOCK
    if m.chat.type not in [ChatType.SUPERGROUP, ChatType.GROUP]:
        return await m.reply_text(
            "This command is made to be used in groups only!",
        )
    SUPPORT_STAFF = get_support_staff()
    if (
            (m.chat.id in set(TEMP_ADMIN_CACHE_BLOCK.keys()))
            and (m.from_user.id not in SUPPORT_STAFF)
            and TEMP_ADMIN_CACHE_BLOCK[m.chat.id] == "manualblock"
    ):
        await m.reply_text("Can only reload admin cache once per 10 mins!")
        return
    try:
        await admin_cache_reload(m, "admincache")
        TEMP_ADMIN_CACHE_BLOCK[m.chat.id] = "manualblock"
        await m.reply_text(text="Reloaded all admins in this chat!")
    except RPCError as ef:
        await m.reply_text(
            text=f"Some error occured, report it using `/bug` \n <b>Error:</b> <code>{ef}</code>"
        )
        LOGGER.error(ef)
        LOGGER.error(format_exc())
    return


@Gojo.on_message(filters.regex(r"^(?i)@admin(s)?") & filters.group)
async def tag_admins(_, m: Message):
    db = Reporting(m.chat.id)
    if not db.get_settings():
        return
    try:
        admin_list = ADMIN_CACHE[m.chat.id]
    except KeyError:
        admin_list = await admin_cache_reload(m, "adminlist")
    user_admins = [i for i in admin_list if not (i[1].lower()).endswith("bot")]
    mention_users = [(await mention_html("\u2063", admin[0])) for admin in user_admins]
    mention_users.sort(key=lambda x: x[1])
    mention_str = "".join(mention_users)
    await m.reply_text(
        (
            f"{(await mention_html(m.from_user.first_name, m.from_user.id))}"
            f" reported the message to admins!{mention_str}"
        ),
    )


@Gojo.on_message(command("fullpromote") & promote_filter)
async def fullpromote_usr(c: Gojo, m: Message):
    global ADMIN_CACHE
    if len(m.text.split()) == 1 and not m.reply_to_message:
        await m.reply_text(
            text="I can't promote nothing! Give me an username or user id or atleast reply to that user"
        )
        return
    try:
        user_id, user_first_name, user_name = await extract_user(c, m)
    except Exception:
        return
    bot = await c.get_chat_member(m.chat.id, c.me.id)
    if user_id == c.me.id:
        await m.reply_text("Huh, how can I even promote myself?")
        return
    if not bot.privileges.can_promote_members:
        return await m.reply_text(
            "I don't have enough permissions!",
        )  # This should be here
    user = await c.get_chat_member(m.chat.id, m.from_user.id)
    if m.from_user.id != OWNER_ID and user.status != CMS.OWNER:
        return await m.reply_text("This command can only be used by chat owner.")
    # If user is alreay admin
    try:
        admin_list = {i[0] for i in ADMIN_CACHE[m.chat.id]}
    except KeyError:
        admin_list = {
            i[0] for i in (await admin_cache_reload(m, "promote_cache_update"))
        }
    if user_id in admin_list:
        await m.reply_text(
            "This user is already an admin, how am I supposed to re-promote them?",
        )
        return
    try:
        await m.chat.promote_member(user_id=user_id, privileges=bot.privileges)
        title = ""
        if m.chat.type in [ChatType.SUPERGROUP, ChatType.GROUP]:
            title = "Gojo"  # Default fullpromote title
            if len(m.text.split()) == 3 and not m.reply_to_message:
                title = " ".join(m.text.split()[2:16])  # trim title to 16 characters
            elif len(m.text.split()) >= 2 and m.reply_to_message:
                title = " ".join(m.text.split()[1:16])  # trim title to 16 characters

            try:
                await c.set_administrator_title(m.chat.id, user_id, title)
            except RPCError as e:
                LOGGER.error(e)
                LOGGER.error(format_exc())
            except Exception as e:
                LOGGER.error(e)
                LOGGER.error(format_exc())
        await m.reply_text(
            (
                "{promoter} promoted {promoted} in chat <b>{chat_title}</b> with full rights!"
            ).format(
                promoter=(await mention_html(m.from_user.first_name, m.from_user.id)),
                promoted=(await mention_html(user_first_name, user_id)),
                chat_title=f"{escape(m.chat.title)} title set to {title}"
                if title
                else f"{escape(m.chat.title)} title set to Default",
            ),
        )
        # If user is approved, disapprove them as they willbe promoted and get
        # even more rights
        if Approve(m.chat.id).check_approve(user_id):
            Approve(m.chat.id).remove_approve(user_id)
        # ----- Add admin to temp cache -----
        try:
            inp1 = user_name or user_first_name
            admins_group = ADMIN_CACHE[m.chat.id]
            admins_group.append((user_id, inp1))
            ADMIN_CACHE[m.chat.id] = admins_group
        except KeyError:
            await admin_cache_reload(m, "promote_key_error")
    except ChatAdminRequired:
        await m.reply_text(text="I'm not admin or I don't have rights......")
    except RightForbidden:
        await m.reply_text(text="I don't have enough rights to promote this user.")
    except UserAdminInvalid:
        await m.reply_text(
            text="Cannot act on this user, maybe I wasn't the one who changed their permissions."
        )
    except RPCError as e:
        await m.reply_text(
            text=f"Some error occured, report it using `/bug` \n <b>Error:</b> <code>{e}</code>"
        )
        LOGGER.error(e)
        LOGGER.error(format_exc())
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROMOTE — Interactive Permission Selector
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Temporary store: { "chat_id:user_id": {perms dict} }
_promote_sessions: dict = {}

# All toggleable permissions with display names
PERM_LABELS = {
    "can_manage_chat":        "Manage Chat",
    "can_delete_messages":    "Delete Messages",
    "can_restrict_members":   "Restrict Members",
    "can_invite_users":       "Invite Users",
    "can_pin_messages":       "Pin Messages",
    "can_change_info":        "Change Info",
    "can_manage_video_chats": "Manage Video Chats",
    "can_post_messages":      "Post Messages",
    "can_edit_messages":      "Edit Messages",
}


def _promote_keyboard(chat_id: int, user_id: int, perms: dict) -> list:
    """Build toggle button grid for permissions."""
    rows = []
    keys = list(PERM_LABELS.keys())
    # 2 buttons per row
    for i in range(0, len(keys), 2):
        row = []
        for perm in keys[i:i+2]:
            label = PERM_LABELS[perm]
            status = "✅" if perms.get(perm, False) else "☑️"
            row.append((
                f"{status} {label}",
                f"prm_{perm}_{chat_id}_{user_id}"
            ))
        rows.append(row)
    # Done + Cancel
    rows.append([
        ("✅ Done",   f"prm_done_{chat_id}_{user_id}"),
        ("❌ Cancel", f"prm_cancel_{chat_id}_{user_id}"),
    ])
    return rows


@Gojo.on_message(command("promote") & promote_filter)
async def promote_usr(c: Gojo, m: Message):
    global ADMIN_CACHE

    if len(m.text.split()) == 1 and not m.reply_to_message:
        return await m.reply_text(
            "I can't promote nothing! Reply to a user or give username."
        )
    try:
        user_id, user_first_name, user_name = await extract_user(c, m)
    except Exception:
        return

    bot = await c.get_chat_member(m.chat.id, c.me.id)

    if user_id == c.me.id:
        return await m.reply_text("Huh, how can I even promote myself?")

    if not bot.privileges.can_promote_members:
        return await m.reply_text("I don't have enough permissions!")

    # Already admin check
    try:
        admin_list = {i[0] for i in ADMIN_CACHE[m.chat.id]}
    except KeyError:
        admin_list = {i[0] for i in (await admin_cache_reload(m, "promote_cache_update"))}

    if user_id in admin_list:
        return await m.reply_text("This user is already an admin!")

    # Build default permissions (all OFF — user selects what to give)
    default_perms = {p: False for p in PERM_LABELS}

    session_key = f"{m.chat.id}:{user_id}"
    _promote_sessions[session_key] = {
        "perms":      default_perms,
        "requester":  m.from_user.id,
        "user_name":  user_name or user_first_name,
        "user_fname": user_first_name,
    }

    kb = _promote_keyboard(m.chat.id, user_id, default_perms)
    mention = await mention_html(user_first_name, user_id)

    await m.reply_text(
        f"👮 <b>Promote</b> {mention}\n\n"
        f"<i>Select the permissions to give.\n"
        f"Click ☑️ to enable, ✅ to disable.\n"
        f"Press <b>Done</b> when finished.</i>",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text=btn[0], callback_data=btn[1])
                for btn in row
            ]
            for row in kb
        ])
    )


@Gojo.on_callback_query(filters.regex(r"^prm_"))
async def promote_callback(c: Gojo, q: CallbackQuery):
    data      = q.data          # e.g. prm_can_delete_messages_-100123_456
    parts     = data.split("_")
    chat_id   = int(parts[-2])
    user_id   = int(parts[-1])
    action    = "_".join(parts[1:-2])  # e.g. can_delete_messages OR done OR cancel

    session_key = f"{chat_id}:{user_id}"
    session     = _promote_sessions.get(session_key)

    # Only the person who ran /promote can use buttons
    if not session or q.from_user.id != session["requester"]:
        return await q.answer("Not for you!", show_alert=True)

    # ── Cancel ────────────────────────────────────────────────────────────────
    if action == "cancel":
        _promote_sessions.pop(session_key, None)
        await q.edit_message_text("❌ Promotion cancelled.")
        return

    # ── Done — apply permissions ───────────────────────────────────────────────
    if action == "done":
        perms  = session["perms"]
        fname  = session["user_fname"]
        uname  = session["user_name"]

        # Check at least one permission selected
        if not any(perms.values()):
            return await q.answer(
                "Select at least one permission!", show_alert=True
            )

        try:
            await c.promote_chat_member(
                chat_id,
                user_id,
                privileges=ChatPrivileges(**perms)
            )

            # Title — default "Admin"
            try:
                await c.set_administrator_title(chat_id, user_id, "Admin")
            except RPCError:
                pass

            # Remove from approved if present
            if Approve(chat_id).check_approve(user_id):
                Approve(chat_id).remove_approve(user_id)

            # Update admin cache
            try:
                admins_group = ADMIN_CACHE[chat_id]
                admins_group.append((user_id, uname))
                ADMIN_CACHE[chat_id] = admins_group
            except KeyError:
                pass

            _promote_sessions.pop(session_key, None)

            # Build summary of granted permissions
            granted = [PERM_LABELS[p] for p, v in perms.items() if v]
            granted_str = "\n".join(f"  ✅ {g}" for g in granted) if granted else "  None"

            promoter_mention = await mention_html(q.from_user.first_name, q.from_user.id)
            promoted_mention = await mention_html(fname, user_id)

            await q.edit_message_text(
                f"👮 {promoter_mention} promoted {promoted_mention} in <b>{escape(q.message.chat.title)}</b>!\n\n"
                f"<b>Permissions granted:</b>\n{granted_str}"
            )

        except ChatAdminRequired:
            await q.edit_message_text("I'm not admin or I don't have rights.")
        except RightForbidden:
            await q.edit_message_text("I don't have enough rights to promote this user.")
        except UserAdminInvalid:
            await q.edit_message_text("Cannot act on this user.")
        except RPCError as e:
            await q.edit_message_text(f"Error: <code>{e}</code>")
            LOGGER.error(e)
        return

    # ── Toggle permission ─────────────────────────────────────────────────────
    if action in session["perms"]:
        session["perms"][action] = not session["perms"][action]
        _promote_sessions[session_key] = session

        kb = _promote_keyboard(chat_id, user_id, session["perms"])
        mention = await mention_html(session["user_fname"], user_id)

        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton  # noqa — already imported
        await q.edit_message_reply_markup(
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(text=btn[0], callback_data=btn[1])
                    for btn in row
                ]
                for row in kb
            ])
        )
        await q.answer()
    else:
        await q.answer("Unknown action.", show_alert=True)


@Gojo.on_message(command("demote") & promote_filter)
async def demote_usr(c: Gojo, m: Message):
    global ADMIN_CACHE
    if len(m.text.split()) == 1 and not m.reply_to_message:
        await m.reply_text("I can't demote nothing.")
        return
    try:
        user_id, user_first_name, _ = await extract_user(c, m)
    except Exception:
        return
    if user_id == c.me.id:
        await m.reply_text("Get an admin to demote me!")
        return
    # If user not already admin
    try:
        admin_list = {i[0] for i in ADMIN_CACHE[m.chat.id]}
    except KeyError:
        admin_list = {
            i[0] for i in (await admin_cache_reload(m, "demote_cache_update"))
        }
    if user_id not in admin_list:
        await m.reply_text(
            "This user is not an admin, how am I supposed to re-demote them?",
        )
        return
    try:
        await m.chat.promote_member(
            user_id=user_id,
            privileges=ChatPrivileges(can_manage_chat=False),
        )
        # ----- Remove admin from cache -----
        try:
            admin_list = ADMIN_CACHE[m.chat.id]
            user = next(user for user in admin_list if user[0] == user_id)
            admin_list.remove(user)
            ADMIN_CACHE[m.chat.id] = admin_list
        except (KeyError, StopIteration):
            await admin_cache_reload(m, "demote_key_stopiter_error")
        await m.reply_text(
            ("{demoter} demoted {demoted} in <b>{chat_title}</b>!").format(
                demoter=(
                    await mention_html(
                        m.from_user.first_name,
                        m.from_user.id,
                    )
                ),
                demoted=(await mention_html(user_first_name, user_id)),
                chat_title=m.chat.title,
            ),
        )
    except ChatAdminRequired:
        await m.reply_text("I am not admin aroung here.")
    except RightForbidden:
        await m.reply_text("I can't demote users here.")
    except UserAdminInvalid:
        await m.reply_text(
            "Cannot act on this user, maybe I wasn't the one who changed their permissions."
        )
    except BotChannelsNa:
        await m.reply_text(
            "May be the user is bot and due to telegram restrictions I can't demote them. Please do it manually")
    except RPCError as ef:
        await m.reply_text(
            f"Some error occured, report it using `/bug` \n <b>Error:</b> <code>{ef}</code>"
        )
        LOGGER.error(ef)
        LOGGER.error(format_exc())
    return


@Gojo.on_message(command("invitelink"))
async def get_invitelink(c: Gojo, m: Message):
    # Bypass the bot devs, sudos and owner

    DEV_LEVEL = get_support_staff("dev_level")
    if m.from_user.id not in DEV_LEVEL:
        user = await m.chat.get_member(m.from_user.id)
        if not user.privileges.can_invite_users and user.status != CMS.OWNER:
            await m.reply_text(text="You don't have rights to invite users....")
            return False
    try:
        link = await c.export_chat_invite_link(m.chat.id)
        await m.reply_text(
            text=f"Invite Link for Chat <b>{m.chat.id}</b>: {link}",
            disable_web_page_preview=True,
        )
    except ChatAdminRequired:
        await m.reply_text(text="I'm not admin or I don't have rights.")
    except ChatAdminInviteRequired:
        await m.reply_text(text="I don't have permission for invite link!")
    except RightForbidden:
        await m.reply_text(text="You don't have permissions to invite users.")
    except RPCError as ef:
        await m.reply_text(
            text=f"Some error occured, report it using `/bug` \n <b>Error:</b> <code>{ef}</code>"
        )
        LOGGER.error(ef)
        LOGGER.error(format_exc())
    return


@Gojo.on_message(command("setgtitle") & admin_filter)
async def setgtitle(_, m: Message):
    user = await m.chat.get_member(m.from_user.id)
    if not user.privileges.can_change_info and user.status != CMS.OWNER:
        await m.reply_text(
            "You don't have enough permission to use this command!",
        )
        return False
    if len(m.command) < 1:
        return await m.reply_text("Please read /help for using it!")
    gtit = m.text.split(None, 1)[1]
    try:
        await m.chat.set_title(gtit)
    except Exception as e:
        return await m.reply_text(f"Error: {e}")
    return await m.reply_text(
        f"Successfully Changed Group Title From {m.chat.title} To {gtit}",
    )


@Gojo.on_message(command("setgdes") & admin_filter)
async def setgdes(_, m: Message):
    user = await m.chat.get_member(m.from_user.id)
    if not user.privileges.can_change_info and user.status != CMS.OWNER:
        await m.reply_text(
            "You don't have enough permission to use this command!",
        )
        return False
    if len(m.command) < 1:
        return await m.reply_text("Please read /help for using it!")
    desp = m.text.split(None, 1)[1]
    try:
        await m.chat.set_description(desp)
    except Exception as e:
        return await m.reply_text(f"Error: {e}")
    return await m.reply_text(
        f"Successfully Changed Group description From {m.chat.description} To {desp}",
    )


@Gojo.on_message(command("title") & admin_filter)
async def set_user_title(c: Gojo, m: Message):
    user = await m.chat.get_member(m.from_user.id)
    if not user.privileges.can_promote_members and user.status != CMS.OWNER:
        await m.reply_text(
            "You don't have enough permission to use this command!",
        )
        return False
    if len(m.text.split()) == 1 and not m.reply_to_message:
        return await m.reply_text("To whom??")
    if m.reply_to_message:
        if len(m.text.split()) >= 2:
            reason = m.text.split(None, 1)[1]
    elif len(m.text.split()) >= 3:
        reason = m.text.split(None, 2)[2]
    try:
        user_id, _, _ = await extract_user(c, m)
    except Exception:
        return
    if not user_id:
        return await m.reply_text("Cannot find user!")
    if user_id == c.me.id:
        return await m.reply_text("Huh, why ?")
    if not reason:
        return await m.reply_text("Read /help please!")
    from_user = await c.get_users(user_id)
    title = reason
    try:
        await c.set_administrator_title(m.chat.id, from_user.id, title)
    except Exception as e:
        return await m.reply_text(f"Error: {e}")
    return await m.reply_text(
        f"Successfully Changed {from_user.mention}'s Admin Title To {title}",
    )


@Gojo.on_message(command("setgpic") & admin_filter)
async def setgpic(c: Gojo, m: Message):
    user = await m.chat.get_member(m.from_user.id)
    if not user.privileges.can_change_info and user.status != CMS.OWNER:
        await m.reply_text(
            "You don't have enough permission to use this command!",
        )
        return False
    if not m.reply_to_message:
        return await m.reply_text("Reply to a photo to set it as chat photo")
    if not m.reply_to_message.photo and not m.reply_to_message.document:
        return await m.reply_text("Reply to a photo to set it as chat photo")
    photo = await m.reply_to_message.download()
    is_vid = bool(m.reply_to_message.video)
    try:
        await m.chat.set_photo(photo, video=is_vid)
    except Exception as e:
        remove(photo)
        return await m.reply_text(f"Error: {e}")
    await m.reply_text("Successfully Changed Group Photo!")
    remove(photo)


__PLUGIN__ = "admin"
__alt_name__ = [
    "admins",
    "promote",
    "demote",
    "adminlist",
    "setgpic",
    "title",
    "setgtitle",
    "fullpromote",
    "invitelink",
    "setgdes",
    "zombies",
]
__HELP__ = """
**Admin**

**User Commands:**
• /adminlist: List all the admins in the Group.

**Admin only:**
• /invitelink: Gets chat invitelink.
• /promote: Promotes the user replied to or tagged (supports with title).
• /fullpromote: Fully Promotes the user replied to or tagged (supports with title).
• /demote: Demotes the user replied to or tagged.
• /setgpic: Set group picture.
• /admincache: Reloads the List of all the admins in the Group.
• /zombies: Bans all the deleted accounts. (owner only)
• /title: sets a custom title for an admin that the bot promoted.
• /disable <commandname>: Stop users from using "commandname" in this group.
• /enable <item name>: Allow users from using "commandname" in this group.
• /disableable: List all disableable commands.
• /disabledel <yes/off>: Delete disabled commands when used by non-admins.
• /disabled: List the disabled commands in this chat.
• /enableall: enable all disabled commands.

**Example:**
`/promote @username`: this promotes a user to admin."""
