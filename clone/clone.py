import os, logging, asyncio, re, json, base64, random, pytz, aiohttp, requests, string, json, http.client, time, datetime, motor.motor_asyncio
from struct import pack
from shortzy import Shortzy
from validators import domain
from pyrogram import Client, filters, enums
from pyrogram.types import *
from pyrogram.file_id import FileId
from pyrogram.errors import ChatAdminRequired, InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid, ChannelInvalid, UsernameInvalid, UsernameNotModified
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

TOKENS = {}
VERIFIED = {}
BATCH_FILES = {}

async def is_subscribed(bot, user_id: int, bot_id: int):
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
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status == enums.ChatMemberStatus.BANNED:
                return False
        except UserNotParticipant:
            return False
        except Exception as e:
            await bot.send_message(
                LOG_CHANNEL,
                f"⚠️ Clone is_subscribed Error:\n\n<code>{channel_id}: {e}</code>"
            )
            print(f"⚠️ Clone is_subscribed Error: {channel_id}: {e}")
            return False

    return True

async def get_verify_shorted_link(client, link):
    bot_id = (await client.get_me()).id
    clone = await db.get_clone_by_id(bot_id)
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

async def check_token(bot, userid, token):
    user = await bot.get_users(userid)
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

async def get_token(bot, userid, link):
    user = await bot.get_users(userid)
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    TOKENS[user.id] = {token: False}
    link = f"{link}VERIFY-{user.id}-{token}"
    shortened_verify_url = await get_verify_shorted_link(bot, link)
    return str(shortened_verify_url)

async def verify_user(bot, userid, token):
    user = await bot.get_users(userid)
    TOKENS[user.id] = {token: True}

    clone = await db.get_bot((await bot.get_me()).id)
    validity_hours = clone.get("access_token_validity", 24)

    VERIFIED[user.id] = datetime.datetime.now() + datetime.timedelta(hours=validity_hours)

async def check_verification(bot, userid):
    user = await bot.get_users(userid)
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

            if not new_fsub_data:
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

        # --- Batch Handler ---
        """if data.startswith("BATCH-"):
            if clone.get("access_token", False) and not await check_verification(client, message.from_user.id):
                btn = [
                    [InlineKeyboardButton("✅ Verify", url=await get_token(client, message.from_user.id, f"https://t.me/{username}?start="))],
                    [InlineKeyboardButton("ℹ️ How To Open Link & Verify", url=clone.get("access_token_tutorial", None))]
                ]
                return await message.reply_text(
                    "🚫 You are not **verified**! Kindly **verify** to continue.",
                    protect_content=True,
                    reply_markup=InlineKeyboardMarkup(btn)
                )

            sts = await message.reply("Please wait...")
            file_id = data.split("-", 1)[1]
            msgs = BATCH_FILES.get(file_id)

            if not msgs:
                file = await client.download_media(file_id)
                with open(file) as file_data:
                    msgs = json.loads(file_data.read())
                os.remove(file)
                BATCH_FILES[file_id] = msgs

            sent = 0
            for msg in msgs:
                original_caption = msg.get("caption") or ""
                file_name = msg.get("file_name") or "Unknown"
                file_size = get_size(msg.get("file_size") or 0)

                if clone.get("caption", None):
                    try:
                        f_caption = clone.get("caption", None).format(
                            file_name=file_name,
                            file_size=file_size,
                            caption=original_caption
                        )
                    except:
                        f_caption = original_caption or f"<code>{file_name}</code>"
                else:
                    f_caption = original_caption or f"<code>{file_name}</code>"

                try:
                    m = await client.send_cached_media(
                        chat_id=message.from_user.id,
                        file_id=msg.get("file_id"),
                        caption=f_caption,
                        protect_content=clone.get("forward_protect", False)
                    )
                    sent += 1

                    if clone.get("auto_delete", False):
                        auto_delete_time = int(clone.get("auto_delete_time", 1))
                        k = await m.reply(
                            clone.get('auto_delete_msg', script.AD_TXT).format(time=auto_delete_time),
                            quote=True
                        )
                        asyncio.create_task(auto_delete_message(client, m, k, auto_delete_time))
                except FloodWait as e:
                    await asyncio.sleep(e.x)
                    try:
                        m = await client.send_cached_media(
                            chat_id=message.from_user.id,
                            file_id=msg.get("file_id"),
                            caption=f_caption,
                            protect_content=clone.get("forward_protect", False)
                        )
                        sent += 1

                        if clone.get("auto_delete", False):
                            auto_delete_time = int(clone.get("auto_delete_time", 1))
                            k = await m.reply(
                                clone.get('auto_delete_msg', script.AD_TXT).format(time=auto_delete_time),
                                quote=True
                            )
                            asyncio.create_task(auto_delete_message(client, m, k, auto_delete_time))
                    except Exception as e2:
                        await client.send_message(
                            LOG_CHANNEL,
                            f"⚠️ Clone Batch Error After FloodWait:\n\n<code>{e2}</code>"
                        )
                        print(f"⚠️ Clone Batch Error After FloodWait: {e2}")
                        continue
                except Exception as e:
                    await client.send_message(
                        LOG_CHANNEL,
                        f"⚠️ Clone Batch Error Sending File:\n\n<code>{e}</code>"
                    )
                    print(f"⚠️ Clone Batch Error Sending File: {e}")
                    continue
            await sts.edit(f"✅ Successfully sent `{sent}` files.")"""

        # --- Single File Handler ---
        pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)

        if clone.get("access_token", False) and not await check_verification(client, message.from_user.id):
            verify_url = await get_token(client, message.from_user.id, f"https://t.me/{me.username}?start=")
            btn = [[InlineKeyboardButton("✅ Verify", url=verify_url)]]

            tutorial_url = clone.get("access_token_tutorial", None)
            if tutorial_url:
                btn.append([InlineKeyboardButton("ℹ️ Tutorial", url=tutorial_url)])

            #btn.append([InlineKeyboardButton("♻️ Try Again", url=f"https://t.me/{me.username}?start={file_id}")])

            return await message.reply_text(
                "🚫 You are not **verified**! Kindly **verify** to continue.",
                protect_content=clone.get("forward_protect", False),
                reply_markup=InlineKeyboardMarkup(btn)
            )

        try:
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                protect_content=clone.get("forward_protect", False),
            )

            filetype = msg.media
            file = getattr(msg, filetype.value)

            original_caption = msg.caption or ""

            if clone.get("caption", None):
                try:
                    f_caption = clone.get("caption", None).format(
                        file_name=file.file_name,
                        file_size=get_size(file.file_size),
                        caption=original_caption
                    )
                except:
                    f_caption = original_caption or f"<code>{file.file_name}</code>"
            else:
                f_caption = original_caption or f"<code>{file.file_name}</code>"

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
        except:
            pass
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Start Bot Error:\n\n<code>{e}</code>"
        )
        print(f"⚠️ Clone Start Bot Error: {e}")

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
    """Return file_id, file_ref"""
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

