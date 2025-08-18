import re
from pyrogram import filters, Client, enums
from pyrogram.types import Message
from plugins.dbusers import db
from config import ADMINS, LOG_CHANNEL
import base64
import requests
import json

async def get_short_link(user, link):
    api_key = user["shortener_api"]
    base_site = user["base_site"]
    print(user)
    response = requests.get(f"https://{base_site}/api?api={api_key}&url={link}")
    data = response.json()
    if data["status"] == "success" or rget.status_code == 200:
        return data["shortenedUrl"]

@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    user_id = m.from_user.id
    user = await db.get_user(user_id)
    cmd = m.command

    if len(cmd) == 1:
        s = script.SHORTENER_API_MESSAGE.format(base_site=user["base_site"], shortener_api=user["shortener_api"])
        return await m.reply(s)

    elif len(cmd) == 2:    
        api = cmd[1].strip()
        await update_user_info(user_id, {"shortener_api": api})
        await m.reply("Shortener API updated successfully to " + api)
    else:
        await m.reply("You are not authorized to use this command.")

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    user = await db.get_user(user_id)
    cmd = m.command
    text = f"/base_site (base_site)\n\nCurrent base site: None\n\n EX: /base_site shortnerdomain.com\n\nIf You Want To Remove Base Site Then Copy This And Send To Bot - `/base_site None`"
    
    if len(cmd) == 1:
        return await m.reply(text=text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site = cmd[1].strip()
        if not domain(base_site):
            return await m.reply(text=text, disable_web_page_preview=True)
        await update_user_info(user_id, {"base_site": base_site})
        await m.reply("Base Site updated successfully")
    else:
        await m.reply("You are not authorized to use this command.")

@Client.on_message(filters.command(['genlink']) & filters.user(ADMINS))
async def gen_link_s(bot, message):
    try:
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
        bot_username = (await client.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={outstr}"

        # Shorten if possible
        if user.get("base_site") and user.get("shortener_api") is not None:
            short_link = await get_short_link(user, share_link)
            await g_msg.reply(
                f"Here is your link:\n\n{short_link}"
            )
        else:
            await g_msg.reply(
                f"Here is your link:\n\n{share_link}"
            )

    except Exception as e:
        await bot.send_message(LOG_CHANNEL, f"⚠️ Clone Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
        
