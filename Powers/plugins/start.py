from random import choice
from time import gmtime, strftime, time

from pyrogram import enums, filters
from pyrogram.enums import ChatMemberStatus as CMS
from pyrogram.enums import ChatType
from pyrogram.errors import (MediaCaptionTooLong, MessageNotModified,
                             QueryIdInvalid, RPCError, UserIsBlocked)
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, Message)

from Powers import (HELP_COMMANDS, LOGGER, OWNER_ID, PREFIX_HANDLER,
                    PYROGRAM_VERSION, PYTHON_VERSION, UPTIME, VERSION)
from Powers.bot_class import Gojo
from Powers.database.captcha_db import CAPTCHA_DATA
from Powers.supports import get_support_staff
from Powers.utils.custom_filters import command
from Powers.utils.extras import StartPic
from Powers.utils.kbhelpers import ikb
from Powers.utils.parser import mention_html
from Powers.utils.start_utils import (gen_cmds_kb, gen_start_kb, get_help_msg,
                                      get_private_note, get_private_rules)
from Powers.utils.string import encode_decode


def _safe_name(user) -> str:
    """Safe mention — works even if username is None."""
    return f"[{user.first_name}](tg://user?id={user.id})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(
    command("start") & (filters.group | filters.private),
)
async def start(c: Gojo, m: Message):
    if m.chat.type == ChatType.PRIVATE:
        if len(m.text.strip().split()) > 1:
            arg = m.text.split(None, 1)[1]
            help_option = arg.lower()

            if help_option.startswith("note") and (
                    help_option not in ("note", "notes")
            ):
                await get_private_note(c, m, help_option)
                return

            if help_option.startswith("rules"):
                await get_private_rules(c, m, help_option)
                return

            help_msg, help_kb = await get_help_msg(c, m, help_option)

            if help_msg:
                await m.reply_photo(
                    photo=str(choice(StartPic)),
                    caption=help_msg,
                    parse_mode=enums.ParseMode.MARKDOWN,
                    reply_markup=help_kb,
                    quote=True,
                )
                return

            if len(arg.split("_", 1)) >= 2:
                if arg.split("_")[1] == "help":
                    await m.reply_photo(
                        photo=str(choice(StartPic)),
                        caption=help_msg,
                        parse_mode=enums.ParseMode.MARKDOWN,
                        reply_markup=help_kb,
                        quote=True,
                    )
                    return
                elif arg.split("_", 1)[0] == "qr":
                    decoded = encode_decode(arg.split("_", 1)[1], "decode")
                    decode = decoded.split(":")
                    chat = decode[0]
                    user = decode[1]
                    if m.from_user.id != int(user):
                        await m.reply_text("Not for you Baka")
                        return
                    try:
                        await c.unban_chat_member(int(chat), int(user))
                        msg = CAPTCHA_DATA().del_message_id(chat, user)
                        try:
                            chat_ = await c.get_chat(chat)
                            kb = ikb([[("Link to chat", f"{chat_.invite_link}", "url")]])
                        except Exception:
                            kb = None
                        await m.reply_text("You can now talk in the chat", reply_markup=kb)
                        try:
                            await c.delete_messages(chat, msg)
                        except Exception:
                            pass
                        return
                    except Exception:
                        return

        try:
            cpt = (
                f"Hey {_safe_name(m.from_user)}! I am {c.me.first_name} ✨.\n"
                f"I'm here to help you manage your group(s)!\n"
                f"Hit /help to find out more about how to use me in my full potential!"
            )
            try:
                kb = await gen_start_kb(m)
            except Exception:
                kb = None

            await m.reply_photo(
                photo=str(choice(StartPic)),
                caption=cpt,
                reply_markup=kb,
                quote=True,
            )
        except UserIsBlocked:
            LOGGER.warning(f"Bot blocked by {m.from_user.id}")
        except RPCError as e:
            LOGGER.error(f"[start] {e}")
            try:
                await m.reply_text(cpt)
            except Exception:
                pass
    else:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "Connect me to pm",
                url=f"https://{c.me.username}.t.me/",
            )
        ]])
        await m.reply_photo(
            photo=str(choice(StartPic)),
            caption="I'm alive :3",
            reply_markup=kb,
            quote=True,
        )
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# start_back callback
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_callback_query(filters.regex("^start_back$"))
async def start_back(c: Gojo, q: CallbackQuery):
    try:
        cpt = (
            f"Hey {_safe_name(q.from_user)}! I am {c.me.first_name} ✨.\n"
            f"I'm here to help you manage your group(s)!\n"
            f"Hit /help to find out more about how to use me in my full potential!"
        )
        await q.edit_message_caption(
            caption=cpt,
            reply_markup=(await gen_start_kb(q.message)),
        )
    except MessageNotModified:
        pass
    await q.answer()
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# commands menu callback
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_callback_query(filters.regex("^commands$"))
async def commands_menu(c: Gojo, q: CallbackQuery):
    ou = await gen_cmds_kb(q.message)
    keyboard = ikb(ou, True)
    try:
        cpt = (
            f"Hey **{_safe_name(q.from_user)}**! I am {c.me.first_name} ✨.\n"
            f"I'm here to help you manage your group(s)!\n"
            f"Commands available:\n"
            f"× /start: Start the bot\n"
            f"× /help: Give's you this message.\n\n"
            f"You can use {', '.join(PREFIX_HANDLER)} as your prefix handler"
        )
        await q.edit_message_caption(caption=cpt, reply_markup=keyboard)
    except MessageNotModified:
        pass
    except QueryIdInvalid:
        await q.message.reply_photo(
            photo=str(choice(StartPic)), caption=cpt, reply_markup=keyboard
        )
    await q.answer()
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /help
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_message(command("help"))
async def help_menu(c: Gojo, m: Message):
    if len(m.text.split()) >= 2:
        textt = m.text.replace(" ", "_").replace("_", " ", 1)
        help_option = (textt.split(None)[1]).lower()
        help_msg, help_kb = await get_help_msg(c, m, help_option)

        if not help_msg:
            LOGGER.error(f"No help_msg found for help_option - {help_option}!!")
            return

        if m.chat.type == ChatType.PRIVATE:
            if len(help_msg) >= 1026:
                await m.reply_text(
                    help_msg, parse_mode=enums.ParseMode.MARKDOWN, quote=True
                )
            await m.reply_photo(
                photo=str(choice(StartPic)),
                caption=help_msg,
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=help_kb,
                quote=True,
            )
        else:
            await m.reply_photo(
                photo=str(choice(StartPic)),
                caption=f"Press the button below to get help for <i>{help_option}</i>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "Help",
                        url=f"t.me/{c.me.username}?start={help_option}",
                    )
                ]]),
            )
    else:
        if m.chat.type == ChatType.PRIVATE:
            ou = await gen_cmds_kb(m)
            keyboard = ikb(ou, True)
            msg = (
                f"Hey **{_safe_name(m.from_user)}**! I am {c.me.first_name} ✨.\n"
                f"I'm here to help you manage your group(s)!\n"
                f"Commands available:\n"
                f"× /start: Start the bot\n"
                f"× /help: Give's you this message."
            )
        else:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Help",
                    url=f"t.me/{c.me.username}?start=start_help",
                )
            ]])
            msg = "Contact me in PM to get the list of possible commands."

        await m.reply_photo(
            photo=str(choice(StartPic)),
            caption=msg,
            reply_markup=keyboard,
        )
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pagination helper
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_divided_msg(plugin_name: str, page: int = 1, back_to_do=None):
    msg = HELP_COMMANDS[plugin_name]["help_msg"]
    msg = msg.split("\n")
    l = len(msg)
    new_msg = ""
    total = l // 10
    first = 10 * (page - 1)
    last = 10 * page

    if not first:
        for i in msg[first:last]:
            new_msg += f"{i}\n"
        kb = [[("Next page ▶️", f"iter_page_{plugin_name}_{f'{back_to_do}_' if back_to_do else ''}{page + 1}")]]
    else:
        first += 1
        if page == total:
            for i in msg[first:]:
                new_msg += f"{i}\n"
            kb = [[("◀️ Previous page", f"iter_page_{plugin_name}_{f'{back_to_do}_' if back_to_do else ''}{page - 1}")]]
        else:
            for i in msg[first:last]:
                new_msg += f"{i}\n"
            kb = [[
                ("◀️ Previous page", f"iter_page_{plugin_name}_{f'{back_to_do}_' if back_to_do else ''}{page - 1}"),
                ("Next page ▶️",     f"iter_page_{plugin_name}_{f'{back_to_do}_' if back_to_do else ''}{page + 1}"),
            ]]

    kb = ikb(kb, True, back_to_do) if back_to_do else ikb(kb)
    return new_msg, kb


