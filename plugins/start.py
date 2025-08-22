import os, logging, asyncio, re, json, base64, requests, time, datetime, motor.motor_asyncio
from validators import domain
from pyrogram import Client, filters, enums
from pyrogram.types import *
from pyrogram.errors import ChatAdminRequired, InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid, ChannelInvalid, UsernameInvalid, UsernameNotModified
from config import *
from Script import script
from utils import verify_user, check_token, check_verification, get_token

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.bot = self.db.clone_bots
        self.settings = self.db.bot_settings

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
        )

    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def add_clone_bot(self, bot_id, user_id, first_name, username, bot_token):
        settings = {
            'is_bot': True,
            'bot_id': bot_id,
            'user_id': user_id,
            'name': first_name,
            'username': username,
            'token': bot_token,
            # Start Message
            'wlc': script.START_TXT,
            'pics': None,
            # Auto Delete
            'auto_delete': False,
            'auto_delete_time': 30,
            'auto_delete_msg': script.AD_TXT,
            # Forward Protect
            'forward_protect': False,
            # Moderators (empty list by default)
            'moderators': [],
            # Status
            'users_count': 0,
            'banned_users': [],
            'storage_used': 0,
            'storage_limit': 536870912 # 512 MB default
        }
        await self.bot.insert_one(settings)

    async def is_clone_exist(self, user_id):
        clone = await self.bot.find_one({'user_id': int(user_id)})
        return bool(clone)

    async def get_clone_by_id(self, bot_id):
        clone = await self.bot.find_one({'bot_id': int(bot_id)})
        return clone

    async def get_clones_by_user(self, user_id):
        """
        Fetch clones where user is owner (int) or a moderator (string).
        """
        clones = []
        user_id_str = str(user_id)  # moderator match as string
        try:
            user_id_int = int(user_id)  # owner match as int
        except ValueError:
            return []

        cursor = self.bot.find({
            "$or": [
                {"user_id": user_id_int},    # owner
                {"moderators": user_id_str}  # moderator
            ]
        })

        async for clone in cursor:
            clones.append(clone)

        return clones

    async def update_clone(self, bot_id, user_data):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$set': user_data}, upsert=True)

    async def update_clone(self, bot_id, user_data: dict, raw=False):
        if raw:
            await self.bot.update_one({'bot_id': int(bot_id)}, user_data, upsert=True)
        else:
            await self.bot.update_one({'bot_id': int(bot_id)}, {'$set': user_data}, upsert=True)

    async def delete_clone(self, bot_id):
        await self.bot.delete_one({'bot_id': int(bot_id)})
        #await self.settings.delete_many({'bot_id': int(bot_id)})
        #await self.settings.update_many(
            #{'bot_id': int(bot_id)},
            #{'$set': {'active': False}}  # Add or use a field like 'active' to indicate clone is deleted
        #)

    async def increment_users_count(self, bot_id):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$inc': {'users_count': 1}})

    async def add_storage_used(self, bot_id, size: int):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$inc': {'storage_used': size}})

    async def ban_user(self, bot_id, user_id):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$addToSet': {'banned_users': int(user_id)}})

    async def unban_user(self, bot_id, user_id):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$pull': {'banned_users': int(user_id)}})

    async def get_banned_users(self, bot_id):
        clone = await self.bot.find_one({'bot_id': int(bot_id)})
        return clone.get("banned_users", []) if clone else []

    async def get_bot(self, bot_id):
        bot_data = await self.bot.find_one({"bot_id": bot_id})
        return bot_data

    async def update_bot(self, bot_id, bot_data):
        await self.bot.update_one({"bot_id": bot_id}, {"$set": bot_data}, upsert=True)

    async def get_all_bots(self):
        return self.bot.find({})

    async def get_user(self, user_id):
        user_id = int(user_id)
        user = await self.db.user.find_one({"user_id": user_id})
        if not user:
            res = {
                "user_id": user_id,
                "shortener_api": None,
                "base_site": None,
            }
            await self.db.user.insert_one(res)
            user = await self.db.user.find_one({"user_id": user_id})
        return user

    async def update_user_info(self, user_id, value:dict):
        user_id = int(user_id)
        myquery = {"user_id": user_id}
        newvalues = { "$set": value }
        self.db.user.update_one(myquery, newvalues)

    async def has_premium_access(self, user_id):
        user_data = await self.get_user(user_id)
        if user_data:
            expiry_time = user_data.get("expiry_time")
            if expiry_time is None:
                # User previously used the free trial, but it has ended.
                return False
            elif isinstance(expiry_time, datetime.datetime) and datetime.datetime.now() <= expiry_time:
                return True
            else:
                await self.users.update_one({"id": user_id}, {"$set": {"expiry_time": None}})
        return False

    async def check_remaining_uasge(self, userid):
        user_id = userid
        user_data = await self.get_user(user_id)        
        expiry_time = user_data.get("expiry_time")
        # Calculate remaining time
        remaining_time = expiry_time - datetime.datetime.now()
        return remaining_time

    async def get_free_trial_status(self, user_id):
        user_data = await self.get_user(user_id)
        if user_data:
            return user_data.get("has_free_trial", False)
        return False

    async def give_free_trail(self, userid):        
        user_id = userid
        seconds = 5*60         
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        user_data = {"id": user_id, "expiry_time": expiry_time, "has_free_trial": True}
        await self.users.update_one({"id": user_id}, {"$set": user_data}, upsert=True)

    async def all_premium_users(self):
        count = await self.users.count_documents({
        "expiry_time": {"$gt": datetime.datetime.now()}
        })
        return count

