import re
import base64
from pyrogram import filters, Client, enums
from pyrogram.types import Message
from clone_plugins.users_api import get_user, get_short_link

# ================= Helper Functions =================

async def update_user_info(user_id: int, data: dict):
    # Implement your DB update logic here
    pass

def is_valid_domain(domain: str) -> bool:
    # Simple domain validation
    pattern = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
    if domain.lower() == "none":
        return True
    return re.match(pattern, domain) is not None

async def reply_text(m: Message, text: str):
    return await m.reply(text=text, disable_web_page_preview=True)

# ================= Command Handlers =================

@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command

    if len(cmd) == 1:
        s = script.SHORTENER_API_MESSAGE.format(
            base_site=user.get("base_site", "None"),
            shortener_api=user.get("shortener_api", "Not Set")
        )
        return await reply_text(m, s)

    elif len(cmd) == 2:    
        api = cmd[1].strip()
        await update_user_info(user_id, {"shortener_api": api})
        await reply_text(m, f"Shortener API updated successfully to: {api}")
    else:
        await reply_text(m, "You are not authorized to use this command.")

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command
    text = (
        "/base_site (base_site)\n\n"
        f"Current base site: {user.get('base_site', 'None')}\n\n"
        "EX: /base_site shortnerdomain.com\n"
        "To remove base site: `/base_site None`"
    )
    
    if len(cmd) == 1:
        return await reply_text(m, text)
    
    elif len(cmd) == 2:
        base_site = cmd[1].strip()
        if not is_valid_domain(base_site):
            return await reply_text(m, text)
        await update_user_info(user_id, {"base_site": base_site})
        await reply_text(m, f"Base Site updated successfully to: {base_site}")
    
    else:
        await reply_text(m, "You are not authorized to use this command.")

@Client.on_message(filters.command(['genlink']))
async def gen_link_s(client: Client, message: Message):
    replied = message.reply_to_message
    if not replied:
        return await reply_text(message, "Reply to a message to get a shareable link.")
    
    file_type = replied.media
    if not file_type or file_type not in [
        enums.MessageMediaType.VIDEO,
        enums.MessageMediaType.AUDIO,
        enums.MessageMediaType.DOCUMENT
    ]:
        return await reply_text(message, "Reply to a supported media type (video, audio, document).")

    file_id = getattr(replied, file_type.value).file_id
    encoded = base64.urlsafe_b64encode(f"file_{file_id}".encode()).decode().rstrip("=")

    user_id = message.from_user.id
    user = await get_user(user_id)  # replaced clonedb.get_user for consistency
    bot_username = (await client.get_me()).username
    share_link = f"https://t.me/{bot_username}?start={encoded}"

    if user.get("shortener_api"):
        # Use user's shortener API if set
        await reply_text(message, f"<b>⭕ Here is your link:\n\n🔗 Original link: {share_link}</b>")
    else:
        # Fallback to bot's shortener
        short_link = await get_short_link(user, share_link)
        await reply_text(message, f"<b>⭕ Here is your link:\n\n🖇️ Short link: {short_link}</b>")