async def auto_post_clone(bot_id: int, db, target_channel: int):
    clone = await db.get_clone_by_id(bot_id)
    if not clone or not clone.get("auto_post", False):
        return

    clone_client = get_client(bot_id)
    if not clone_client:
        message.reply("⚠️ Clone client not running!")
        return

    while True:
        try:
            fresh = await db.get_clone_by_id(bot_id)
            if not fresh or not fresh.get("auto_post", False):
                return

            last_posted = fresh.get("last_posted_id", 0)
            item = await db.media.find_one(
                {"bot_id": bot_id, "msg_id": {"$gt": last_posted}},
                sort=[("msg_id", 1)]
            )

            if not item:
                await asyncio.sleep(60)
                continue

            media_type = None
            if "photo" in item.get("file_id", ""):
                media_type = "photo"
            elif "video" in item.get("file_id", ""):
                media_type = "video"
            else:
                media_type = "document"

            file_id, _ = unpack_new_file_id(item["file_id"])
            string = f"file_{file_id}"
            outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
            bot_username = (await clone_client.get_me()).username
            share_link = f"https://t.me/{bot_username}?start={outstr}"

            header = clone.get("header", None)
            footer = clone.get("footer", None)
            selected_caption = random.choice(script.CAPTION_LIST)

            text = ""
            if header:
                text += f"{header}\n\n"

            text += f"{selected_caption}\n\nHere is your link:\n{share_link}"

            if footer:
                text += f"\n\n{footer}"

            if media_type == "photo":
                await clone_client.send_photo(chat_id=target_channel, photo=db_image, caption=text)
            elif media_type == "video":
                await clone_client.send_video(chat_id=target_channel, video=db_image, caption=text)
            else:
                await clone_client.send_document(chat_id=target_channel, document=db_image, caption=text)

            await db.update_clone(bot_id, {"last_posted_id": item["msg_id"]})

            sleep_time = int(fresh.get("interval_sec", 30))
            await asyncio.sleep(sleep_time)

        except Exception as e:
            await clone_client.send_message(
                LOG_CHANNEL,
                f"⚠️ Clone Auto Post Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
            )
            print(f"⚠️ Clone Auto-post error: {e}")