db = Database(DB_URI, DB_NAME)

logger = logging.getLogger(__name__)

BATCH_FILES = {}
WAITING_FOR_TOKEN = {}
WAITING_FOR_WLC = {}
WAITING_FOR_CLONE_PHOTO = {}
WAITING_FOR_CLONE_PHOTO_MSG = {}
AUTO_DELETE_TIME = {}
AUTO_DELETE_MESSAGE = {}
ADD_MODERATOR = {}

START_TIME = time.time()

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
    file_name = '@PookieManagerBot ' + ' '.join(filter(lambda x: not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
    return file_name

@Client.on_message(filters.command("start") & filters.private & filters.incoming)
async def start(client, message):
    try:
        username = client.me.username

        # --- Save user in DB ---
        if not await db.is_user_exist(message.from_user.id):
            await db.add_user(message.from_user.id, message.from_user.first_name)
            await client.send_message(
                LOG_CHANNEL,
                script.LOG_TEXT.format(message.from_user.id, message.from_user.mention)
            )

        # If /start only (no arguments)
        if len(message.command) == 1:
            buttons = [
                [
                    InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                    InlineKeyboardButton('😊 About', callback_data='about')
                ],
                [InlineKeyboardButton('🤖 Create Your Own Clone', callback_data='clone')],
                [InlineKeyboardButton('🔒 Close', callback_data='close')]
            ]
            return await message.reply_text(
                script.START_TXT.format(user=message.from_user.mention, bot=client.me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # --- Verification Handler ---
        data = message.command[1]
        if data.startswith("verify-"):
            parts = data.split("-", 2)
            if len(parts) < 3 or str(message.from_user.id) != parts[1]:
                return await message.reply_text("<b>Invalid or expired link!</b>", protect_content=True)

            if await check_token(client, parts[1], parts[2]):
                await verify_user(client, parts[1], parts[2])
                return await message.reply_text(
                    f"<b>Hey {message.from_user.mention}, verification successful! ✅</b>",
                    protect_content=True
                )
            else:
                return await message.reply_text("<b>Invalid or expired link!</b>", protect_content=True)

        # --- Batch Handler ---
        if data.startswith("BATCH-"):
            if VERIFY_MODE and not await check_verification(client, message.from_user.id):
                btn = [
                    [InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://t.me/{username}?start="))],
                    [InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)]
                ]
                return await message.reply_text(
                    "<b>You are not verified! Kindly verify to continue.</b>",
                    protect_content=True,
                    reply_markup=InlineKeyboardMarkup(btn)
                )

            sts = await message.reply("**🔺 Please wait...**")
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

            for msg in msgs:
                channel_id = int(msg.get("channel_id"))
                msgid = msg.get("msg_id")
                info = await client.get_messages(channel_id, int(msgid))
                if info.media:
                    f_caption = info.caption or ""
                    title = formate_file_name(getattr(info, info.media.value).file_name or "")
                    size = get_size(int(getattr(info, info.media.value).file_size))
                    if BATCH_FILE_CAPTION:
                        f_caption = BATCH_FILE_CAPTION.format(
                            file_name=title or '',
                            file_size=size or '',
                            file_caption=f_caption or ''
                        )
                    await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=FORWARD_PROTECT_MODE)
                else:
                    await info.copy(chat_id=message.from_user.id, protect_content=FORWARD_PROTECT_MODE)
                await asyncio.sleep(1)
            return await sts.delete()

        # --- Single File Handler ---
        pre, decode_file_id = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii").split("_", 1)
        if VERIFY_MODE and not await check_verification(client, message.from_user.id):
            btn = [
                [InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://t.me/{username}?start="))],
                [InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)]
            ]
            return await message.reply_text(
                "<b>You are not verified! Kindly verify to continue.</b>",
                protect_content=True,
                reply_markup=InlineKeyboardMarkup(btn)
            )

        msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
        if msg.media:
            media = getattr(msg, msg.media.value)
            title = formate_file_name(media.file_name or "")
            size = get_size(media.file_size)
            f_caption = f"<code>{title}</code>"
            if CUSTOM_FILE_CAPTION:
                f_caption = CUSTOM_FILE_CAPTION.format(
                    file_name=title or '',
                    file_size=size or '',
                    file_caption=''
                )
            await msg.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=FORWARD_PROTECT_MODE)
        else:
            await msg.copy(chat_id=message.from_user.id, protect_content=FORWARD_PROTECT_MODE)

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Start Handler Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )

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

        await message.reply(
            f"Here is your link:\n\n{share_link}",
            reply_markup=reply_markup
        )

    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )

