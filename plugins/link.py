import re
from pyrogram import filters, Client, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from plugins.dbusers import db
from config import OWNERS, LOG_CHANNEL
import os
import asyncio
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
        await db.update_user_info(user_id, {"shortener_api": api})
        await m.reply("<b>Shortener API updated successfully to</b> " + api)

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    user = await db.get_user(user_id)
    cmd = m.command
    text = f"`/base_site (base_site)`\n\n<b>Current base site: None\n\n EX:</b> `/base_site shortnerdomain.com`\n\nIf You Want To Remove Base Site Then Copy This And Send To Bot - `/base_site None`"
    if len(cmd) == 1:
        return await m.reply(text=text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site = cmd[1].strip()
        if base_site == None:
            await db.update_user_info(user_id, {"base_site": base_site})
            return await m.reply("<b>Base Site updated successfully</b>")
            
        if not domain(base_site):
            return await m.reply(text=text, disable_web_page_preview=True)
        await db.update_user_info(user_id, {"base_site": base_site})
        await m.reply("<b>Base Site updated successfully</b>")

@Client.on_message(filters.command(['genlink']) & filters.user(OWNERS))
async def gen_link_s(bot, message):
    try:
        username = (await bot.get_me()).username

        # 🔽 Support reply-to-message
        if message.reply_to_message:
            g_msg = message.reply_to_message
        else:
            try:
                g_msg = await bot.ask(
                    message.chat.id,
                    "📩 Please send me the message (file/text/media) to generate a shareable link.\n\nSend /cancel to stop.",
                    timeout=60
                )
            except asyncio.TimeoutError:
                return await message.reply("<b>⏰ Timeout! You didn’t send any message in 60s.</b>")

            if g_msg.text and g_msg.text.lower() == '/cancel':
                return await message.reply('<b>🚫 Process has been cancelled.</b>')

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

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔁 Share URL", url=f'https://t.me/share/url?url={share_link}')]]
        )

        # Shorten if possible
        if user.get("base_site") and user.get("shortener_api") is not None:
            short_link = await get_short_link(user, share_link)
            await g_msg.reply(
                f"Here is your link:\n\n{short_link}",
                reply_markup=reply_markup
            )
        else:
            await g_msg.reply(
                f"Here is your link:\n\n{share_link}",
                reply_markup=reply_markup
            )

    except Exception as e:
        await bot.send_message(LOG_CHANNEL, f"⚠️ Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")

@Client.on_message(filters.command(['batch']) & filters.user(OWNERS))
async def gen_link_batch(bot, message):
    username = (await bot.get_me()).username
    parts = message.text.strip().split()

    if len(parts) != 3:
        return await message.reply("❌ Correct format:\n`/batch <first_link> <last_link>`")

    _, first, last = parts
    regex = re.compile(r"(https://)?(t\.me|telegram\.me|telegram\.dog)/(c/)?(\d+|[a-zA-Z0-9_]+)/(\d+)$")

    # ---- Parse first link ----
    match = regex.match(first)
    if not match:
        return await message.reply("❌ Invalid first link")
    f_chat_id, f_msg_id = match.group(4), int(match.group(5))
    if f_chat_id.isnumeric():
        f_chat_id = int("-100" + f_chat_id)

    # ---- Parse last link ----
    match = regex.match(last)
    if not match:
        return await message.reply("❌ Invalid last link")
    l_chat_id, l_msg_id = match.group(4), int(match.group(5))
    if l_chat_id.isnumeric():
        l_chat_id = int("-100" + l_chat_id)

    # ---- Check same chat ----
    if f_chat_id != l_chat_id:
        return await message.reply("❌ Both messages must be from the same channel.")

    try:
        chat_id = (await bot.get_chat(f_chat_id)).id
    except Exception as e:
        return await message.reply(f"⚠️ Error: {e}")

    # ---- Collect messages ----
    total = abs(l_msg_id - f_msg_id) + 1
    start_id, end_id = min(f_msg_id, l_msg_id), max(f_msg_id, l_msg_id)

    sts = await message.reply(f"📦 Collecting {total} messages...")

    collected, outlist = 0, []
    async for msg in bot.iter_messages(chat_id, offset_id=start_id-1, reverse=True):
        if msg.id > end_id:
            break
        if msg.empty or msg.service:
            continue
        collected += 1
        outlist.append({"channel_id": chat_id, "msg_id": msg.id})

        if collected % 20 == 0 or collected == total:
            try:
                await sts.edit(
                    f"📦 Collecting messages...\n"
                    f"✅ Done: {collected}/{total}\n"
                    f"⏳ Remaining: {total - collected}"
                )
            except: pass

    # ---- Save JSON ----
    filepath = f"batch_{message.from_user.id}.json"
    with open(filepath, "w") as out:
        json.dump(outlist, out)

    post = await bot.send_document(
        LOG_CHANNEL,
        filepath,
        file_name="Batch.json",
        caption="⚠️ Batch Generated For Filestore"
    )
    os.remove(filepath)

    file_id = base64.urlsafe_b64encode(str(post.id).encode()).decode().strip("=")
    share_link = f"https://t.me/{username}?start=BATCH-{file_id}"

    user = await db.get_user(message.from_user.id)
    if user.get("base_site") and user.get("shortener_api"):
        share_link = await get_short_link(user, share_link)

    await sts.edit(f"✅ Here is your batch link:\n\nContains `{collected}` messages.\n\n{share_link}")
