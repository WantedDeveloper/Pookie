import os
import logging
import random
import asyncio
from validators import domain
from Script import script
from plugins.dbusers import db
from pyrogram import Client, filters, enums
from plugins.users_api import get_user, update_user_info
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import *
from utils import verify_user, check_token, check_verification, get_token
from config import *
import re
import json
import base64
from urllib.parse import quote_plus
from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size

logger = logging.getLogger(__name__)

BATCH_FILES = {}

WAITING_FOR_TOKEN = {}
EDITING_WLC = {}
WAITING_FOR_CLONE_PHOTO = {}

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
    file_name = 'FuckYou ' + ' '.join(filter(lambda x: not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
    return file_name

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    await message.delete()
    try:
        username = client.me.username

        if not await db.is_user_exist(message.from_user.id):
            await db.add_user(message.from_user.id, message.from_user.first_name)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(message.from_user.id, message.from_user.mention))

        #await load_clone_settings(client.me.id)

        if len(message.command) != 2:
            buttons = [[
                InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                InlineKeyboardButton('😊 About', callback_data='about')
                ],[
                InlineKeyboardButton('🤖 Create Your Own Clone', callback_data='clone')
                ],[
                InlineKeyboardButton('🔒 Close', callback_data='close')
            ]]

            if PICS:
                return await message.reply_photo(
                    photo=PICS,
                    caption=script.START_TXT.format(message.from_user.mention, client.me.mention),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            await message.reply_text(
                script.START_TXT.format(message.from_user.mention, client.me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Bot Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

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

@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command

    if len(cmd) == 1:
        s = script.SHORTENER_API_MESSAGE.format(base_site=user["base_site"], shortener_api=user["shortener_api"])
        return await m.reply(s)

    elif len(cmd) == 2:    
        api = cmd[1].strip()
        await update_user_info(user_id, {"shortener_api": api})
        await m.reply("<b>Shortener API updated successfully to</b> " + api)

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command
    text = f"`/base_site (base_site)`\n\n<b>Current base site: None\n\n EX:</b> `/base_site shortnerdomain.com`\n\nIf You Want To Remove Base Site Then Copy This And Send To Bot - `/base_site None`"
    if len(cmd) == 1:
        return await m.reply(text=text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site = cmd[1].strip()
        if base_site == None:
            await update_user_info(user_id, {"base_site": base_site})
            return await m.reply("<b>Base Site updated successfully</b>")
            
        if not domain(base_site):
            return await m.reply(text=text, disable_web_page_preview=True)
        await update_user_info(user_id, {"base_site": base_site})
        await m.reply("<b>Base Site updated successfully</b>")

async def show_clone_menu(client, message, user_id):
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
        await client.send_message(LOG_CHANNEL, f"⚠️ Clone Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

async def show_message_menu(msg, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_text_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_text_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_text_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'start_message_{bot_id}')]
        ]
        await msg.edit_text(text=script.ST_TXT_TXT, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Message Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

async def show_photo_menu(msg, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('➕ Add', callback_data=f'add_photo_{bot_id}'),
            InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_photo_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'start_message_{bot_id}')]
        ]
        await msg.edit_text(text=script.ST_PIC_TXT, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Photo Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

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
                text=script.START_TXT.format(query.from_user.mention, me.mention),
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
                text=script.ABOUT_TXT.format(me.mention),
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
                text=script.CUSTOMIZEC_TXT.format(f"@{clone['username']}"),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Handle per-clone actions
        elif any(query.data.startswith(prefix) for prefix in [
            "start_message_", "start_text_", "edit_text_", "cancel_edit_", "see_text_", "default_text_", "start_photo_", "add_photo_", "cancel_add_", "delete_photo_", "force_subscribe_", "access_token_", "premium_user_",
            "auto_delete_", "forward_protect_", "moderator_", "status_",
            "activate_deactivate_", "restart_", "delete_", "delete_clone_"
        ]):
            action, bot_id = query.data.rsplit("_", 1)

            # Start Message Menu
            if action == "start_message":
                buttons = [
                    [InlineKeyboardButton('✏️ Start Text', callback_data=f'start_text_{bot_id}'),
                     InlineKeyboardButton('🖼️ Start Photo', callback_data=f'start_photo_{bot_id}')],
                    [InlineKeyboardButton('🔺 Footer', callback_data=f'help_{bot_id}'),
                     InlineKeyboardButton('🔻 Header', callback_data=f'help_{bot_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(text=script.ST_MSG_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Start Text
            elif action == "start_text":
                await show_message_menu(query.message, bot_id)

            # Edit Text
            elif action == "edit_text":
                #asyncio.create_task(wait_for_clone_message(user_id, bot_id, query.message))
                EDITING_WLC[user_id] = {
                    "bot_id": bot_id,
                    "message": query.message  # store the message object to reply later
                }
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_edit_{bot_id}')]]
                await query.message.edit_text(text=script.EDIT_TXT_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Cancel Edit Text
            elif action == "cancel_edit":
                if user_id in EDITING_WLC:
                    EDITING_WLC.pop(user_id)
                await show_message_menu(query.message, bot_id)

            # See Start Text
            elif action == "see_text":
                clone = await db.get_clone_by_id(bot_id)
                start_text = clone.get("wlc", "No text set for this clone.")
                await query.answer(f"📝 Current Start Message:\n\n{start_text}", show_alert=True)

            # Default Start Text
            elif action == "default_text":
                default_text = script.START_TXT
                await db.update_clone(bot_id, {"wlc": default_text})
                await query.answer(f"🔄 Start message reset to default:\n\n{default_text}", show_alert=True)

            # Start Photo Menu
            elif action == "start_photo":
                await show_photo_menu(query.message, bot_id)

            # Add Photo
            elif action == "add_photo":
                #asyncio.create_task(wait_for_clone_photo(user_id, bot_id, query.message))
                WAITING_FOR_CLONE_PHOTO[user_id] = bot_id
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_add_{bot_id}')]]
                await query.message.edit_text(text=script.ADD_PIC_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Cancel Add Photo
            elif action == "cancel_add":
                WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
                await show_photo_menu(query.message, bot_id)

            # Delete Photo
            elif action == "delete_photo":
                await db.update_clone(bot_id, {"pics": None})
                await query.answer("✨ Successfully deleted your clone start photo.", show_alert=True)

            # Force Subscribe
            elif action == "force_subscribe":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(text=script.FSUB_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Access Token
            elif action == "access_token":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(text=script.TOKEN_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Premium User
            elif action == "premium_user":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(text=script.PREMIUM_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Auto Delete
            elif action == "auto_delete":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(text=script.DELETE_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Forward Protect
            elif action == "forward_protect":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(text=script.FORWARD_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Moderator Menu
            elif action == "moderator":
                buttons = [
                    [InlineKeyboardButton('➕ Add', callback_data=f'add_moderator_{bot_id}'),
                    InlineKeyboardButton('➖ Remove', callback_data=f'remove_moderator_{bot_id}'),
                    InlineKeyboardButton('🔁 Transfer', callback_data=f'transfer_moderator_{bot_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(text=script.MODERATOR_TXT, reply_markup=InlineKeyboardMarkup(buttons))

            # Status
            elif action == "status":
                clone = await db.get_clone_by_id(bot_id)
                users_count = clone.get("users_count", 0)
                storage_used = clone.get("storage_used", 0)
                storage_limit = clone.get("storage_limit", 536870912)
                storage_free = storage_limit - storage_used

                await query.answer(
                    f"📊 Status for @{clone.get('username')}\n\n"
                    f"👤 Users: {users_count}\n"
                    f"💾 Used: {get_size(storage_used)}\n"
                    f"💽 Free: {get_size(storage_free)}",
                    show_alert=True
                )

            # Activate/Deactivate
            elif action == "activate_deactivate":
                await query.message.delete()

            # Restart
            elif action == "restart":
                clone = await db.get_clone_by_id(bot_id)
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
                await query.message.edit_text(text='⚠️ Are You Sure? Do you want delete your clone bot.', reply_markup=InlineKeyboardMarkup(buttons))

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
                f"⚠️ Unknown callback data received:\n\n{query.data}\n\nUser: {query.from_user.id}\n\nKindly check this message for assistance."
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

@Client.on_message()
async def token_handler(client, message):
    user_id = message.from_user.id

    # check if user is in waiting mode
    if user_id not in WAITING_FOR_TOKEN:
        return  

    msg = WAITING_FOR_TOKEN[user_id]

    # 🗑 delete user message to keep chat clean
    try:
        await message.delete()
    except:
        pass

    # ✅ ensure it is forwarded from BotFather
    if not (message.forward_from and message.forward_from.id == 93372553):
        await msg.edit_text("❌ Please forward the BotFather message containing your bot token.")
        await asyncio.sleep(2)
        await show_clone_menu(client, msg, user_id)
        WAITING_FOR_TOKEN.pop(user_id, None)
        return

    # ✅ extract token
    try:
        token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", message.text or "")[0]
    except IndexError:
        await msg.edit_text("❌ Could not detect bot token. Please forward the correct BotFather message.")
        await asyncio.sleep(2)
        await show_clone_menu(client, msg, user_id)
        WAITING_FOR_TOKEN.pop(user_id, None)
        return

    # ✅ proceed with bot creation
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
        await xd.stop()

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

@Client.on_message(filters.text & filters.user(ADMINS))
async def capture_wlc_text(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id in EDITING_WLC:
        data = EDITING_WLC.pop(user_id)
        bot_id = data["bot_id"]
        orig_msg = data["message"]

        wlc_text = message.text

        # Update in DB
        await db.update_clone(bot_id, {"wlc": wlc_text})

        # Delete user message to keep chat clean
        try:
            await message.delete()
        except:
            pass

        # Show updated message menu using the stored message object
        await show_message_menu(orig_msg, bot_id)

@Client.on_message(filters.photo & filters.user(ADMINS))
async def capture_photo(client: Client, message: Message):
    try:
        user_id = message.from_user.id

        # Check if user is currently sending start photo for a clone
        if user_id in WAITING_FOR_CLONE_PHOTO:
            bot_id = WAITING_FOR_CLONE_PHOTO.pop(user_id)  # Get the clone ID
            photo_file_id = message.photo.file_id
            await db.update_clone(bot_id, {"pics": photo_file_id})

            await message.delete()
            await show_photo_menu(message, bot_id)

    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Capture Photo Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")

async def wait_for_clone_photo(user_id, bot_id, message):
    try:
        WAITING_FOR_CLONE_PHOTO[user_id] = bot_id
        await asyncio.sleep(120)
        if user_id in WAITING_FOR_CLONE_PHOTO and WAITING_FOR_CLONE_PHOTO[user_id] == bot_id:
            WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
            await show_photo_menu(message, bot_id)
    except Exception as e:
        await message.client.send_message(LOG_CHANNEL, f"⚠️ Capture Message Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