@Client.on_message(filters.command(['batch']) & filters.user(OWNERS) & filters.private)
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

        async for msg in bot.iter_messages(f_chat_id, end_id, start_id):
            tot += 1
            if og_msg % 20 == 0:
                try:
                    await sts.edit(FRMT.format(
                        total=total_msgs,
                        current=tot,
                        rem=(total_msgs - tot),
                        sts="Saving Messages"
                    ))
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

        await sts.edit(
            f"✅ Contains `{og_msg}` files.\n\nHere is your link:\n\n{share_link}",
            reply_markup=reply_markup
        )

    except ChannelInvalid:
        await message.reply('⚠️ This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        await message.reply('⚠️ Invalid Link specified.')
    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Batch Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )

# Broadcast message sender with error handler
async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Error"
    except Exception as e:
        return False, f"Error: {str(e)}"

# Progress bar generator
def make_progress_bar(done, total):
    filled = int((done / total) * 20)
    empty = 20 - filled
    return "🟩" * filled + "⬛" * empty

# Broadcast command
@Client.on_message(filters.command("broadcast") & filters.user(OWNERS) & filters.private)
async def broadcast(bot, message):
    try:
        users = await db.get_all_users()

        # 🔽 Support reply-to-message
        if message.reply_to_message:
            b_msg = message.reply_to_message
        else:
            try:
                b_msg = await bot.ask(
                    message.chat.id,
                    "📩 <b>Send the message to broadcast</b>\n\n/cancel to stop.",
                    timeout=60
                )
            except asyncio.TimeoutError:
                return await message.reply("<b>⏰ Timeout! You didn’t send any message in 60s.</b>")

            if b_msg.text and b_msg.text.lower() == '/cancel':
                return await message.reply('<b>🚫 Broadcast cancelled.</b>')

        sts = await message.reply_text("⏳ <b>Broadcast starting...</b>")
        start_time = time.time()
        total_users = await db.total_users_count()

        done = blocked = deleted = failed = success = 0

        async for user in users:
            try:
                if "id" in user:
                    pti, sh = await broadcast_messages(int(user["id"]), b_msg)
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
                        eta = datetime.timedelta(
                            seconds=int(remaining / speed)
                        ) if speed > 0 else "∞"

                        try:
                            await sts.edit(f"""
📢 <b>Broadcast in Progress...</b>

{progress} {percent:.1f}%

👥 <b>Total:</b> {total_users}
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
            except Exception:
                failed += 1
                done += 1
                continue

        # Final summary
        time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
        speed = round(done / (time.time()-start_time), 2) if done > 0 else 0
        progress_bar = "🟩" * 20

        final_text = f"""
✅ <b>Broadcast Completed</b> ✅

⏱ <b>Duration:</b> {time_taken}
👥 <b>Total Users:</b> {total_users}

📊 <b>Results:</b>
✅ <b>Success:</b> {success} ({(success/total_users)*100:.1f}%)
🚫 <b>Blocked:</b> {blocked} ({(blocked/total_users)*100:.1f}%)
❌ <b>Deleted:</b> {deleted} ({(deleted/total_users)*100:.1f}%)
⚠️ <b>Failed:</b> {failed} ({(failed/total_users)*100:.1f}%)

━━━━━━━━━━━━━━━━━━━━━━
{progress_bar} 100%
━━━━━━━━━━━━━━━━━━━━━━

⚡ <b>Speed:</b> {speed} users/sec
"""

        await sts.edit(final_text)

        # Log summary to LOG_CHANNEL for all admins
        #try:
            #await bot.send_message(LOG_CHANNEL, f"📢 **Broadcast Summary**\n\n{final_text}")
        #except:
            #pass

    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Broadcast Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )

async def show_clone_menu(client, message, user_id):
    try:
        # Fetch clones where the user is owner or moderator
        clones = await db.get_clones_by_user(user_id)
        buttons = []

        if clones:
            # ✅ Show list of accessible clones
            for clone in clones:
                bot_name = clone.get("name", f"Clone {clone['bot_id']}")
                buttons.append([InlineKeyboardButton(
                    f'⚙️ {bot_name}', callback_data=f'manage_{clone["bot_id"]}'
                )])
        else:
            # ✅ No clones accessible, show Add Clone button
            buttons.append([InlineKeyboardButton("➕ Add Clone", callback_data="add_clone")])

        # Common back button
        buttons.append([InlineKeyboardButton('⬅️ Back', callback_data='start')])

        await message.edit_text(
            script.MANAGEC_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Clone Menu Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )

async def show_text_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_text_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_text_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_text_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'start_message_{bot_id}')]
        ]
        await message.edit_text(
            text=script.ST_TXT_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Text Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )

async def show_photo_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('➕ Add', callback_data=f'add_photo_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_photo_{bot_id}'),
            InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_photo_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'start_message_{bot_id}')]
        ]
        await message.edit_text(
            text=script.ST_PIC_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Photo Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )

async def show_time_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_adtime_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_adtime_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_adtime_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'auto_delete_{bot_id}')]
        ]
        await message.edit_text(
            text=script.AD_TIME_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Time Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )

async def show_message_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_admessage_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_admessage_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_admessage_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'auto_delete_{bot_id}')]
        ]
        await message.edit_text(
            text=script.AD_MSG_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Message Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )

async def show_moderator_menu(client, message, bot_id):
    try:
        clone = await db.get_clone_by_id(bot_id)
        moderators = clone.get("moderators", [])

        # Build moderator list text
        mod_list_lines = []
        for mod in moderators:
            try:
                user_id_int = int(mod_id)
            except ValueError:
                user_id_int = mod_id

            user = await db.col.find_one({"id": user_id_int})
            name = user.get("name") if user else mod_id
            mod_list_lines.append(f"👤 {name} (`{mod_id}`)")

        mod_list_text = "\n".join(mod_list_lines)

        # Buttons
        buttons = [
            [
                InlineKeyboardButton("➕ Add", callback_data=f"add_moderator_{bot_id}"),
                InlineKeyboardButton("➖ Remove", callback_data=f"remove_moderator_{bot_id}"),
                InlineKeyboardButton("🔁 Transfer", callback_data=f"transfer_moderator_{bot_id}")
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")]
        ]

        # Menu text
        text = script.MODERATOR_TXT
        if mod_list_text:
            text += f"\n\n👥 **Current Moderators:**\n{mod_list_text}"

        await message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Moderator Menu Error:\n<code>{e}</code>\nClone Data: {clone}\n\nKindly check this message to get assistance."
        )

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
                text=script.START_TXT.format(user=query.from_user.mention, bot=me.mention),
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
                text=script.ABOUT_TXT.format(bot=me.mention),
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
                text=script.CUSTOMIZEC_TXT.format(username=f"@{clone['username']}"),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Handle per-clone actions
        elif any(query.data.startswith(prefix) for prefix in [
            "start_message_", "start_text_", "edit_text_", "cancel_edit_", "see_text_", "default_text_", "start_photo_", "add_photo_", "cancel_add_", "see_photo_", "delete_photo_",
            "force_subscribe_", "access_token_", "premium_user_",
            "auto_delete_", "ad_status_", "ad_time_", "edit_adtime_", "cancel_editadtime_", "see_adtime_", "default_adtime_", "ad_message_", "edit_admessage_", "cancel_editadmessage_", "see_admessage_", "default_admessage_",
            "forward_protect_", "fp_status_",
            "moderator_", "add_moderator_", "cancel_addmoderator_", "remove_moderator_", "remove_mod_", "transfer_moderator_", "transfer_mod_",
            "status_", "activate_deactivate_", "restart_", "delete_", "delete_clone_"
        ]):
            data = query.data

            # Default values
            action = None
            bot_id = None
            mod_id = None

            if data.startswith("remove_mod_"):
                _, _, bot_id, mod_id = data.split("_", 3)
                action = "remove_mod"
            elif data.startswith("transfer_mod_"):
                _, _, bot_id, mod_id = data.split("_", 3)
                action = "transfer_mod"
            elif data.startswith("add_moderator_"):
                _, _, bot_id = data.split("_", 2)
                action = "add_moderator"
            elif data.startswith("cancel_addmoderator_"):
                _, _, bot_id = data.split("_", 2)
                action = "cancel_addmoderator"
            elif data.startswith("remove_moderator_"):
                _, _, bot_id = data.split("_", 2)
                action = "remove_moderator"
            elif data.startswith("transfer_moderator_"):
                _, _, bot_id = data.split("_", 2)
                action = "transfer_moderator"
            else:
                # fallback: split last part as bot_id
                action, bot_id = data.rsplit("_", 1)

            clone = await db.get_clone_by_id(bot_id)

            # Start Message Menu
            if action == "start_message":
                buttons = [
                    [InlineKeyboardButton('✏️ Start Text', callback_data=f'start_text_{bot_id}'),
                     InlineKeyboardButton('🖼️ Start Photo', callback_data=f'start_photo_{bot_id}')],
                    [InlineKeyboardButton('🔺 Footer', callback_data=f'help_{bot_id}'),
                     InlineKeyboardButton('🔻 Header', callback_data=f'help_{bot_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(
                    text=script.ST_MSG_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Start Text Menu
            elif action == "start_text":
                await show_text_menu(client, query.message, bot_id)

            # Edit Text
            elif action == "edit_text":
                WAITING_FOR_WLC[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_edit_{bot_id}')]]
                await query.message.edit_text(
                    text=script.EDIT_TXT_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Edit Text
            elif action == "cancel_edit":
                WAITING_FOR_WLC.pop(user_id, None)
                await show_text_menu(client, query.message, bot_id)

            # See Start Text
            elif action == "see_text":
                start_text = clone.get("wlc", script.START_TXT)
                await query.answer(f"📝 Current Start Message:\n\n{start_text}", show_alert=True)

            # Default Start Text
            elif action == "default_text":
                await db.update_clone(bot_id, {"wlc": script.START_TXT})
                await query.answer(f"🔄 Start message reset to default.", show_alert=True)

            # Start Photo Menu
            elif action == "start_photo":
                await show_photo_menu(client, query.message, bot_id)

            # Add Photo
            elif action == "add_photo":
                WAITING_FOR_CLONE_PHOTO[user_id] = bot_id
                WAITING_FOR_CLONE_PHOTO_MSG[user_id] = query.message
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_add_{bot_id}')]]
                await query.message.edit_text(
                    text="Send your new start message photo.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Add Photo
            elif action == "cancel_add":
                WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
                WAITING_FOR_CLONE_PHOTO_MSG.pop(user_id, None)
                await show_photo_menu(client, query.message, bot_id)

            # See Start Phito
            elif action == "see_photo":
                start_photo = clone.get("pics", None)
                if start_photo:
                    await query.message.reply_photo(
                        photo=start_photo,
                        caption=f"🖼 Current Start Photo for @{clone.get('username')}"
                    )
                else:
                    await query.answer("❌ No start photo set for this clone.", show_alert=True)

            # Delete Photo
            elif action == "delete_photo":
                await db.update_clone(bot_id, {"pics": None})
                await query.answer("✨ Successfully deleted your clone start photo.", show_alert=True)

            # Force Subscribe
            elif action == "force_subscribe":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.FSUB_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Access Token
            elif action == "access_token":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.TOKEN_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Premium User
            elif action == "premium_user":
                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.PREMIUM_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Auto Delete Menu
            elif action == "auto_delete":
                current = clone.get("auto_delete", False)
                time_set = clone.get("auto_delete_time", 30)
                msg_set = clone.get("auto_delete_msg", script.AD_TXT)

                if current:
                    buttons = [
                        [InlineKeyboardButton("⏱ Time", callback_data=f"ad_time_{bot_id}"),
                        InlineKeyboardButton("📝 Message", callback_data=f"ad_message_{bot_id}"),
                        InlineKeyboardButton("❌ Disable", callback_data=f"ad_status_{bot_id}")]
                    ]
                    status = f"🟢 Enabled\n\n⏱ Time: {time_set} minutes\n📝 Msg: {msg_set.format(time=f'{time_set} minutes')}"
                else:
                    buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"ad_status_{bot_id}")]]
                    status = "🔴 Disabled"

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")])
                await query.message.edit_text(
                    text=script.DELETE_TXT.format(status=f"{status}"),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Status
            elif action == "ad_status":
                new_value = not clone.get("auto_delete", False)
                await db.update_clone(bot_id, {"auto_delete": new_value})

                if new_value:
                    status_text = "🟢 Auto Delete has been successfully ENABLED!"
                else:
                    status_text = "🔴 Auto Delete has been successfully DISABLED!"

                buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=f"auto_delete_{bot_id}")]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Time Menu
            elif action == "ad_time":
                await show_time_menu(client, query.message, bot_id)

            # Edit Message
            elif action == "edit_adtime":
                AUTO_DELETE_TIME[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editadtime_{bot_id}')]]
                await query.message.edit_text(
                    text="⏱ Send me new auto delete time in **minutes** (e.g. `60` for 1 hour).",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Message
            elif action == "cancel_editadtime":
                AUTO_DELETE_TIME.pop(user_id, None)
                await show_time_menu(client, query.message, bot_id)

            # See Message
            elif action == "see_adtime":
                ad_time = clone.get("auto_delete_time", 30)
                await query.answer(f"📝 Current Auto Delete Time:\n\n{ad_time} minutes", show_alert=True)

            # Default Time
            elif action == "default_adtime":
                await db.update_clone(bot_id, {"auto_delete_time": 30})
                await query.answer(f"🔄 Auto delete message reset to default.", show_alert=True)

            # Message Menu
            elif action == "ad_message":
                await show_message_menu(client, query.message, bot_id)

            # Edit Message
            elif action == "edit_admessage":
                AUTO_DELETE_MESSAGE[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editadmessage_{bot_id}')]]
                await query.message.edit_text(
                    text="📝 Send me the new auto delete message.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Message
            elif action == "cancel_editadmessage":
                AUTO_DELETE_MESSAGE.pop(user_id, None)
                await show_message_menu(client, query.message, bot_id)

            # See Message
            elif action == "see_admessage":
                ad_message = clone.get("auto_delete_msg", script.AD_TXT)
                await query.answer(f"📝 Current Auto Delete Message:\n\n{ad_message}", show_alert=True)

            # Default Message
            elif action == "default_admessage":
                await db.update_clone(bot_id, {"auto_delete_msg": script.AD_TXT})
                await query.answer(f"🔄 Auto delete message reset to default.", show_alert=True)

            # Forward Protect
            elif action == "forward_protect":
                current = clone.get("forward_protect", False)
                if current:
                    buttons = [[InlineKeyboardButton("❌ Disable", callback_data=f"fp_status_{bot_id}")]]
                    status = "🟢 Enabled"
                else:
                    buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"fp_status_{bot_id}")]]
                    status = "🔴 Disabled"

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")])
                await query.message.edit_text(
                    text=script.FORWARD_TXT.format(status=f"{status}"),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Status
            elif action == "fp_status":
                new_value = not clone.get("forward_protect", False)
                await db.update_clone(bot_id, {"forward_protect": new_value})

                if new_value:
                    status_text = "🟢 Forward Protect has been successfully ENABLED!"
                else:
                    status_text = "🔴 Forward Protect has been successfully DISABLED!"

                buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=f"forward_protect_{bot_id}")]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Moderator Menu
            elif action == "moderator":
                await show_moderator_menu(client, query.message, bot_id)

            # Add Moderator
            elif action == "add_moderator":
                ADD_MODERATOR[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_addmoderator_{bot_id}')]]
                await query.message.edit_text(
                    text="📝 Send me the new moderator user id.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Message
            elif action == "cancel_addmoderator":
                ADD_MODERATOR(user_id, None)
                await show_moderator_menu(client, query.message, bot_id)

            # Remove Moderator Menu
            elif action == "remove_moderator":
                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                for mod_id in moderators:
                    try:
                        user_id_int = int(mod_id)
                    except ValueError:
                        user_id_int = mod_id

                    user = await db.col.find_one({"id": user_id_int})
                    name = user.get("name") if user else mod_id

                    buttons.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"remove_mod_{bot_id}_{mod_id}")])

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"moderator_{bot_id}")])
                await query.message.edit_text(
                    "👥 Select a moderator to remove:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Remove Moderator
            elif action == "remove_mod":
                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                await db.update_clone(bot_id, {"$pull": {"moderators": mod_id}}, raw=True)
                await query.answer("✅ Moderator removed!", show_alert=True)
                await show_moderator_menu(client, query.message, bot_id)

            # Transfer Moderator Menu
            elif action == "transfer_moderator":
                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                for mod_id in moderators:
                    try:
                        user_id_int = int(mod_id)
                    except ValueError:
                        user_id_int = mod_id

                    user = await db.col.find_one({"id": user_id_int})
                    name = user.get("name") if user else mod_id

                    buttons.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"transfer_mod_{bot_id}_{mod_id}")])

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"moderator_{bot_id}")])
                await query.message.edit_text(
                    "🔁 Select a moderator to transfer ownership:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Transfer Moderator
            elif action == "transfer_mod":
                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                old_owner = int(clone.get("user_id"))
                if int(user_id) != old_owner:
                    return await query.answer("❌ Only the owner can transfer ownership!", show_alert=True)

                mod_id = int(mod_id)
                await db.update_clone(bot_id, {"user_id": mod_id}, raw=True)
                if str(old_owner) not in clone.get("moderators", []):
                    await db.update_clone(bot_id, {"$addToSet": {"moderators": str(old_owner)}}, raw=True)

                await db.update_clone(bot_id, {"$pull": {"moderators": str(mod_id)}}, raw=True)
                await query.answer("✅ Ownership transferred!", show_alert=True)
                await show_clone_menu(client, query.message, old_owner)

            # Status
            elif action == "status":
                users_count = clone.get("users_count", 0)
                storage_used = clone.get("storage_used", 0)
                storage_limit = clone.get("storage_limit", 536870912)
                storage_free = storage_limit - storage_used
                banned_users = len(clone.get("banned_users", []))

                uptime = str(datetime.timedelta(seconds=int(time.time() - START_TIME)))

                await query.answer(
                    f"📊 Status for @{clone.get('username')}\n\n"
                    f"👤 Users: {users_count}\n"
                    f"🚫 Banned: {banned_users}\n"
                    f"💾 Used: {get_size(storage_used)} / {get_size(storage_limit)}\n"
                    f"💽 Free: {get_size(storage_free)}\n"
                    f"⏱ Uptime: {uptime}\n",
                    show_alert=True
                )

            # Activate/Deactivate
            elif action == "activate_deactivate":
                await query.message.delete()

            # Restart
            elif action == "restart":
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
                await query.message.edit_text(
                    text='⚠️ Are You Sure? Do you want delete your clone bot.',
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

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
                f"⚠️ Unknown Callback Data Received:\n\n{query.data}\n\nUser: {query.from_user.id}\n\nKindly check this message for assistance."
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

@Client.on_message(filters.text | filters.photo)
async def message_capture(client: Client, message: Message):
    user_id = message.from_user.id

    # Token Capture
    if user_id in WAITING_FOR_TOKEN:
        msg = WAITING_FOR_TOKEN[user_id]

        try:
            await message.delete()
        except:
            pass

        if await db.is_clone_exist(user_id):
            await msg.edit_text("You have already cloned a bot delete first.")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
            WAITING_FOR_TOKEN.pop(user_id, None)
            return

        # Ensure forwarded from BotFather
        if not (message.forward_from and message.forward_from.id == 93372553):
            await msg.edit_text("❌ Please forward the BotFather message containing your bot token.")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
            WAITING_FOR_TOKEN.pop(user_id, None)
            return

        # Extract token
        try:
            token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", message.text or "")[0]
        except IndexError:
            await msg.edit_text("❌ Could not detect bot token. Please forward the correct BotFather message.")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
            WAITING_FOR_TOKEN.pop(user_id, None)
            return

        # Create bot
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

            await msg.edit_text(f"✅ Successfully cloned your bot: @{bot.username}")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
        except Exception as e:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Create Bot Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
           )
            await msg.edit_text(f"❌ Failed to create bot: {e}")
            await asyncio.sleep(2)
            await show_clone_menu(client, msg, user_id)
        finally:
            WAITING_FOR_TOKEN.pop(user_id, None)
        return

    # Start Text Handler
    if user_id in WAITING_FOR_WLC:
        orig_msg, bot_id = WAITING_FOR_WLC[user_id]

        try:
            await message.delete()
        except:
            pass

        new_text = message.text.strip() if message.text else ""
        if not new_text:
            await orig_msg.edit_text("❌ You sent an empty message. Please send a valid start text.")
            await asyncio.sleep(2)
            await show_text_menu(client, orig_msg, bot_id)
            WAITING_FOR_WLC.pop(user_id, None)
            return

        await orig_msg.edit_text("✏️ Updating your clone's start text, please wait...")
        try:
            await db.update_clone(bot_id, {"wlc": new_text})
            await orig_msg.edit_text("✅ Successfully updated start text!")
            await asyncio.sleep(1)
            await show_text_menu(client, orig_msg, bot_id)
        except Exception as e:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Update Start Text Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
            )
            await orig_msg.edit_text(f"❌ Failed to update start text: {e}")
            await asyncio.sleep(2)
            await show_text_menu(client, orig_msg, bot_id)
        finally:
            WAITING_FOR_WLC.pop(user_id, None)
        return

    # Start Photo Handler
    if user_id in WAITING_FOR_CLONE_PHOTO:
        bot_id = WAITING_FOR_CLONE_PHOTO[user_id]
        orig_msg = WAITING_FOR_CLONE_PHOTO_MSG[user_id]

        try:
            await message.delete()
        except:
            pass

        if not message.photo:
            await orig_msg.edit_text("❌ Please send a valid photo for your clone.")
            await asyncio.sleep(2)
            await show_photo_menu(client, orig_msg, bot_id)
            WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
            WAITING_FOR_CLONE_PHOTO_MSG.pop(user_id, None)
            return

        await orig_msg.edit_text("📸 Updating your clone's photo, please wait...")
        try:
            os.makedirs("photos", exist_ok=True)  # ensure folder exists
            file_path = await message.download(f"photos/{bot_id}.jpg")
            await db.update_clone(bot_id, {"pics": file_path})
            await orig_msg.edit_text("✅ Successfully updated the start photo!")
            await asyncio.sleep(2)
            await show_photo_menu(client, orig_msg, bot_id)
        except Exception as e:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Update Photo Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
            )
            await orig_msg.edit_text(f"❌ Failed to update start photo: {e}")
        finally:
            WAITING_FOR_CLONE_PHOTO.pop(user_id, None)
            WAITING_FOR_CLONE_PHOTO_MSG.pop(user_id, None)
        return

    # Auto Delete Time Handler
    if user_id in AUTO_DELETE_TIME:
        orig_msg, bot_id = AUTO_DELETE_TIME[user_id]

        try:
            await message.delete()
        except:
            pass

        new_text = message.text.strip() if message.text else ""
        if not new_text:
            await orig_msg.edit_text("❌ You sent an empty message. Please send a valid start text.")
            await asyncio.sleep(2)
            await show_time_menu(client, orig_msg, bot_id)
            AUTO_DELETE_TIME.pop(user_id, None)
            return

        await orig_msg.edit_text("✏️ Updating your clone's auto delete time, please wait...")
        try:
            await db.update_clone(bot_id, {"auto_delete_time": new_text})
            await orig_msg.edit_text("✅ Successfully updated auto delete time!")
            await asyncio.sleep(1)
            await show_time_menu(client, orig_msg, bot_id)
        except Exception as e:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Update Auto Delete Time Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
            )
            await orig_msg.edit_text(f"❌ Failed to update auto delete time: {e}")
            await asyncio.sleep(2)
            await show_time_menu(client, orig_msg, bot_id)
        finally:
            AUTO_DELETE_TIME.pop(user_id, None)
        return

    # Auto Delete Message Handler
    if user_id in AUTO_DELETE_MESSAGE:
        orig_msg, bot_id = AUTO_DELETE_MESSAGE[user_id]

        try:
            await message.delete()
        except:
            pass

        new_text = message.text.strip() if message.text else ""
        if not new_text:
            await orig_msg.edit_text("❌ You sent an empty message. Please send a valid start text.")
            await asyncio.sleep(2)
            await show_message_menu(client, orig_msg, bot_id)
            AUTO_DELETE_MESSAGE.pop(user_id, None)
            return

        await orig_msg.edit_text("✏️ Updating your clone's auto delete message, please wait...")
        try:
            await db.update_clone(bot_id, {"auto_delete_msg": new_text})
            await orig_msg.edit_text("✅ Successfully updated auto delete message!")
            await asyncio.sleep(1)
            await show_message_menu(client, orig_msg, bot_id)
        except Exception as e:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Update Auto Delete Message Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
            )
            await orig_msg.edit_text(f"❌ Failed to update auto delete message: {e}")
            await asyncio.sleep(2)
            await show_message_menu(client, orig_msg, bot_id)
        finally:
            AUTO_DELETE_MESSAGE.pop(user_id, None)
        return

    # Add Moderator Handler
    if user_id in ADD_MODERATOR:
        orig_msg, bot_id = ADD_MODERATOR[user_id]

        try:
            await message.delete()
        except:
            pass

        new_text = message.text.strip() if message.text else ""
        if not new_text:
            await orig_msg.edit_text("❌ You sent an empty message. Please send a valid start text.")
            await asyncio.sleep(2)
            await show_moderator_menu(client, orig_msg, bot_id)
            ADD_MODERATOR.pop(user_id, None)
            return

        await orig_msg.edit_text("✏️ Updating your clone's moderator, please wait...")
        try:
            await db.update_clone(bot_id, {"$addToSet": {"moderators": new_text}}, raw=True)
            await orig_msg.edit_text("✅ Successfully updated moderator!")
            await asyncio.sleep(1)
            await show_moderator_menu(client, orig_msg, bot_id)
        except Exception as e:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Update Moderator Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
            )
            await orig_msg.edit_text(f"❌ Failed to update moderator: {e}")
            await asyncio.sleep(2)
            await show_moderator_menu(client, orig_msg, bot_id)
        finally:
            ADD_MODERATOR.pop(user_id, None)
        return

async def restart_bots():
    bots_cursor = await db.get_all_bots()
    bots = await bots_cursor.to_list(None)
    for bot in bots:
        bot_token = bot['token']
        try:
            xd = Client(
                f"{bot_token}", API_ID, API_HASH,
                bot_token=bot_token,
                plugins={"root": "clone_plugins"},
            )
            await xd.start()
        except Exception as e:
            print(f"Error while restarting bot with token {bot_token}: {e}")