@Gojo.on_callback_query(filters.regex(r"^iter_page_.*[0-9]$"))
async def helppp_page_iter(c: Gojo, q: CallbackQuery):
    data = q.data.split("_")
    plugin_ = data[2]
    try:
        back_to = data[-2]
    except Exception:
        back_to = None
    curr_page = int(data[-1])
    msg, kb = await get_divided_msg(plugin_, curr_page, back_to_do=back_to)
    await q.edit_message_caption(msg, reply_markup=kb)
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bot info callback
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_callback_query(filters.regex("^bot_curr_info$"))
async def give_curr_info(c: Gojo, q: CallbackQuery):
    start = time()
    up = strftime("%Hh %Mm %Ss", gmtime(time() - UPTIME))
    x = await c.send_message(q.message.chat.id, "Pinging..")
    delta_ping = time() - start
    await x.delete()
    txt = (
        f"🏓 Ping : {delta_ping * 1000:.3f} ms\n"
        f"📈 Uptime : {up}\n"
        f"🤖 Bot version: {VERSION}\n"
        f"🐍 Python version: {PYTHON_VERSION}\n"
        f"🔥 Pyrogram version: {PYROGRAM_VERSION}"
    )
    await q.answer(txt, show_alert=True)
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Plugin info callback
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_callback_query(filters.regex("^plugins."))
async def get_module_info(c: Gojo, q: CallbackQuery):
    module = q.data.split(".", 1)[1]
    help_msg = HELP_COMMANDS[f"plugins.{module}"]["help_msg"]
    help_kb  = HELP_COMMANDS[f"plugins.{module}"]["buttons"]
    try:
        await q.edit_message_caption(
            caption=help_msg,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=ikb(help_kb, True, todo="commands"),
        )
    except MediaCaptionTooLong:
        caption, kb = await get_divided_msg(f"plugins.{module}", back_to_do="commands")
        await q.edit_message_caption(caption, enums.ParseMode.MARKDOWN, kb)
    await q.answer()
    return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Delete callback
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Gojo.on_callback_query(filters.regex("^DELETEEEE$"))
async def delete_back(_, q: CallbackQuery):
    await q.message.delete()
    return
