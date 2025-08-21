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

@Client.on_message(filters.command(['genlink']) & filters.user(OWNERS) & filters.private)
async def link(bot, message):
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
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        await query.answer("❌ An error occurred. The admin has been notified.", show_alert=True)

@Client.on_message(filters.command(['batch']) & filters.user(OWNERS) & filters.private)
async def batch(bot, message):
    try:
        username = (await bot.get_me()).username
        
        if " " not in message.text:
            return await message.reply("Use correct format.\nExample /batch https://t.me/example/10 https://t.me/example/20.")
        
        links = message.text.strip().split(" ")
        if len(links) != 3:
            return await message.reply("Use correct format.\nExample /batch https://t.me/example/10 https://t.me/example/20.")
        
        cmd, first, last = links
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        
        match = regex.match(first)
        if not match:
            return await message.reply('Invalid link')
        f_chat_id = match.group(4)
        f_msg_id = int(match.group(5))
        if f_chat_id.isnumeric():
            f_chat_id = int("-100" + f_chat_id)

        match = regex.match(last)
        if not match:
            return await message.reply('Invalid link')
        l_chat_id = match.group(4)
        l_msg_id = int(match.group(5))
        if l_chat_id.isnumeric():
            l_chat_id = int("-100" + l_chat_id)

        if f_chat_id != l_chat_id:
            return await message.reply("Chat ids not matched.")
        
        chat_id = (await bot.get_chat(f_chat_id)).id

        sts = await message.reply("Generating link for your message .\nThis may take time depending upon number of messages.")
        FRMT = "Generating Link...**\nTotal Messages: {total}\nDone: {current}\nRemaining: {rem}\nStatus: {sts}"

        outlist = []
        og_msg = 0
        tot = 0

        async for msg in bot.iter_messages(f_chat_id, l_msg_id, f_msg_id):
            tot += 1
            if og_msg % 20 == 0:
                try:
                    await sts.edit(FRMT.format(total=l_msg_id-f_msg_id, current=tot, rem=((l_msg_id-f_msg_id) - tot), sts="Saving Messages"))
                except:
                    pass
            if msg.empty or msg.service:
                continue
            file = {
                "channel_id": f_chat_id,
                "msg_id": msg.id
            }
            og_msg += 1
            outlist.append(file)

        filename = f"batchmode_{message.from_user.id}.json"
        with open(filename, "w+") as out:
            json.dump(outlist, out)
        
        post = await bot.send_document(LOG_CHANNEL, filename, file_name="Batch.json", caption="⚠️ Batch Generated For Filestore.")
        os.remove(filename)
        string = str(post.id)
        file_id = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
        
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        share_link = f"https://t.me/{username}?start=BATCH-{file_id}"

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔁 Share URL", url=f'https://t.me/share/url?url={share_link}')]]
        )

        if user["base_site"] and user["shortener_api"] is not None:
            short_link = await get_short_link(user, share_link)
            await sts.edit(f"Contains `{og_msg}` files.\n\nHere is your link:\n\n{short_link}", reply_markup=reply_markup)
        else:
            await sts.edit(f"Contains `{og_msg}` files.\n\nHere is your link:\n\n{share_link}", reply_markup=reply_markup)

    except ChannelInvalid:
        await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        await message.reply('Invalid Link specified.')
    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Batch Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        await query.answer("❌ An error occurred. The admin has been notified.", show_alert=True)

@Client.on_message(filters.command('header') & filters.private)
async def header_handler(bot, m: Message):
    user_id = m.from_user.id
    cmd = m.command
    user = await get_user(user_id)
    if m.reply_to_message:
        header_text = m.reply_to_message.text.html
        await update_user_info(user_id, {"header_text": header_text})
        await m.reply("Header Text Updated Successfully")
    elif "remove" in cmd:
        await update_user_info(user_id, {"header_text": ""})
        return await m.reply("Header Text Successfully Removed")
    else:
        return await m.reply(HEADER_MESSAGE + "\n\nCurrent Header Text: " + user["header_text"].replace("\n", "\n"))

@Client.on_message(filters.command('footer') & filters.private)
async def footer_handler(bot, m: Message):
    user_id = m.from_user.id
    cmd = m.command
    user = await get_user(user_id)
    if not m.reply_to_message:
        if "remove" not in cmd:
            return await m.reply(FOOTER_MESSAGE + "\n\nCurrent Footer Text: " + user["footer_text"].replace("\n", "\n"))

        await update_user_info(user_id, {"footer_text": ""})
        return await m.reply("Footer Text Successfully Removed")
    elif m.reply_to_message.text:
        footer_text = m.reply_to_message.text.html
        await update_user_info(user_id, {"footer_text": footer_text})
        await m.reply("Footer Text Updated Successfully")