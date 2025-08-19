import os
import logging
import random
import asyncio
import re
import json
import base64
from validators import domain
from Script import script
from plugins.dbusers import db
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid
from pyrogram.types import *
from utils import verify_user, check_token, check_verification, get_token
from config import *
from urllib.parse import quote_plus
from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size
import time
from datetime import timedelta

logger = logging.getLogger(__name__)

START_TIME = time.time()

BATCH_FILES = {}
WAITING_FOR_TOKEN = {}
WAITING_FOR_WLC = {}
WAITING_FOR_CLONE_PHOTO = {}
WAITING_FOR_CLONE_PHOTO_MSG = {}
AUTO_DELETE_TIME = {}
AUTO_DELETE_MESSAGE = {}

def get_size(size):
    """Get size in readable format"""

    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    chars = ["[", "]", "(", ")"]
    for c in chars:
        file_name.replace(c, "")
    file_name = '@PookieManagerBot ' + ' '.join(filter(lambda x: not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
    return file_name

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    await message.delete()
    try:
        username = client.me.username

        if not await db.is_user_exist(message.from_user.id):
            await db.add_user(message.from_user.id, message.from_user.first_name)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(message.from_user.id, message.from_user.mention))

        if len(message.command) != 2:
            buttons = [[
                InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                InlineKeyboardButton('😊 About', callback_data='about')
                ],[
                InlineKeyboardButton('🤖 Create Your Own Clone', callback_data='clone')
                ],[
                InlineKeyboardButton('🔒 Close', callback_data='close')
            ]]

            await message.reply_text(
                script.START_TXT.format(user=message.from_user.mention, bot=client.me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Start Bot Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""
    if data.split("-", 1)[0] == "verify":
        userid = data.split("-", 2)[1]
        token = data.split("-", 3)[2]
        if str(message.from_user.id) != str(userid):
            return await message.reply_text(
                text="<b>Invalid link or Expired link !</b>",
                protect_content=True
            )
        is_valid = await check_token(client, userid, token)
        if is_valid == True:
            await message.reply_text(
                text=f"<b>Hey {message.from_user.mention}, You are successfully verified !\nNow you have unlimited access for all files till today midnight.</b>",
                protect_content=True
            )
            await verify_user(client, userid, token)
        else:
            return await message.reply_text(
                text="<b>Invalid link or Expired link !</b>",
                protect_content=True
            )
    elif data.split("-", 1)[0] == "BATCH":
        try:
            if not await check_verification(client, message.from_user.id) and VERIFY_MODE == True:
                btn = [[
                    InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://telegram.me/{username}?start="))
                ],[
                    InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)
                ]]
                await message.reply_text(
                    text="<b>You are not verified !\nKindly verify to continue !</b>",
                    protect_content=True,
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return
        except Exception as e:
            return await message.reply_text(f"**Error - {e}**")
        sts = await message.reply("**🔺 ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ**")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            decode_file_id = base64.urlsafe_b64decode(file_id + "=" * (-len(file_id) % 4)).decode("ascii")
            msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
            media = getattr(msg, msg.media.value)
            file_id = media.file_id
            file = await client.download_media(file_id)
            try: 
                with open(file) as file_data:
                    msgs=json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs
            
        filesarr = []
        for msg in msgs:
            channel_id = int(msg.get("channel_id"))
            msgid = msg.get("msg_id")
            info = await client.get_messages(channel_id, int(msgid))
            if info.media:
                file_type = info.media
                file = getattr(info, file_type.value)
                f_caption = getattr(info, 'caption', '')
                if f_caption:
                    f_caption = f_caption.html
                old_title = getattr(file, "file_name", "")
                title = formate_file_name(old_title)
                size=get_size(int(file.file_size))
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption=BATCH_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                    except:
                        f_caption=f_caption
                if f_caption is None:
                    f_caption = f"{title}"
                if STREAM_MODE == True:
                    if info.video or info.document:
                        log_msg = info
                        fileName = {quote_plus(get_name(log_msg))}
                        stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        button = [[
                            InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                            InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                        ],[
                            InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                        ]]
                        reply_markup=InlineKeyboardMarkup(button)
                else:
                    reply_markup = None
                try:
                    msg = await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=False, reply_markup=reply_markup)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=False, reply_markup=reply_markup)
                except:
                    continue
            else:
                try:
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except:
                    continue
            filesarr.append(msg)
            await asyncio.sleep(1) 
        await sts.delete()
        if AUTO_DELETE_MODE == True:
            k = await client.send_message(chat_id = message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{AUTO_DELETE} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(AUTO_DELETE_TIME)
            for x in filesarr:
                try:
                    await x.delete()
                except:
                    pass
            await k.edit_text("<b>Your All Files/Videos is successfully deleted!!!</b>")
        return

    pre, decode_file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
    if not await check_verification(client, message.from_user.id) and VERIFY_MODE == True:
        btn = [[
            InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://telegram.me/{username}?start="))
        ],[
            InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)
        ]]
        await message.reply_text(
            text="<b>You are not verified !\nKindly verify to continue !</b>",
            protect_content=True,
            reply_markup=InlineKeyboardMarkup(btn)
        )
        return
    try:
        msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
        if msg.media:
            media = getattr(msg, msg.media.value)
            title = formate_file_name(media.file_name)
            size=get_size(media.file_size)
            f_caption = f"<code>{title}</code>"
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption=CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='')
                except:
                    return
            if STREAM_MODE == True:
                if msg.video or msg.document:
                    log_msg = msg
                    fileName = {quote_plus(get_name(log_msg))}
                    stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    button = [[
                        InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                        InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                    ],[
                        InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                    ]]
                    reply_markup=InlineKeyboardMarkup(button)
            else:
                reply_markup = None
            del_msg = await msg.copy(chat_id=message.from_user.id, caption=f_caption, reply_markup=reply_markup, protect_content=False)
        else:
            del_msg = await msg.copy(chat_id=message.from_user.id, protect_content=False)
        if AUTO_DELETE_MODE == True:
            k = await client.send_message(chat_id = message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{AUTO_DELETE} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(AUTO_DELETE_TIME)
            try:
                await del_msg.delete()
            except:
                pass
            await k.edit_text("<b>Your File/Video is successfully deleted!!!</b>")
        return
    except:
        pass

async def show_clone_menu(client, message, user_id):
    try:
        clones = await db.get_clone(user_id)
        buttons = []

        if clones:
            # ✅ show list of clones
            for clone in clones:
                bot_name = clone.get("name", f"Clone {clone['bot_id']}")
                buttons.append([InlineKeyboardButton(f'⚙️ {bot_name}', callback_data=f'manage_{clone["bot_id"]}')])
        else:
            # ✅ no clones, show Add Clone button
            buttons.append([InlineKeyboardButton("➕ Add Clone", callback_data="add_clone")])

        # common back button
        buttons.append([InlineKeyboardButton('⬅️ Back', callback_data='start')])

        await message.edit_text(
            script.MANAGEC_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Show Clone Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

async def show_text_menu(msg, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_text_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_text_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_text_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'start_message_{bot_id}')]
        ]
        await msg.edit_text(
            text=script.ST_TXT_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Show Text Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

async def show_photo_menu(msg, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('➕ Add', callback_data=f'add_photo_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_photo_{bot_id}'),
            InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_photo_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'start_message_{bot_id}')]
        ]
        await msg.edit_text(
            text=script.ST_PIC_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Show Photo Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

async def show_time_menu(msg, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_adtime_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_adtime_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_adtime_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'auto_delete_{bot_id}')]
        ]
        await msg.edit_text(
            text=script.AD_TIME_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Show Time Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

async def show_message_menu(msg, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_admessage_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_admessage_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_admessage_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'auto_delete_{bot_id}')]
        ]
        await msg.edit_text(
            text=script.AD_MSG_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Show Message Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    try:
        user_id = query.from_user.id

        # Start Menu
        if query.data == "start":
            buttons = [
                [InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                 InlineKeyboardButton('ℹ️ About', callback_data='about')],
                [InlineKeyboardButton('🤖 Create Your Own Clone', callback_data='clone')],
                [InlineKeyboardButton('🔒 Close', callback_data='close')]
            ]
            me = await client.get_me()
            await query.message.edit_text(
                text=script.START_TXT.format(user=query.from_user.mention, bot=me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Help
        elif query.data == "help":
            buttons = [[InlineKeyboardButton('⬅️ Back', callback_data='start')]]
            await query.message.edit_text(
                text=script.HELP_TXT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # About
        elif query.data == "about":
            buttons = [[InlineKeyboardButton('⬅️ Back', callback_data='start')]]
            me = await client.get_me()
            await query.message.edit_text(
                text=script.ABOUT_TXT.format(bot=me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Clone Menu
        elif query.data == "clone":
            await show_clone_menu(client, query.message, user_id)

        # Add Clone
        elif query.data == "add_clone":
            WAITING_FOR_TOKEN[user_id] = query.message
            buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_clone")]]
            await query.message.edit_text(
                text=script.CLONE_TXT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Cancel Add Clone
        elif query.data == "cancel_add_clone":
            WAITING_FOR_TOKEN.pop(user_id, None)
            await show_clone_menu(client, query.message, user_id)

        # Clone Manage Menu
        elif query.data.startswith("manage_"):
            bot_id = query.data.split("_", 1)[1]
            clone = await db.get_clone_by_id(bot_id)
            buttons = [
                [InlineKeyboardButton('📝 Start Message', callback_data=f'start_message_{bot_id}'),
                 InlineKeyboardButton('🔔 Force Subscribe', callback_data=f'force_subscribe_{bot_id}')],
                [InlineKeyboardButton('🔑 Access Token', callback_data=f'access_token_{bot_id}'),
                 InlineKeyboardButton('💎 Premium User', callback_data=f'premium_user_{bot_id}')],
                [InlineKeyboardButton('⏳ Auto Delete', callback_data=f'auto_delete_{bot_id}'),
                 InlineKeyboardButton('🚫 Forward Protect', callback_data=f'forward_protect_{bot_id}')],
                [InlineKeyboardButton('🛡 Moderator', callback_data=f'moderator_{bot_id}'),
                 InlineKeyboardButton('📊 Status', callback_data=f'status_{bot_id}')],
                [InlineKeyboardButton('✅ Activate', callback_data=f'activate_deactivate_{bot_id}'),
                 InlineKeyboardButton('🔄 Restart', callback_data=f'restart_{bot_id}')],
                [InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_{bot_id}')],
                [InlineKeyboardButton('⬅️ Back', callback_data='clone')]
            ]
            await query.message.edit_text(
                text=script.CUSTOMIZEC_TXT.format(username=f"@{clone['username']}"),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Handle per-clone actions
        elif any(query.data.startswith(prefix) for prefix in [
            "start_message_", "start_text_", "edit_text_", "cancel_edit_", "see_text_", "default_text_", "start_photo_", "add_photo_", "cancel_add_", "see_photo_", "delete_photo_",
            "force_subscribe_", "access_token_", "premium_user_",
            "auto_delete_", "ad_status_", "ad_time_", "edit_adtime_", "cancel_editadtime_", "see_adtime_", "default_adtime_", "ad_message_", "edit_admessage_", "cancel_editadmessage_", "see_admessage_", "default_admessage_",
            "forward_protect_", "moderator_", "status_", "activate_deactivate_", "restart_", "delete_", "delete_clone_"
        ]):
            action, bot_id = query.data.rsplit("_", 1)
            clone = await db.get_clone_by_id(bot_id)

            # Start Message Menu
            if action == "start_message":
                buttons = [
                    [InlineKeyboardButton('✏️ Start Text', callback_data=f'start_text_{bot_id}'),
                     InlineKeyboardButton('🖼️ Start Photo', callback_data=f'start_photo_{bot_id}')],
                    [InlineKeyboardButton('🔺 Footer', callback_data=f'help_{bot_id}'),
                     InlineKeyboardButton('🔻 Header', callback_data=f'help_{bot_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(
                    text=script.ST_MSG_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Start Text Menu
            elif action == "start_text":
                await show_text_menu(query.message, bot_id)

            # Edit Text
            elif action == "edit_text":
                WAITING_FOR_WLC[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_edit_{bot_id}')]]
                await query.message.edit_text(
                    text=script.EDIT_TXT_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Edit Text
            elif action == "cancel_edit":
                WAITING_FOR_WLC.pop(user_id, None)
                await show_text_menu(query.message, bot_id)

            # See Start Text
            elif action == "see_text":
                start_text = clone.get("wlc", script.START_TXT)
                await query.answer(f"📝 Current Start Message:\n\n{start_text}", show_alert=True)

            # Default Start Text
            elif action == "default_text":
                await db.update_clone(bot_id, {"wlc": script.START_TXT})
                await query.answer(f"🔄 Start message reset to default.", show_alert=True)

            # Start Photo Menu
            elif action == "start_photo":
                await show_photo_menu(query.message, bot_id)

            # Add Photo
            elif action == "add_photo":
                WAITING_FOR_CLONE_PHOTO[user_id] = bot_id
                WAITING_FOR_CLONE_PHOTO_MSG[user_id] = query.message
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_add_{bot_id}')]]
                await query.message.edit_text(
                    text="Send your new start message photo.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Add Photo
            elif action == "cancel_add":
                WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
                WAITING_FOR_CLONE_PHOTO_MSG.pop(user_id, None)
                await show_photo_menu(query.message, bot_id)

            # See Start Phito
            elif action == "see_photo":
                start_photo = clone.get("pics", None)
                if start_photo:
                    await query.message.reply_photo(
                        photo=start_photo,
                        caption=f"🖼 Current Start Photo for @{clone.get('username')}"
                    )
                else:
                    await query.answer("❌ No start photo set for this clone.", show_alert=True)

            # Delete Photo
            elif action == "delete_photo":
                await db.update_clone(bot_id, {"pics": None})
                await query.answer("✨ Successfully deleted your clone start photo.", show_alert=True)

            # Force Subscribe
            elif action == "force_subscribe":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.FSUB_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Access Token
            elif action == "access_token":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.TOKEN_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Premium User
            elif action == "premium_user":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.PREMIUM_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Auto Delete Menu
            elif action == "auto_delete":
                current = clone.get("auto_delete", False)
                time_set = clone.get("auto_delete_time", 30)
                msg_set = clone.get("auto_delete_msg", script.AD_TXT)
                if current:
                    buttons = [
                        [InlineKeyboardButton("⏱ Time", callback_data=f"ad_time_{bot_id}")],
                        [InlineKeyboardButton("📝 Message", callback_data=f"ad_message_{bot_id}")],
                        [InlineKeyboardButton("❌ Disable", callback_data=f"ad_status_{bot_id}")]
                    ]
                    status = f"🟢 Enabled\n⏱ Time: {time_set} minutes\n📝 Msg: {clone.get('auto_delete_msg','')}"
                else:
                    buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"ad_status_{bot_id}")]]
                    status = "🔴 Disabled"

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")])
                await query.message.edit_text(
                    text=script.DELETE_TXT.format(status=f"{status}"), reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Status
            elif action == "ad_status":
                clone = await db.get_auto_delete(bot_id)
                new_value = not clone.get("auto_delete", False)
                await db.set_auto_delete(bot_id, new_value)
                await query.answer("✅ Auto Delete updated!", show_alert=True)

            # Time Menu
            elif action == "ad_time":
                await show_time_menu(query.message, bot_id)

            # Edit Message
            elif action == "edit_adtime":
                AUTO_DELETE_TIME[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editadtime_{bot_id}')]]
                await query.message.edit_text(
                    text="⏱ Send me new auto delete time in **minutes** (e.g. `60` for 1 hour).",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Message
            elif action == "cancel_editadtime":
                AUTO_DELETE_TIME.pop(user_id, None)
                await show_time_menu(query.message, bot_id)

            # See Message
            elif action == "see_adtime":
                ad_time = clone.get("auto_delete_time", 30)
                await query.answer(f"📝 Current Auto Delete Time:\n\n{ad_time}", show_alert=True)

            # Default Time
            elif action == "default_adtime":
                await db.update_clone(bot_id, {"auto_delete_time": 30})
                await query.answer(f"🔄 Auto delete message reset to default.", show_alert=True)

            # Message Menu
            elif action == "ad_message":
                await show_message_menu(query.message, bot_id)

            # Edit Message
            elif action == "edit_admessage":
                AUTO_DELETE_MESSAGE[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editadmessage_{bot_id}')]]
                await query.message.edit_text(
                    text="📝 Send me the new auto delete message.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Message
            elif action == "cancel_editadmessage":
                AUTO_DELETE_MESSAGE.pop(user_id, None)
                await show_message_menu(query.message, bot_id)

            # See Message
            elif action == "see_admessage":
                ad_message = clone.get("auto_delete_msg", script.AD_TXT)
                await query.answer(f"📝 Current Auto Delete Message:\n\n{ad_message}", show_alert=True)

            # Default Message
            elif action == "default_admessage":
                await db.update_clone(bot_id, {"auto_delete_msg": script.AD_TXT})
                await query.answer(f"🔄 Auto delete message reset to default.", show_alert=True)

            # Forward Protect
            elif action == "forward_protect":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.FORWARD_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Moderator Menu
            elif action == "moderator":
                buttons = [
                    [InlineKeyboardButton('➕ Add', callback_data=f'add_moderator_{bot_id}'),
                    InlineKeyboardButton('➖ Remove', callback_data=f'remove_moderator_{bot_id}'),
                    InlineKeyboardButton('🔁 Transfer', callback_data=f'transfer_moderator_{bot_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(
                    text=script.MODERATOR_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Status
            elif action == "status":
                users_count = clone.get("users_count", 0)
                storage_used = clone.get("storage_used", 0)
                storage_limit = clone.get("storage_limit", 536870912)
                storage_free = storage_limit - storage_used
                banned_users = len(clone.get("banned_users", []))

                uptime = str(timedelta(seconds=int(time.time() - START_TIME)))

                await query.answer(
                    f"📊 Status for @{clone.get('username')}\n\n"
                    f"👤 Users: {users_count}\n"
                    f"🚫 Banned: {banned_users}\n"
                    f"💾 Used: {get_size(storage_used)} / {get_size(storage_limit)}\n"
                    f"💽 Free: {get_size(storage_free)}\n"
                    f"⏱ Uptime: {uptime}\n",
                    show_alert=True
                )

            # Activate/Deactivate
            elif action == "activate_deactivate":
                await query.message.delete()

            # Restart
            elif action == "restart":
                await query.message.edit_text(f"🔄 Restarting clone bot `@{clone['username']}`...\n[░░░░░░░░░░] 0%")
                for i in range(1, 11):
                    await asyncio.sleep(0.5)
                    bar = '▓' * i + '░' * (10 - i)
                    await query.message.edit_text(f"🔄 Restarting clone bot `@{clone['username']}`...\n[{bar}] {i*10}%")
                await query.message.edit_text(f"✅ Clone bot `@{clone['username']}` restarted successfully!")
                await asyncio.sleep(2)
                await show_clone_menu(client, query.message, user_id)

            # Delete Menu
            elif action == "delete":
                buttons = [
                    [InlineKeyboardButton('✅ Yes, Sure', callback_data=f'delete_clone_{bot_id}')],
                    [InlineKeyboardButton('❌ No, Go Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(
                    text='⚠️ Are You Sure? Do you want delete your clone bot.',
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Delete Clone
            elif action == "delete_clone":
                bot_id = int(bot_id)
                await db.delete_clone(bot_id)
                await query.message.edit_text("✅ Clone deleted successfully.")
                await asyncio.sleep(2)
                await show_clone_menu(client, query.message, user_id)

        # Close
        elif query.data == "close":
            await query.message.delete()
            await query.message.reply_text("❌ Menu closed. Send /start again.")

        # Optional: Handle unknown callback
        else:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Unknown Callback Data Received:\n\n{query.data}\n\nUser: {query.from_user.id}\n\nKindly check this message for assistance."
            )
            await query.answer("⚠️ Unknown action.", show_alert=True)

    except Exception as e:
        # Send error to log channel
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Callback Handler Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        # Optionally notify user
        await query.answer("❌ An error occurred. The admin has been notified.", show_alert=True)

@Client.on_message(filters.text | filters.photo)
async def message_capture(client: Client, message: Message):
    user_id = message.from_user.id

    # Token Capture
    if user_id in WAITING_FOR_TOKEN:
        msg = WAITING_FOR_TOKEN[user_id]

        try:
            await message.delete()
        except:
            pass

        # Ensure forwarded from BotFather
        if not (message.forward_from and message.forward_from.id == 93372553):
            await msg.edit_text("❌ Please forward the BotFather message containing your bot token.")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
            WAITING_FOR_TOKEN.pop(user_id, None)
            return

        # Extract token
        try:
            token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", message.text or "")[0]
        except IndexError:
            await msg.edit_text("❌ Could not detect bot token. Please forward the correct BotFather message.")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
            WAITING_FOR_TOKEN.pop(user_id, None)
            return

        # Create bot
        await msg.edit_text("👨‍💻 Creating your bot, please wait...")
        try:
            xd = Client(
                f"{token}", API_ID, API_HASH,
                bot_token=token,
                plugins={"root": "clone_plugins"}
            )
            await xd.start()
            bot = await xd.get_me()
            await db.add_clone_bot(bot.id, user_id, bot.first_name, bot.username, token)

            await msg.edit_text(f"✅ Successfully cloned your bot: @{bot.username}")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
        except Exception as e:
            await client.send_message(LOG_CHANNEL, f"⚠️ Create Bot Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
            await msg.edit_text(f"❌ Failed to create bot: {e}")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
        finally:
            WAITING_FOR_TOKEN.pop(user_id, None)
        return

    # Start Text Handler
    if user_id in WAITING_FOR_WLC:
        orig_msg, bot_id = WAITING_FOR_WLC[user_id]

        try:
            await message.delete()
        except:
            pass

        new_text = message.text.strip() if message.text else ""
        if not new_text:
            await orig_msg.edit_text("❌ You sent an empty message. Please send a valid start text.")
            await asyncio.sleep(2)
            await show_text_menu(orig_msg, bot_id)
            WAITING_FOR_WLC.pop(user_id, None)
            return

        await orig_msg.edit_text("✏️ Updating your clone's start text, please wait...")
        try:
            await db.update_clone(bot_id, {"wlc": new_text})
            await orig_msg.edit_text("✅ Successfully updated start text!")
            await asyncio.sleep(1)
            await show_text_menu(orig_msg, bot_id)
        except Exception as e:
            await client.send_message(LOG_CHANNEL, f"⚠️ Update Start Text Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
            await orig_msg.edit_text(f"❌ Failed to update start text: {e}")
            await asyncio.sleep(2)
            await show_text_menu(orig_msg, bot_id)
        finally:
            WAITING_FOR_WLC.pop(user_id, None)
        return

    # Start Photo Handler
    if user_id in WAITING_FOR_CLONE_PHOTO:
        bot_id = WAITING_FOR_CLONE_PHOTO[user_id]
        orig_msg = WAITING_FOR_CLONE_PHOTO_MSG[user_id]

        try:
            await message.delete()
        except:
            pass

        if not message.photo:
            await orig_msg.edit_text("❌ Please send a valid photo for your clone.")
            await asyncio.sleep(2)
            await show_photo_menu(orig_msg, bot_id)
            WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
            WAITING_FOR_CLONE_PHOTO_MSG.pop(user_id, None)
            return

        await orig_msg.edit_text("📸 Updating your clone's photo, please wait...")
        try:
            os.makedirs("photos", exist_ok=True)  # ensure folder exists
            file_path = await message.download(f"photos/{bot_id}.jpg")
            await db.update_clone(bot_id, {"pics": file_path})
            await orig_msg.edit_text("✅ Successfully updated the start photo!")
            await asyncio.sleep(2)
            await show_photo_menu(orig_msg, bot_id)
        except Exception as e:
            await client.send_message(LOG_CHANNEL, f"⚠️ Update Photo Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
            await orig_msg.edit_text(f"❌ Failed to update start photo: {e}")
        finally:
            WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
            WAITING_FOR_CLONE_PHOTO_MSG.pop(user_id, None)
        return

    # Auto Delete Time Handler
    if user_id in AUTO_DELETE_TIME:
        orig_msg, bot_id = AUTO_DELETE_TIME[user_id]

        try:
            await message.delete()
        except:
            pass

        new_text = message.text.strip() if message.text else ""
        if not new_text:
            await orig_msg.edit_text("❌ You sent an empty message. Please send a valid start text.")
            await asyncio.sleep(2)
            await show_time_menu(orig_msg, bot_id)
            AUTO_DELETE_TIME.pop(user_id, None)
            return

        await orig_msg.edit_text("✏️ Updating your clone's auto delete time, please wait...")
        try:
            await db.update_clone(bot_id, {"auto_delete_time": new_text})
            await orig_msg.edit_text("✅ Successfully updated auto delete time!")
            await asyncio.sleep(1)
            await show_time_menu(orig_msg, bot_id)
        except Exception as e:
            await client.send_message(LOG_CHANNEL, f"⚠️ Update Auto Delete Time Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
            await orig_msg.edit_text(f"❌ Failed to update auto delete time: {e}")
            await asyncio.sleep(2)
            await show_time_menu(orig_msg, bot_id)
        finally:
            AUTO_DELETE_TIME.pop(user_id, None)
        return

    # Auto Delete Message Handler
    if user_id in AUTO_DELETE_MESSAGE:
        orig_msg, bot_id = AUTO_DELETE_MESSAGE[user_id]

        try:
            await message.delete()
        except:
            pass

        new_text = message.text.strip() if message.text else ""
        if not new_text:
            await orig_msg.edit_text("❌ You sent an empty message. Please send a valid start text.")
            await asyncio.sleep(2)
            await show_message_menu(orig_msg, bot_id)
            AUTO_DELETE_MESSAGE.pop(user_id, None)
            return

        await orig_msg.edit_text("✏️ Updating your clone's auto delete message, please wait...")
        try:
            await db.update_clone(bot_id, {"auto_delete_msg": new_text})
            await orig_msg.edit_text("✅ Successfully updated auto delete message!")
            await asyncio.sleep(1)
            await show_message_menu(orig_msg, bot_id)
        except Exception as e:
            await client.send_message(LOG_CHANNEL, f"⚠️ Update Auto Delete Message Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
            await orig_msg.edit_text(f"❌ Failed to update auto delete message: {e}")
            await asyncio.sleep(2)
            await show_message_menu(orig_msg, bot_id)
        finally:
            AUTO_DELETE_MESSAGE.pop(user_id, None)
        return

async def restart_bots():
    bots_cursor = await db.get_all_bots()
    bots = await bots_cursor.to_list(None)
    for bot in bots:
        bot_token = bot['token']
        try:
            xd = Client(
                f"{bot_token}", API_ID, API_HASH,
                bot_token=bot_token,
                plugins={"root": "clone_plugins"},
            )
            await xd.start()
        except Exception as e:
            print(f"Error while restarting bot with token {bot_token}: {e}")
