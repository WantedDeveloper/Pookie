import os, logging, asyncio, re, json, base64, random, aiohttp, requests, string, time, datetime, motor.motor_asyncio
from shortzy import Shortzy
from validators import domain
from pyrogram import Client, filters, enums
from pyrogram.types import *
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from pyrogram.file_id import FileId
from struct import pack
from plugins.config import *
from plugins.database import db
from plugins.clone_instance import get_client
from plugins.script import script

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]

    async def add_user(self, bot_id, user_id):
        user = {'user_id': int(user_id)}
        await self.db[str(bot_id)].insert_one(user)
    
    async def is_user_exist(self, bot_id, id):
        user = await self.db[str(bot_id)].find_one({'user_id': int(id)})
        return bool(user)
    
    async def total_users_count(self, bot_id):
        count = await self.db[str(bot_id)].count_documents({})
        return count

    async def get_all_users(self, bot_id):
        return self.db[str(bot_id)].find({})

    async def delete_user(self, bot_id, user_id):
        await self.db[str(bot_id)].delete_many({'user_id': int(user_id)})

    async def get_user(self, user_id):
        user_id = int(user_id)
        user = await self.db.users.find_one({"user_id": user_id})
        if not user:
            res = {
                "user_id": user_id,
                "shortener_api": None,
                "base_site": None,
            }
            await self.db.users.insert_one(res)
            user = await self.db.users.find_one({"user_id": user_id})
        return user

    async def update_user_info(self, user_id, value:dict):
        user_id = int(user_id)
        myquery = {"user_id": user_id}
        newvalues = { "$set": value }
        await self.db.users.update_one(myquery, newvalues)

clonedb = Database(CLONE_DB_URI, CDB_NAME)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CLONE_ME = {}
TOKENS = {}
VERIFIED = {}
BATCH_FILES = {}
SHORTEN_STATE = {}

async def is_subscribed(client, user_id: int, bot_id: int):
    clone = await db.get_bot(bot_id)
    if not clone:
        return True
    
    fsub_data = clone.get("force_subscribe", [])
    if not fsub_data:
        return True

    for item in fsub_data:
        channel_id = int(item["channel"])
        mode = item.get("mode", "normal")

        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status == enums.ChatMemberStatus.BANNED:
                return False
        except UserNotParticipant:
            return False
        except Exception as e:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Clone is_subscribed Error:\n\n<code>{channel_id}: {e}</code>"
            )
            print(f"⚠️ Clone is_subscribed Error: {channel_id}: {e}")
            return False

    return True

async def get_verify_shorted_link(client, link):
    me = await client.get_me()
    clone = await db.get_bot(me.id)
    if SHORTLINK_URL == clone.get("shorten_link", None):
        url = f'https://{SHORTLINK_URL}/easy_api'
        params = {
            "key": clone.get("shorten_api", None),
            "link": link,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, raise_for_status=True, ssl=False) as response:
                    data = await response.text()
                    return data
        except Exception as e:
            print(f"⚠️ Error: {e}")
            return link
    else:
        #response = requests.get(f"https://{SHORTLINK_URL}/api?api={SHORTLINK_API}&url={link}")
        #data = response.json()
        #if data["status"] == "success" or rget.status_code == 200:
            #return data["shortenedUrl"]
        shortzy = Shortzy(api_key=clone.get("shorten_api", None), base_site=clone.get("shorten_link", None))
        link = await shortzy.convert(link)
        return link

async def check_token(client, userid, token):
    user = await client.get_users(userid)
    if user.id in TOKENS.keys():
        TKN = TOKENS[user.id]
        if token in TKN.keys():
            is_used = TKN[token]
            if is_used == True:
                return False
            else:
                return True
    else:
        return False

async def get_token(client, userid, link):
    user = await client.get_users(userid)
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    TOKENS[user.id] = {token: False}
    link = f"{link}VERIFY-{user.id}-{token}"
    shortened_verify_url = await get_verify_shorted_link(client, link)
    return str(shortened_verify_url)

async def verify_user(client, userid, token):
    user = await client.get_users(userid)
    TOKENS[user.id] = {token: True}

    clone = await db.get_bot((await client.get_me()).id)
    validity_hours = clone.get("access_token_validity", 24)

    VERIFIED[user.id] = datetime.datetime.now() + datetime.timedelta(hours=validity_hours)

async def check_verification(client, userid):
    user = await client.get_users(userid)
    expiry = VERIFIED.get(user.id, None)

    if not expiry:
        return False

    if datetime.datetime.now() > expiry:
        del VERIFIED[user.id]
        return False

    return True

def get_size(size):
    """Get size in readable format"""

    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

async def auto_delete_message(client, msg_to_delete, notice_msg, hours):
    try:
        await asyncio.sleep(hours * 3600)  # sleep in background
        await msg_to_delete.delete()
        await notice_msg.edit_text("Your File/Video is successfully deleted!!!")
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Auto Delete Error:\n\n<code>{e}</code>"
        )
        print(f"⚠️ Clone Auto Delete Error: {e}")