@Client.on_message(filters.command(['genlink']) & filters.user(ADMINS) & filters.private)
async def link(bot, message):
    try:
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

        if not g_msg.media:
            return await message.reply("❌ This message has no supported media.")

        file_type = g_msg.media
        file = getattr(g_msg, file_type.value, None)
        if not file:
            return await message.reply("❌ Unsupported file type.")

        file_id, _ = unpack_new_file_id(file.file_id)
        string = f"file_{file_id}"
        outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")

        bot_username = (await bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={outstr}"

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔁 Share URL", url=f'https://t.me/share/url?url={share_link}')]]
        )

        text = f"Here is your link:\n{share_link}"

        await message.reply(
            text,
            reply_markup=reply_markup
        )

    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Generate Link Error: {e}")

"""@Client.on_message(filters.command(['batch']) & filters.user(ADMINS) & filters.private)
async def batch(bot, message):
    try:
        username = (await bot.get_me()).username
        usage_text = f"Use correct format.\nExample:\n/batch https://t.me/{username}/10 https://t.me/{username}/20"

        # Check format
        if " " not in message.text:
            return await message.reply(usage_text)

        links = message.text.strip().split(" ")
        if len(links) != 3:
            return await message.reply(usage_text)

        cmd, first, last = links
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")

        # First link
        match = regex.match(first)
        if not match:
            return await message.reply('Invalid first link.')
        f_chat_id = match.group(4)
        f_msg_id = int(match.group(5))
        f_chat_id = int(f"-100{f_chat_id}") if f_chat_id.isnumeric() else f_chat_id

        # Last link
        match = regex.match(last)
        if not match:
            return await message.reply('Invalid last link.')
        l_chat_id = match.group(4)
        l_msg_id = int(match.group(5))
        l_chat_id = int(f"-100{l_chat_id}") if l_chat_id.isnumeric() else l_chat_id

        # Check chat id match
        if f_chat_id != l_chat_id:
            return await message.reply("❌ Chat IDs do not match.")

        chat_id = (await bot.get_chat(f_chat_id)).id

        # Always ensure correct order (min → max)
        start_id = min(f_msg_id, l_msg_id)
        end_id = max(f_msg_id, l_msg_id)

        total_msgs = (end_id - start_id) + 1

        sts = await message.reply(
            "⏳ Generating link for your messages...\n"
            "This may take time depending upon number of messages."
        )
        FRMT = "Generating Link...\n\nTotal: {total}\nDone: {current}\nRemaining: {rem}\nStatus: {sts}"

        outlist = []
        og_msg = 0
        tot = 0

        # Fetch messages one by one in range
        for msg_id in range(start_id, end_id + 1):
            try:
                msg = await bot.get_messages(f_chat_id, msg_id)
            except:
                continue

            tot += 1
            if tot % 20 == 0:
                try:
                    await sts.edit(FRMT.format(
                        total=total_msgs,
                        current=tot,
                        rem=(total_msgs - tot),
                        sts="Saving Messages"
                    ))
                except:
                    pass

            if not msg or msg.empty or msg.service:
                continue

            file_type = msg.media
            file = getattr(msg, file_type.value)
            caption = getattr(msg, 'caption')

            file_id, _ = unpack_new_file_id(file.file_id)

            file = {
                "file_id": file.file_id,
                "caption": caption,
                "file_name": file.file_name,
                "file_size": file.file_size,
                "protect": False
            }
            og_msg += 1
            outlist.append(file)

        # Convert to file_id
        string = json.dumps(outlist)
        file_id = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")

        share_link = f"https://t.me/{username}?start=BATCH-{file_id}"

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔁 Share URL", url=f'https://t.me/share/url?url={share_link}')]]
        )

        bot_id = (await bot.get_me()).id
        clone = await db.get_clone_by_id(bot_id)

        header = clone.get("header", None)
        footer = clone.get("footer", None)

        text = ""

        if header:
            text += f"{header}\n\n"

        text += f"✅ Contains `{og_msg}` files.\n\nHere is your link:\n\n{share_link}"

        if footer:
            text += f"\n\n{footer}"

        await sts.edit(
            text,
            reply_markup=reply_markup
        )

    except ChannelInvalid:
        await message.reply('⚠️ This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        await message.reply('⚠️ Invalid link specified.')
    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Batch Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Batch Error: {e}")"""

# Broadcast sender with error handling
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

# Progress bar generator
def make_progress_bar(done, total):
    filled = int((done / total) * 20)
    empty = 20 - filled
    return "🟩" * filled + "⬛" * empty

