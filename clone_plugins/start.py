import os
import logging
import random
import asyncio
from Script import script
from validators import domain
from clone_plugins.dbusers import clonedb
from pyrogram import Client, filters, enums
from plugins.dbusers import db
from pyrogram.errors import ChatAdminRequired, FloodWait
from config import *
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery, InputMediaPhoto
import re
import json
import base64

logger = logging.getLogger(__name__)

def get_size(size):
    """Get size in readable format"""

    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    await message.delete()
    try:
        me = await client.get_me()

        # Check banned users
        banned = await db.get_banned_users(me.id)
        if message.from_user.id in banned:
            return await message.reply_text("🚫 You are banned from using this bot.")

        # Track new users
        if not await clonedb.is_user_exist(me.id, message.from_user.id):
            await clonedb.add_user(me.id, message.from_user.id)
            await db.increment_users_count(me.id)

        if len(message.command) != 2:
            buttons = [[
                InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                InlineKeyboardButton('😊 About', callback_data='about')
                ],[
                InlineKeyboardButton('🤖 Create Your Own Clone', url=f'https://t.me/{BOT_USERNAME}?start=clone')
                ],[
                InlineKeyboardButton('🔒 Close', callback_data='close')
            ]]

            clone = await db.get_bot(me.id)
            start_text = clone.get("wlc")
            start_pic = clone.get("pics")

            if start_pic:
                return await message.reply_photo(
                    photo=start_pic,
                    caption=start_text.format(user=message.from_user.mention, bot=client.me.mention),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            await message.reply_text(
                start_text.format(user=message.from_user.mention, bot=client.me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Clone Start Bot Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")

    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""   

    pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
    try:
        msg = await client.send_cached_media(
            chat_id=message.from_user.id,
            file_id=file_id,
            protect_content=True if pre == 'filep' else False,
        )
        filetype = msg.media
        file = getattr(msg, filetype.value)
        title = '@PookieManagerBot  ' + ' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@'), file.file_name.split()))
        size=get_size(file.file_size)
        await db.add_storage_used(me.id, file.file_size)
        f_caption = f"<code>{title}</code>"
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption=CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='')
            except:
                return
        await msg.edit_caption(f_caption)
        k = await msg.reply(f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{AUTO_DELETE} mins</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</i></b>",quote=True)
        await asyncio.sleep(AUTO_DELETE_TIME)
        await msg.delete()
        await k.edit_text("<b>Your File/Video is successfully deleted!!!</b>")
        return
    except:
        pass

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    try:
        me = await client.get_me()

        # Start Menu
        if query.data == "start":
            buttons = [
                [InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                 InlineKeyboardButton('ℹ️ About', callback_data='about')],
                [InlineKeyboardButton('🤖 Create Your Own Clone', url=f'https://t.me/{BOT_USERNAME}?start=clone')],
                [InlineKeyboardButton('🔒 Close', callback_data='close')]
            ]
            clone = await db.get_bot(me.id)
            start_text = clone.get("wlc")
            await query.message.edit_text(
                text=start_text.format(user=query.from_user.mention, bot=me.mention),
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
            owner = await db.get_bot(me.id)
            ownerid = int(owner['user_id'])
            await query.message.edit_text(
                text=script.CABOUT_TXT.format(bot=me.mention, developer=ownerid),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Close
        elif query.data == "close":
            await query.message.delete()
            await query.message.reply_text("❌ Menu closed. Send /start again.")

        # Optional: Handle unknown callback
        else:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Clone Unknown Callback Data Received:\n\n{query.data}\n\nUser: {query.from_user.id}\n\nKindly check this message for assistance."
            )
            await query.answer("⚠️ Unknown action.", show_alert=True)

    except Exception as e:
        # Send error to log channel
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Callback Handler Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        # Optionally notify user
        await query.answer("❌ An error occurred. The admin has been notified.", show_alert=True)
