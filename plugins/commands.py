import re
import os
import json
import base64
import asyncio
import datetime
import time
import requests
import json
from pyrogram import filters, Client, enums
from pyrogram.types import Message
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from pyromod import listen
from config import ADMINS, LOG_CHANNEL
from plugins.dbusers import db

async def get_short_link(user, link):
    api_key = user["shortener_api"]
    base_site = user["base_site"]
    print(user)
    response = requests.get(f"https://{base_site}/api?api={api_key}&url={link}")
    data = response.json()
    if data["status"] == "success" or rget.status_code == 200:
        return data["shortenedUrl"]

@Client.on_message(filters.command(['genlink']) & filters.user(ADMINS))
async def gen_link_s(bot, message):
    try:
        username = (await bot.get_me()).username

        # Ask user to send a message
        g_msg = await bot.ask(
            message.chat.id,
            "📩 Please send me the message (file/text/media) to generate a shareable link.\n\nSend /cancel to stop.",
            timeout=60   # 1 min timeout
        )

        # Cancel case
        if g_msg.text and g_msg.text.lower() == '/cancel':
            return await g_msg.reply("<b>🚫 Process has been canceled.</b>")

        # Copy received message to log channel
        post = await g_msg.copy(LOG_CHANNEL)

        # Generate file ID + encoded string
        file_id = str(post.id)
        string = f"file_{file_id}"
        outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")

        user_id = message.from_user.id
        user = await db.get_user(user_id)

        # Generate share link
        share_link = f"https://t.me/{username}?start={outstr}"

        # Shorten if possible
        if user.get("base_site") and user.get("shortener_api") is not None:
            short_link = await get_short_link(user, share_link)
            await g_msg.reply(
                f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\n🖇️ Short Link :- {short_link}</b>"
            )
        else:
            await g_msg.reply(
                f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\n🔗 Original Link :- {share_link}</b>"
            )

    except Exception as e:
        await message.reply(f"⚠️ Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")