# Clone broadcast command with reply-to-message and /cancel support
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.private)
async def broadcast(bot, message):
    try:
        me = await bot.get_me()

        # Use reply-to-message if available
        if message.reply_to_message:
            b_msg = message.reply_to_message
        else:
            # Ask user to send broadcast message
            try:
                b_msg = await bot.ask(
                    chat_id=message.from_user.id,
                    text="📩 Now send me your broadcast message\n\nType /cancel to stop.",
                    timeout=60
                )
            except asyncio.TimeoutError:
                return await message.reply("<b>⏰ Timeout! You didn’t send any message in 60s.</b>")

            # Check if user canceled
            if b_msg.text and b_msg.text.lower() == "/cancel":
                return await message.reply("<b>🚫 Broadcast cancelled.</b>")

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

                # Update progress every 10 users
                if not done % 10 or done == total_users:
                    progress = make_progress_bar(done, total_users)
                    percent = (done / total_users) * 100
                    elapsed = time.time() - start_time
                    speed = done / elapsed if elapsed > 0 else 0
                    remaining = total_users - done
                    eta = datetime.timedelta(seconds=int(remaining / speed)) if speed > 0 else "∞"

                    try:
                        await sts.edit(f"""
📢 <b>Broadcast in Progress...</b>

{progress} {percent:.1f}%

👥 <b>Total Users:</b> {total_users}
✅ Success: {success}
🚫 Blocked: {blocked}
❌ Deleted: {deleted}
⚠️ Failed: {failed}

⏳ <b>ETA:</b> {eta}
⚡ <b>Speed:</b> {speed:.2f} users/sec
""")
                    except:
                        pass
            else:
                done += 1
                failed += 1

        # Final summary
        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        progress_bar = "🟩" * 20
        final_text = f"""
✅ <b>Broadcast Completed</b> ✅

⏱ <b>Duration:</b> {time_taken}
👥 <b>Total Users:</b> {total_users}

📊 <b>Results:</b>
✅ Success: {success} ({(success/total_users)*100:.1f}%)
🚫 Blocked: {blocked} ({(blocked/total_users)*100:.1f}%)
❌ Deleted: {deleted} ({(deleted/total_users)*100:.1f}%)
⚠️ Failed: {failed} ({(failed/total_users)*100:.1f}%)

━━━━━━━━━━━━━━━━━━━━━━
{progress_bar} 100%
━━━━━━━━━━━━━━━━━━━━━━

⚡ <b>Speed:</b> {speed:.2f} users/sec
"""
        await sts.edit(final_text)

    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Broadcast Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Broadcast Error: {e}")

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
        print(f"⚠️ Clone Callback Handler Error: {e}")
        # Optionally notify user
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

API_USER = "104878628"
API_SECRET = "EGzKWZpc6CypVcogQTW49QQDH9M8zbb4"

async def check_nsfw(file_path):
    url = "https://api.sightengine.com/1.0/check.json"
    data = {
        'models': 'nudity',
        'api_user': API_USER,
        'api_secret': API_SECRET,
    }
    files = {'media': open(file_path, 'rb')}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, files=files) as resp:
            return await resp.json()

@Client.on_message(filters.group | filters.channel)
async def message_capture(client: Client, message: Message):
    try:
        me = await client.get_me()
        clone = await db.get_clone_by_id(me.id)

        selected_caption = random.choice(script.CAPTION_LIST)

        header = clone.get("header", None)
        footer = clone.get("footer", None)

        text = message.text or message.caption
        if text:
            if clone.get("word_filter", False):
                original_text = text
                text = clean_text(text)
            else:
                text = text

        if text != original_text:
            await message.edit(text)
            mesaage.reply(f"⚠️ Edited message {me.id} due to inappropriate content.")

        new_text = ""

        if header:
            new_text += f"{header}\n\n"

        if clone.get("random_caption", False):
            new_text += f"{selected_caption}\n\n{text}"
        else:
            new_text += f"{text}"

        if footer:
            new_text += f"\n\n{footer}"

        if f'{me.username}' in text:
            await message.delete()

            file_id = None
            if message.photo:
                file_id = message.photo.file_id
            elif message.video:
                file_id = message.video.file_id
            elif message.document:
                file_id = message.document.file_id

            if file_id:
                await client.send_cached_media(chat_id=message.chat.id, file_id=file_id, caption=new_text)
            else:
                await client.send_message(message.chat.id, new_text)

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

        if media_file_id:
            await db.media.update_one(
                {"bot_id": me.id, "msg_id": message.id},
                {"$set": {
                    "bot_id": me.id,
                    "msg_id": message.id,
                    "file_id": media_file_id,
                    "caption": message.caption or "",
                    "date": int(message.date.timestamp())
                }},
                upsert=True
            )

        if clone.get("media_filter", False):
            file_path = await message.download()
            result = await check_nsfw(file_path)

            nudity_score = result['nudity']['sexual_activity'] + result['nudity']['sexual_display']
            if nudity_score > 0.7:  # 70% confidence threshold
                await message.delete()
                await message.reply("⚠️ Adult content detected & deleted.")

    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Clone Unexpected Error in message_capture:\n<code>{e}</code>")
        print(f"⚠️ Clone Unexpected Error in message_capture: {e}")