@Client.on_message(filters.command("start") & filters.private & filters.incoming)
async def start(client, message):
    try:
        me = await client.get_me()
        clone = await db.get_bot(me.id)
        if not clone:
            return

        # --- Track new users ---
        if not await clonedb.is_user_exist(me.id, message.from_user.id):
            await clonedb.add_user(me.id, message.from_user.id)
            await db.increment_users_count(me.id)

        if not await is_subscribed(client, message.from_user.id, me.id):
            fsub_data = clone.get("force_subscribe", [])
            updated = False
            buttons = []
            new_fsub_data = []

            for item in fsub_data:                
                ch_id = item["channel"]
                target = item.get("limit", 0)
                joined = item.get("joined", 0)
                mode = item.get("mode", "normal")

                clone_client = get_client(me.id)
                if not clone_client:
                    await client.send_message(message.from_user.id, "⚠️ Clone bot not running. Start it first!")
                    return

                if not item.get("link"):
                    if mode == "request":
                        invite = await clone_client.create_chat_invite_link(ch_id, creates_join_request=True)
                    else:
                        invite = await clone_client.create_chat_invite_link(ch_id)
                    item["link"] = invite.invite_link
                    updated = True

                if mode == "normal":
                    try:
                        member = await clone_client.get_chat_member(ch_id, message.from_user.id)
                        if member.status not in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
                            if target == 0 or joined < target:
                                item["joined"] = joined + 1
                                updated = True
                    except UserNotParticipant:
                        pass

                elif mode == "request":
                    if target == 0 or joined < target:
                        item["joined"] = joined + 1
                        updated = True

                if target != 0 and item["joined"] >= target:
                    updated = True
                    continue
                else:
                    new_fsub_data.append(item)

            if updated:
                await db.update_clone(me.id, {"force_subscribe": new_fsub_data})

            if str(message.from_user.id) not in clone.get("premium", []) and not new_fsub_data:
                pass
            else:
                for item in new_fsub_data:
                    buttons.append([InlineKeyboardButton("🔔 Join Channel", url=item["link"])])

                if len(message.command) > 1:
                    start_arg = message.command[1]
                    try:
                        kk, file_id = start_arg.split("_", 1)
                        buttons.append([InlineKeyboardButton("♻️ Try Again", callback_data=f"checksub#{kk}#{file_id}")])
                    except:
                        buttons.append([InlineKeyboardButton("♻️ Try Again", url=f"https://t.me/{me.username}?start={start_arg}")])

                return await client.send_message(
                    message.from_user.id,
                    "🚨 You must join the channel(s) first to use this bot.",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.MARKDOWN
                )

        if len(message.command) == 1:
            buttons = [[
                InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                InlineKeyboardButton('😊 About', callback_data='about')
                ],[
                InlineKeyboardButton('🤖 Create Your Own Clone', url=f'https://t.me/{BOT_USERNAME}?start')
                ],[
                InlineKeyboardButton('🔒 Close', callback_data='close')
            ]]

            start_text = clone.get("wlc") or script.START_TXT
            start_pic = clone.get("pics") or None

            if start_pic:
                return await message.reply_photo(
                    photo=start_pic,
                    caption=start_text.format(user=message.from_user.mention, bot=client.me.mention),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            return await message.reply_text(
                start_text.format(user=message.from_user.mention, bot=client.me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # --- Verification Handler ---
        data = message.command[1]
        try:
            pre, file_id = data.split('_', 1)
        except:
            file_id = data
            pre = ""

        if data.startswith("VERIFY-"):
            parts = data.split("-", 2)
            if len(parts) < 3 or str(message.from_user.id) != parts[1]:
                return await message.reply_text("❌ Invalid or expired link!", protect_content=True)

            if await check_token(client, parts[1], parts[2]):
                await verify_user(client, parts[1], parts[2])
                return await message.reply_text(
                    f"Hey {message.from_user.mention}, **verification** successful! ✅",
                    protect_content=clone.get("forward_protect", False)
                )
            else:
                return await message.reply_text("❌ Invalid or expired link!", protect_content=True)

        # --- Single File Handler ---
        if data.startswith("SINGLE-"):
            try:
                encoded = data.replace("SINGLE-", "", 1)
                decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("ascii")
                pre, decode_file_id = decoded.split("_", 1)

                if clone.get("access_token", False) and str(message.from_user.id) not in clone.get("premium", []) and not await check_verification(client, message.from_user.id):
                    verify_url = await get_token(client, message.from_user.id, f"https://t.me/{me.username}?start=")
                    btn = [[InlineKeyboardButton("✅ Verify", url=verify_url)]]

                    tutorial_url = clone.get("access_token_tutorial", None)
                    if tutorial_url:
                        btn.append([InlineKeyboardButton("ℹ️ Tutorial", url=tutorial_url)])

                    btn.append([InlineKeyboardButton("♻️ Try Again", url=f"https://t.me/{me.username}?start=SINGLE-{encoded}")])

                    return await message.reply_text(
                        "🚫 You are not **verified**! Kindly **verify** to continue.",
                        protect_content=clone.get("forward_protect", False),
                        reply_markup=InlineKeyboardMarkup(btn)
                    )

                msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
                f_caption = None
                sent_msg = None
                if msg.media:
                    file = getattr(msg, msg.media.value)
                    file_name = getattr(file, "file_name", None) or "Media"
                    file_size = getattr(file, "file_size", None)
                    original_caption = msg.caption or ""
                    if clone.get("caption", None):
                        try:
                            f_caption = clone.get("caption", None).format(
                                file_name=file_name,
                                file_size=get_size(file_size) if file_size else "N/A",
                                caption=original_caption
                            )
                        except:
                            f_caption = original_caption or f"<code>{file_name}</code>"
                    else:
                        f_caption = original_caption or f"<code>{file_name}</code>"

                    sent_msg = await msg.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=clone.get("forward_protect", False))
                else:
                    sent_msg = await msg.copy(chat_id=message.from_user.id, protect_content=clone.get("forward_protect", False))

                buttons_data = clone.get("button", [])
                buttons = []
                for btn in buttons_data:
                    buttons.append([InlineKeyboardButton(btn["name"], url=btn["url"])])

                if buttons:
                    await sent_msg.edit_caption(f_caption or (sent_msg.caption or ""), reply_markup=InlineKeyboardMarkup(buttons))
                elif f_caption and f_caption != (sent_msg.caption or ""):
                    await sent_msg.edit_caption(f_caption)

                if clone.get("auto_delete", False):
                    auto_delete_time = clone.get("auto_delete_time", 1)
                    k = await sent_msg.reply(
                        clone.get('auto_delete_msg', script.AD_TXT).format(time=auto_delete_time),
                        quote=True
                    )
                    asyncio.create_task(auto_delete_message(client, sent_msg, k, auto_delete_time))
                return
            except Exception as e:
                await client.send_message(
                    LOG_CHANNEL,
                    f"⚠️ Clone Single File Handler Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
                )
                print(f"⚠️ Clone Single File Handler Error: {e}")

        # --- Batch File Handler ---
        if data.startswith("BATCH-"):
            try:
                if clone.get("access_token", False) and str(message.from_user.id) not in clone.get("premium", []) and not await check_verification(client, message.from_user.id):
                    verify_url = await get_token(client, message.from_user.id, f"https://t.me/{me.username}?start=")
                    btn = [[InlineKeyboardButton("✅ Verify", url=verify_url)]]

                    tutorial_url = clone.get("access_token_tutorial", None)
                    if tutorial_url:
                        btn.append([InlineKeyboardButton("ℹ️ Tutorial", url=tutorial_url)])

                    btn.append([InlineKeyboardButton("♻️ Try Again", url=f"https://t.me/{me.username}?start=BATCH-{file_id}")])

                    return await message.reply_text(
                        "🚫 You are not **verified**! Kindly **verify** to continue.",
                        protect_content=clone.get("forward_protect", False),
                        reply_markup=InlineKeyboardMarkup(btn)
                    )

                file_id = data.split("-", 1)[1]
                msgs = BATCH_FILES.get(file_id)

                if not msgs:
                    decode_file_id = base64.urlsafe_b64decode(file_id + "=" * (-len(file_id) % 4)).decode("ascii")
                    msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
                    media = getattr(msg, msg.media.value)
                    file_id = media.file_id
                    file = await client.download_media(file_id)
                    with open(file) as file_data:
                        msgs = json.loads(file_data.read())
                    os.remove(file)
                    BATCH_FILES[file_id] = msgs

                total_files = len(msgs)
                sts = await message.reply(f"📦 Preparing batch...\n\nTotal files: **{total_files}**")

                sent_files = []
                for index, msg in enumerate(msgs, start=1):
                    try:
                        await sts.edit_text(f"📤 Sending file {index}/{total_files}...")
                    except:
                        pass

                    channel_id = int(msg.get("channel_id"))
                    msgid = msg.get("msg_id")
                    info = await client.get_messages(channel_id, int(msgid))
                    f_caption = None
                    sent_msg = None
                    if info.media:
                        file = getattr(info, info.media.value)
                        file_name = getattr(file, "file_name", None) or "Media"
                        file_size = getattr(file, "file_size", None)
                        original_caption = info.caption or ""
                        if clone.get("caption", None):
                            try:
                                f_caption = clone.get("caption", None).format(
                                    file_name=file_name,
                                    file_size=get_size(file_size) if file_size else "N/A",
                                    caption=original_caption
                                )
                            except:
                                f_caption = original_caption or f"<code>{file_name}</code>"
                        else:
                            f_caption = original_caption or f"<code>{file_name}</code>"

                        sent_msg = await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=clone.get("forward_protect", False))
                    else:
                        sent_msg = await info.copy(chat_id=message.from_user.id, protect_content=clone.get("forward_protect", False))

                    sent_files.append(sent_msg)
                    await asyncio.sleep(1)

                    buttons_data = clone.get("button", [])
                    buttons = []
                    for btn in buttons_data:
                        buttons.append([InlineKeyboardButton(btn["name"], url=btn["url"])])

                    if buttons:
                        await sent_msg.edit_caption(f_caption or (sent_msg.caption or ""), reply_markup=InlineKeyboardMarkup(buttons))
                    elif f_caption and f_caption != (sent_msg.caption or ""):
                        await sent_msg.edit_caption(f_caption)

                if clone.get("auto_delete", False):
                    auto_delete_time = clone.get("auto_delete_time", 1)
                    k = await message.reply(
                        clone.get('auto_delete_msg', script.AD_TXT).format(time=auto_delete_time),
                        quote=True
                    )
                    asyncio.create_task(auto_delete_message(client, sent_files, k, auto_delete_time))

                await sts.edit_text(f"✅ Batch completed!\n\nTotal files sent: **{total_files}**")
                await asyncio.sleep(5)
                await sts.delete()
            except Exception as e:
                await client.send_message(
                    LOG_CHANNEL,
                    f"⚠️ Clone Batch File Handler Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
                )
                print(f"⚠️ Clone Batch File Handler Error: {e}")

        # --- Auto Post Handler ---
        if data.startswith("AUTO-"):
            encoded = data.replace("AUTO-", "", 1)
            decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("ascii")
            pre, file_id = decoded.split("_", 1)

            if clone.get("access_token", False) and str(message.from_user.id) not in clone.get("premium", []) and not await check_verification(client, message.from_user.id):
                verify_url = await get_token(client, message.from_user.id, f"https://t.me/{me.username}?start=")
                btn = [[InlineKeyboardButton("✅ Verify", url=verify_url)]]

                tutorial_url = clone.get("access_token_tutorial", None)
                if tutorial_url:
                    btn.append([InlineKeyboardButton("ℹ️ Tutorial", url=tutorial_url)])

                btn.append([InlineKeyboardButton("♻️ Try Again", url=f"https://t.me/{me.username}?start=AUTO-{encoded}")])

                return await message.reply_text(
                    "🚫 You are not **verified**! Kindly **verify** to continue.",
                    protect_content=clone.get("forward_protect", False),
                    reply_markup=InlineKeyboardMarkup(btn)
                )

            try:
                msg = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=file_id,
                    protect_content=clone.get("forward_protect", False)
                )

                filetype = msg.media
                file = getattr(msg, filetype.value)
                file_name = getattr(file, "file_name", None) or "Media"
                file_size = getattr(file, "file_size", None)
                original_caption = msg.caption or ""
                if clone.get("caption", None):
                    try:
                        f_caption = clone.get("caption", None).format(
                            file_name=file_name,
                            file_size=get_size(file_size) if file_size else "N/A",
                            caption=original_caption
                        )
                    except:
                        f_caption = original_caption or f"<code>{file_name}</code>"
                else:
                    f_caption = original_caption or f"<code>{file_name}</code>"

                buttons_data = clone.get("button", [])
                buttons = []
                for btn in buttons_data:
                    buttons.append([InlineKeyboardButton(btn["name"], url=btn["url"])])

                if buttons:
                    await msg.edit_caption(f_caption, reply_markup=InlineKeyboardMarkup(buttons))
                else:
                    await msg.edit_caption(f_caption)

                if clone.get("auto_delete", False):
                    auto_delete_time = clone.get("auto_delete_time", 1)
                    k = await msg.reply(
                        clone.get('auto_delete_msg', script.AD_TXT).format(time=auto_delete_time),
                        quote=True
                    )
                    asyncio.create_task(auto_delete_message(client, msg, k, auto_delete_time))
                return
            except Exception as e:
                await client.send_message(
                    LOG_CHANNEL,
                    f"⚠️ Clone Auto Post Handler Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
                )
                print(f"⚠️ Clone Auto Post Handler Error: {e}")

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Start Bot Error:\n\n<code>{e}</code>"
        )
        print(f"⚠️ Clone Start Bot Error: {e}")

