import re
from pyrogram import filters, Client, enums
from clone_plugins.dbusers import clonedb
from config import ADMINS, LOG_CHANNEL
import base64

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

        # 🔽 Get target message
        if message.reply_to_message:
            g_msg = message.reply_to_message
        else:
            try:
                g_msg = await bot.ask(
                    message.chat.id,
                    "📩 Please send me the message (file/text/media) to generate a shareable link.\n\nSend /cancel to stop.",
                    timeout=60
                )
                g_msg = g_msg  # ensure it's a Message object
            except asyncio.TimeoutError:
                return await message.reply("<b>⏰ Timeout! You didn’t send any message in 60s.</b>")

            if g_msg.text and g_msg.text.lower() == '/cancel':
                return await message.reply('<b>🚫 Process has been cancelled.</b>')

        # 🔽 Copy message to log channel
        post = await g_msg.copy(LOG_CHANNEL)

        # 🔽 Use copied message ID for link
        file_id = str(post.id)

        # 🔽 Encode to base64
        string = f"file_{file_id}"
        outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")

        # 🔽 Get user info from DB
        user_id = message.from_user.id
        user = await clonedb.get_user(user_id)

        # 🔽 Generate share link
        share_link = f"https://t.me/{username}?start={outstr}"

        # 🔽 Shorten link if API exists
        if user.get("base_site") and user.get("shortener_api"):
            short_link = await get_short_link(user, share_link)
            await g_msg.reply(f"⭕ Here is your link:\n\n{short_link}")
        else:
            await g_msg.reply(f"⭕ Here is your link:\n\n{share_link}")

    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Generate Link Error:\n\n<code>{e}</code>\n\nPlease check this message for assistance."
        )