@Client.on_message(filters.command(['genlink']) & filters.private)
async def link(client, message):
    try:
        me = await client.get_me()
        clone = await db.get_bot(me.id)
        owner_id = clone.get("user_id")
        moderators = clone.get("moderators", [])

        if message.from_user.id != owner_id and message.from_user.id not in moderators:
            await message.reply("❌ You are not authorized to use this bot.")
            return

        if message.reply_to_message:
            g_msg = message.reply_to_message
        else:
            g_msg = await client.ask(
                message.chat.id,
                "📩 Please send me the message (file/text/media) to generate a shareable link.\n\nSend /cancel to stop.",
            )

            if g_msg.text and g_msg.text.lower() == '/cancel':
                return await message.reply('🚫 Process has been cancelled.')

        post = await g_msg.copy(LOG_CHANNEL)
        file_id = str(post.id)
        string = f"file_{file_id}"
        outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
        share_link = f"https://t.me/{me.username}?start=SINGLE-{outstr}"

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔁 Share URL", url=f'https://t.me/share/url?url={share_link}')]]
        )

        await message.reply(
            f"Here is your link:\n{share_link}",
            reply_markup=reply_markup
        )

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Generate Link Error: {e}")

def batch_progress_bar(done, total, length=20):
    if total == 0:
        return "[░" * length + "] 0%"
    
    percent = int((done / total) * 100)
    filled = int((done / total) * length)
    empty = length - filled
    bar = "▓" * filled + "░" * empty

    percent_str = f"{percent}%"
    bar_list = list(bar)
    start_pos = max((length - len(percent_str)) // 2, 0)
    for i, c in enumerate(percent_str):
        if start_pos + i < length:
            bar_list[start_pos + i] = c
    return f"[{''.join(bar_list)}]"

@Client.on_message(filters.command(['batch']) & filters.private)
async def batch(client, message):
    try:
        me = await client.get_me()
        clone = await db.get_bot(me.id)
        owner_id = clone.get("user_id")
        moderators = clone.get("moderators", [])

        if message.from_user.id != owner_id and message.from_user.id not in moderators:
            return await message.reply("❌ You are not authorized to use this bot.")

        usage_text = (
            f"📌 Use correct format.\n\n"
            f"Example:\n/batch https://t.me/{me.username}/10 https://t.me/{me.username}/20"
        )

        if " " not in message.text:
            return await message.reply(usage_text)

        links = message.text.strip().split(" ")
        if len(links) != 3:
            return await message.reply(usage_text)

        cmd, first, last = links
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")

        match = regex.match(first)
        if not match:
            return await message.reply('❌ Invalid first link.')
        f_chat_id = match.group(4)
        f_msg_id = int(match.group(5))
        f_chat_id = int(f"-100{f_chat_id}") if f_chat_id.isnumeric() else f_chat_id

        match = regex.match(last)
        if not match:
            return await message.reply('❌ Invalid last link.')
        l_chat_id = match.group(4)
        l_msg_id = int(match.group(5))
        l_chat_id = int(f"-100{l_chat_id}") if l_chat_id.isnumeric() else l_chat_id

        if f_chat_id != l_chat_id:
            return await message.reply("❌ Chat IDs do not match.")

        chat_id = (await client.get_chat(f_chat_id)).id

        start_id = min(f_msg_id, l_msg_id)
        end_id = max(f_msg_id, l_msg_id)
        total_msgs = (end_id - start_id) + 1

        sts = await message.reply(
            "⏳ Generating link for your messages...\n"
            "This may take time depending upon number of messages."
        )

        outlist = []
        og_msg = 0
        tot = 0

        for msg_id in range(start_id, end_id + 1):
            try:
                msg = await client.get_messages(f_chat_id, msg_id)
            except Exception:
                await asyncio.sleep(0.1)
                continue

            tot += 1
            if og_msg % 20 == 0 or tot == total_msgs:
                try:
                    progress_bar = batch_progress_bar(tot, total_msgs)
                    await sts.edit(f"""
⚙️ <b>Generating Batch Link...</b>

📂 Total: {total_msgs}
✅ Done: {tot}/{total_msgs}
⏳ Remaining: {total_msgs - tot}
📌 Status: Saving Messages

{progress}
""")
                except:
                    pass

            if not msg or msg.empty or msg.service:
                await asyncio.sleep(0.1)
                continue

            file = {
                "channel_id": f_chat_id,
                "msg_id": msg.id
            }
            og_msg += 1
            outlist.append(file)

            await asyncio.sleep(0.1)

        filename = f"batchmode_{message.from_user.id}.json"
        with open(filename, "w+", encoding="utf-8") as out:
            json.dump(outlist, out, indent=2)

        post = await client.send_document(
            LOG_CHANNEL,
            filename,
            file_name="Batch.json",
            caption="⚠️ Batch Generated For Filestore."
        )
        os.remove(filename)

        string = str(post.id)
        file_id = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
        share_link = f"https://t.me/{me.username}?start=BATCH-{file_id}"

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔁 Share URL", url=f'https://t.me/share/url?url={share_link}')]]
        )

        await sts.edit(
            f"Here is your link:\n\n{share_link}",
            reply_markup=reply_markup
        )

    except ChannelInvalid:
        await message.reply('⚠️ This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        await message.reply('⚠️ Invalid Link specified.')
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Batch Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Batch Error: {e}")

@Client.on_message(filters.command("shorten") & filters.private)
async def shorten_handler(client: Client, message: Message):
    try:
        me = await client.get_me()
        clone = await db.get_bot(me.id)
        owner_id = clone.get("user_id")
        moderators = clone.get("moderators", [])

        if message.from_user.id != owner_id and message.from_user.id not in moderators:
            await message.reply("❌ You are not authorized to use this bot.")
            return

        user_id = message.from_user.id
        cmd = message.command
        user = await db.get_user(user_id)

        help_text = (
            "/shorten - Start shortening links\n"
            "/shorten None - Reset Base Site and Shortener API\n\n"
            "Flow:\n"
            "1️⃣ Send /shorten to start\n"
            "2️⃣ Set your Base Site (e.g., shortnerdomain.com)\n"
            "3️⃣ Set your Shortener API\n"
            "4️⃣ Send the link to shorten\n\n"
            "Example to reset: `/shorten None`"
        )

        if len(cmd) == 1:
            help_msg = await message.reply(help_text)
            SHORTEN_STATE[user_id] = {"step": 1, "help_msg_id": help_msg.id}

            if user.get("base_site") and user.get("shortener_api"):
                SHORTEN_STATE[user_id]["step"] = 3
                await message.reply("🔗 Base site and API already set. Send the link you want to shorten:")
            else:
                await message.reply("Please send your **base site** (e.g., shortnerdomain.com):")
            return

        if len(cmd) == 2 and cmd[1].lower() == "none":
            await update_user_info(user_id, {"base_site": None, "shortener_api": None})
            SHORTEN_STATE[user_id] = {"step": 1}
            return await message.reply(
                "✅ Base site and API reset. Please send your **base site** (e.g., shortnerdomain.com)"
            )

        if user_id not in SHORTEN_STATE:
            SHORTEN_STATE[user_id] = {"step": 1}

        state = SHORTEN_STATE[user_id]

        help_msg_id = state.get("help_msg_id")
        if help_msg_id:
            try:
                await client.delete_messages(chat_id=message.chat.id, message_ids=help_msg_id)
            except:
                pass
            state.pop("help_msg_id", None)

        if state["step"] == 1:
            base_site = message.text.strip()
            if not domain(base_site):
                return await message.reply("❌ Invalid domain. Send a valid base site:")
            await update_user_info(user_id, {"base_site": base_site})
            state["step"] = 2
            await message.reply("✅ Base site set. Now send your **Shortener API key**:")
            return

        if state["step"] == 2:
            api = message.text.strip()
            await update_user_info(user_id, {"shortener_api": api})
            state["step"] = 3
            await message.reply("✅ API set. Now send the **link to shorten**:")
            return

        if state["step"] == 3:
            long_link = message.text.strip()
            user = await db.get_user(user_id)
            base_site = user.get("base_site")
            api_key = user.get("shortener_api")
            if not base_site or not api_key:
                SHORTEN_STATE[user_id] = {"step": 1}
                return await message.reply("❌ Base site or API missing. Let's start over. Send your base site:")

            short_link = f"{base_site}/short?api={api_key}&url={long_link}"
            await message.reply(f"🔗 Shortened link:\n{short_link}")
            SHORTEN_STATE.pop(user_id, None)

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Shorten Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Shorten Error: {e}")

async def broadcast_messages(bot_id, user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(bot_id, user_id, message)
    except InputUserDeactivated:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Deleted"
    except UserIsBlocked:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Blocked"
    except PeerIdInvalid:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Error"
    except Exception:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Error"

def broadcast_progress_bar(done, total, length=20):
    if total == 0:
        return "[░" * length + "] 0%"
    
    percent = int((done / total) * 100)
    filled = int((done / total) * length)
    empty = length - filled
    bar = "▓" * filled + "░" * empty

    percent_str = f"{percent}%"
    bar_list = list(bar)
    start_pos = max((length - len(percent_str)) // 2, 0)
    for i, c in enumerate(percent_str):
        if start_pos + i < length:
            bar_list[start_pos + i] = c
    return f"[{''.join(bar_list)}]"

@Client.on_message(filters.command("broadcast") & filters.private)
async def broadcast(client, message):
    try:
        me = await client.get_me()
        clone = await db.get_bot(me.id)
        owner_id = clone.get("user_id")
        moderators = clone.get("moderators", [])

        if message.from_user.id != owner_id and message.from_user.id not in moderators:
            await message.reply("❌ You are not authorized to use this bot.")
            return

        if message.reply_to_message:
            b_msg = message.reply_to_message
        else:
            b_msg = await client.ask(
                message.from_user.id,
                "📩 Now send me your broadcast message\n\nType /cancel to stop.",
            )

            if b_msg.text and b_msg.text.lower() == "/cancel":
                return await message.reply("🚫 Broadcast cancelled.")

        users = await clonedb.get_all_users(me.id)
        total_users = await clonedb.total_users_count(me.id)
        sts = await message.reply_text("⏳ Broadcast starting...")

        done = blocked = deleted = failed = success = 0
        start_time = time.time()

        async for user in users:
            if 'user_id' in user:
                pti, sh = await broadcast_messages(me.id, int(user['user_id']), b_msg)
                if pti:
                    success += 1
                else:
                    if sh == "Blocked":
                        blocked += 1
                    elif sh == "Deleted":
                        deleted += 1
                    else:
                        failed += 1
                done += 1

                if done % 10 == 0 or done == total_users:
                    progress = broadcast_progress_bar(done, total_users)
                    percent = (done / total_users) * 100
                    elapsed = time.time() - start_time
                    speed = done / elapsed if elapsed > 0 else 0
                    remaining = total_users - done
                    eta = datetime.timedelta(seconds=int(remaining / speed)) if speed > 0 else "∞"

                    try:
                        await sts.edit(f"""
📢 <b>Broadcast in Progress...</b>

{progress}

👥 Total Users: {total_users}
✅ Success: {success}
🚫 Blocked: {blocked}
❌ Deleted: {deleted}
⚠️ Failed: {failed}

⏳ ETA: {eta}
⚡ Speed: {speed:.2f} users/sec
""")
                    except:
                        pass
            else:
                done += 1
                failed += 1

        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        final_progress = broadcast_progress_bar(total_users, total_users)
        final_text = f"""
✅ <b>Broadcast Completed</b> ✅

⏱ Duration: {time_taken}
👥 Total Users: {total_users}

📊 Results:
✅ Success: {success} ({(success/total_users)*100:.1f}%)
🚫 Blocked: {blocked} ({(blocked/total_users)*100:.1f}%)
❌ Deleted: {deleted} ({(deleted/total_users)*100:.1f}%)
⚠️ Failed: {failed} ({(failed/total_users)*100:.1f}%)

━━━━━━━━━━━━━━━━━━━━━━
{final_progress} 100%
━━━━━━━━━━━━━━━━━━━━━━

⚡ Speed: {speed:.2f} users/sec
"""
        await sts.edit(final_text)

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Broadcast Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Broadcast Error: {e}")

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0

    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])

    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref

async def auto_post_clone(bot_id: int, assistant, db, target_channel: int):
    try:
        bot_id = int(bot_id)
        clone = await db.get_clone_by_id(bot_id)
        if not clone or not clone.get("auto_post", False):
            return

        clone_client = get_client(bot_id)
        if not clone_client:
            return

        FIX_IMAGE = "https://i.ibb.co/gFv0Nm8M/IMG-20250904-163513-052.jpg"

        async for message in assistant.get_chat_history(-1002912952165, limit=0):  # 0 = full history
            media_file_id = None
            media_type = None

            if message.photo:
                media_file_id = message.photo.file_id
                media_type = "photo"
            elif message.video:
                media_file_id = message.video.file_id
                media_type = "video"
            elif message.document:
                media_file_id = message.document.file_id
                media_type = "document"
            elif message.animation:
                media_file_id = message.animation.file_id
                media_type = "animation"

            if not media_file_id:
                continue

            # Skip duplicates
            if await db.is_media_exist(bot_id, media_file_id):
                continue

            await db.add_media(
                bot_id=bot_id,
                msg_id=message.id,
                file_id=media_file_id,
                caption=message.caption or "",
                media_type=media_type,
                date=int(message.date.timestamp()),
                posted=False
            )
            print(f"✅ Saved media: {media_type} ({media_file_id}) for bot {bot_id}")

            await asyncio.sleep(0.2)  # small delay to avoid flood

        print("📦 Capture completed.")

        while True:
            try:
                fresh = await db.get_clone_by_id(bot_id)
                if not fresh or not fresh.get("auto_post", False):
                    return

                item = await db.get_random_unposted_media(bot_id)
                if not item:
                    print(f"⌛ No new media for {bot_id}, sleeping 60s...")
                    await asyncio.sleep(60)
                    continue

                file_id = item.get("file_id")
                if not file_id:
                    await db.mark_media_posted(item["_id"], bot_id)
                    continue

                unpack, _ = unpack_new_file_id(file_id)
                string = f"file_{unpack}"
                outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
                bot_username = (await clone_client.get_me()).username
                share_link = f"https://t.me/{bot_username}?start=AUTO-{outstr}"

                header = fresh.get("header")
                footer = fresh.get("footer")
                selected_caption = random.choice(script.CAPTION_LIST) if script.CAPTION_LIST else "Here is your file"

                text = ""
                if header:
                    text += f"<blockquote>{header}</blockquote>\n\n"
                text += f"{selected_caption}\n\n<blockquote>🔗 Here is your link:\n{share_link}</blockquote>"
                if footer:
                    text += f"\n\n<blockquote>{footer}</blockquote>"

                await clone_client.send_photo(
                    chat_id=target_channel,
                    photo=FIX_IMAGE,
                    caption=text,
                    parse_mode=enums.ParseMode.HTML
                )

                await db.mark_media_posted(item["_id"], bot_id)

                sleep_time = int(fresh.get("interval_sec", 60))
                await asyncio.sleep(sleep_time)

            except Exception as e:
                print(f"⚠️ Clone Auto-post error for {bot_id}: {e}")
                try:
                    await clone_client.send_message(
                        LOG_CHANNEL,
                        f"⚠️ Clone Auto Post Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
                    )
                except:
                    pass
                await asyncio.sleep(30)

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"❌ Clone AutoPost crashed for {bot_id}:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"❌ Clone AutoPost crashed for {bot_id}: {e}")

"""async def auto_post_clone(bot_id: int, target_channel: int, log_channel: int, assistant):
    try:
        bot_id = int(bot_id)
        clone = await db.get_clone_by_id(bot_id)
        if not clone or not clone.get("auto_post", False):
            return

        clone_client = get_client(bot_id)  # Clone bot client
        if not clone_client:
            return

        FIX_IMAGE = "https://i.ibb.co/gFv0Nm8M/IMG-20250904-163513-052.jpg"

        while True:
            try:
                fresh = await db.get_clone_by_id(bot_id)
                if not fresh or not fresh.get("auto_post", False):
                    return

                last_msg_id = int(clone.get("last_msg_id", 0))

                # Start from very first message if never posted
                if last_msg_id == 0:
                    messages = []
                    async for msg in assistant.get_chat_history(log_channel, limit=100):
                        messages.append(msg)

                    if messages:
                        first_msg = messages[-1]  # last in list = oldest
                        last_msg_id = first_msg.id - 1
                    else:
                        print(f"⚠️ No messages found in log channel {log_channel}")
                        return

                messages = []
                async for msg in assistant.get_chat_history(log_channel, offset_id=last_msg_id):
                    messages.append(msg)

                for msg in reversed(messages):
                    if not msg.media:
                        continue

                    file_type = msg.media.value
                    file = getattr(msg, file_type, None)
                    if not file:
                        continue

                    already = await db.is_media_posted(file.file_id, bot_id)
                    if already:
                        continue

                    unpack, _ = unpack_new_file_id(file.file_id)
                    string = f"file_{unpack}"
                    outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
                    bot_username = (await clone_client.get_me()).username
                    share_link = f"https://t.me/{bot_username}?start=AUTO-{outstr}"

                    header = fresh.get("header")
                    footer = fresh.get("footer")
                    selected_caption = random.choice(script.CAPTION_LIST) if script.CAPTION_LIST else "Here is your file"

                    text = ""
                    if header:
                        text += f"<blockquote>{header}</blockquote>\n\n"
                    text += f"{selected_caption}\n\n<blockquote>🔗 Here is your link:\n{share_link}</blockquote>"
                    if footer:
                        text += f"\n\n<blockquote>{footer}</blockquote>"

                    await clone_client.send_photo(
                        chat_id=target_channel,
                        photo=FIX_IMAGE,
                        caption=text,
                        parse_mode=enums.ParseMode.HTML
                    )

                    await db.mark_media_posted(file.file_id, bot_id)

                    last_msg_id = msg.id
                    await db.update_clone(bot_id, {"last_msg_id": last_msg_id})

                    sleep_time = int(fresh.get("interval_sec", 30))
                    await asyncio.sleep(sleep_time)

                await asyncio.sleep(60)

            except Exception as e:
                print(f"⚠️ Clone Auto-post error for {bot_id}: {e}")
                try:
                    await clone_client.send_message(
                        LOG_CHANNEL,
                        f"⚠️ Clone Auto Post Error:\n\n<code>{e}</code>"
                    )
                except:
                    pass
                await asyncio.sleep(30)

    except Exception as e:
        print(f"❌ AutoPost crashed for {bot_id}: {e}")"""

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    try:
        me = await client.get_me()

        if query.data.startswith("checksub"):
            if not await is_subscribed(client, query):
                await query.answer("Join our channel first.", show_alert=True)
                return
            
            _, kk, file_id = query.data.split("#")
            await query.answer(url=f"https://t.me/{me.username}?start={kk}_{file_id}")

        # Start Menu
        elif query.data == "start":
            buttons = [
                [InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                 InlineKeyboardButton('ℹ️ About', callback_data='about')],
                [InlineKeyboardButton('🤖 Create Your Own Clone', url=f'https://t.me/{BOT_USERNAME}?start')],
                [InlineKeyboardButton('🔒 Close', callback_data='close')]
            ]
            clone = await db.get_bot(me.id)
            start_text = clone.get("wlc") or script.START_TXT
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

        else:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Clone Unknown Callback Data Received:\n\n{query.data}\n\nUser: {query.from_user.id}\n\nKindly check this message for assistance."
            )
            await query.answer("⚠️ Unknown action.", show_alert=True)

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Callback Handler Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Callback Handler Error: {e}")
        await query.answer("❌ An error occurred. The admin has been notified.", show_alert=True)

def mask_partial(word):
    if len(word) <= 2:
        return word[0] + "*"
    mid = len(word) // 2
    return word[:1] + "*" + word[2:]

def clean_text(text: str) -> str:
    cleaned = text
    for word in script.BAD_WORDS:
        cleaned = re.sub(
            re.escape(word), 
            mask_partial(word), 
            cleaned, 
            flags=re.IGNORECASE
        )
    return cleaned

@Client.on_message(filters.group | filters.channel)
async def message_capture(client: Client, message: Message):
    try:
        if client not in CLONE_ME or CLONE_ME[client] is None:
            try:
                CLONE_ME[client] = await client.get_me()
            except Exception as e:
                print(f"⚠️ get_me() failed: {e}")
                return

        me = CLONE_ME.get(client)
        if not me:
            print("❌ Failed to get bot info (me is None)")
            return

        clone = await db.get_bot(me.id)
        if not clone:
            return

        owner_id = clone.get("user_id")
        moderators = clone.get("moderators", [])

        selected_caption = random.choice(script.CAPTION_LIST)

        header = clone.get("header", None)
        footer = clone.get("footer", None)

        text = message.text or message.caption or ""
        original_text = text

        if text:
            if clone.get("word_filter", False):
                text = clean_text(original_text)
            else:
                text = text

        if text != original_text:
            await message.edit(text)
            notify_msg = f"⚠️ Edited inappropriate content in clone @{me.username}.\nMessage ID: {message.id}"

            for mod_id in moderators:
                await client.send_message(chat_id=mod_id, text=notify_msg)
            if owner_id:
                await client.send_message(chat_id=owner_id, text=notify_msg)

        new_text = ""

        if header:
            new_text += f"<blockquote>{header}</blockquote>\n\n"

        if clone.get("random_caption", False):
            new_text += f"{selected_caption}\n\n<blockquote>{text}</blockquote>"
        else:
            new_text += f"{text}"

        if footer:
            new_text += f"\n\n<blockquote>{footer}</blockquote>"

        if me.username and me.username in text:
            await message.delete()

            file_id = None
            if message.photo:
                file_id = message.photo.file_id
            elif message.video:
                file_id = message.video.file_id
            elif message.document:
                file_id = message.document.file_id

            if file_id:
                await client.send_cached_media(chat_id=message.chat.id, file_id=file_id, caption=new_text, parse_mode=enums.ParseMode.HTML)
            else:
                await client.send_message(chat_id=message.chat.id, text=new_text, parse_mode=enums.ParseMode.HTML)

        """media_file_id = None
        media_type = None
        if message.chat.id == -1002912952165:
            if message.photo:
                media_file_id = message.photo.file_id
                media_type = "photo"
            elif message.video:
                media_file_id = message.video.file_id
                media_type = "video"
            elif message.document:
                media_file_id = message.document.file_id
                media_type = "document"
            elif message.animation:
                media_file_id = message.animation.file_id
                media_type = "animation"

            if media_file_id:
                if await db.is_media_exist(me.id, media_file_id):
                    print(f"⚠️ Duplicate media skip kiya: {media_type} ({media_file_id}) for bot {me.id}")
                    return

                await db.add_media(
                    bot_id=me.id,
                    msg_id=message.id,
                    file_id=media_file_id,
                    caption=message.caption or "",
                    media_type=media_type,
                    date=int(message.date.timestamp()),
                    posted=False
                )
                print(f"✅ Saved media: {media_type} ({media_file_id}) for bot {me.id}")
                await asyncio.sleep(0.3)"""

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Unexpected Error in message_capture:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Clone Unexpected Error in message_capture: {e}")
