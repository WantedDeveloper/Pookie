import os, logging, asyncio, re, json, base64, requests, time, datetime, motor.motor_asyncio
from validators import domain
from pyrogram import Client, filters, enums
from pyrogram.types import *
from pyrogram.errors import ChatAdminRequired, InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid, ChannelInvalid, UsernameInvalid, UsernameNotModified
from config import *
from Script import script
from plugins.start import db

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

def get_size(size):
    """Get size in readable format"""

    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

async def auto_delete_message(client, msg, delay, ad_msg):
    try:
        await asyncio.sleep(delay)
        await msg.delete()
        await client.send_message(msg.chat.id, ad_msg)
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Auto Delete Message Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )

@Client.on_message(filters.command("start") & filters.private & filters.incoming)
async def start(client, message):
    try:
        me = await client.get_me()

        # --- Track new users ---
        if not await clonedb.is_user_exist(me.id, message.from_user.id):
            await clonedb.add_user(me.id, message.from_user.id)
            await db.increment_users_count(me.id)

        # --- No extra args: Show start menu ---
        if len(message.command) == 1:
            buttons = [[
                InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                InlineKeyboardButton('😊 About', callback_data='about')
                ],[
                InlineKeyboardButton('🤖 Create Your Own Clone', url=f'https://t.me/{BOT_USERNAME}?start')
                ],[
                InlineKeyboardButton('🔒 Close', callback_data='close')
            ]]

            clone = await db.get_bot(me.id)
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
                    await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=clone.get("forward_protect"))
                else:
                    await info.copy(chat_id=message.from_user.id, protect_content=clone.get("forward_protect"))
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
            await msg.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=clone.get("forward_protect"))
            await db.add_storage_used(me.id, file.file_size)
        else:
            await msg.copy(chat_id=message.from_user.id, protect_content=clone.get("forward_protect"))
            await db.add_storage_used(me.id, file.file_size)

        # Auto-delete if enabled
        clone = await db.get_bot(me.id)
        if clone and clone.get("auto_delete", False):
            ad_time = clone.get("auto_delete_time", 30)
            ad_msg = clone.get("auto_delete_msg", script.AD_TXT)
            asyncio.create_task(auto_delete_message(client, msg, ad_time, ad_msg.format(time=f"{ad_time} minutes")))

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Start Bot Error:\n\n<code>{e}</code>"
        )
        print(f"⚠️ Clone Start Bot Error: {e}")

async def get_short_link(user, link):
    api_key = user["shortener_api"]
    base_site = user["base_site"]
    print(user)
    response = requests.get(f"https://{base_site}/api?api={api_key}&url={link}")
    data = response.json()
    if data["status"] == "success" or rget.status_code == 200:
        return data["shortenedUrl"]

@Client.on_message(filters.command(['genlink']) & filters.user(ADMINS) & filters.private)
async def link(bot, message):
    try:
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


        string = f"msg_{message.id}"
        outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")

        # Get user info
        user_id = message.from_user.id
        user = await clonedb.get_user(user_id)

        # Bot username and share link
        bot_username = (await bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={outstr}"

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
            f"⚠️ Clone Generate Link Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Generate Link Error: {e}")

@Client.on_message(filters.command(['batch']) & filters.user(ADMINS) & filters.private)
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

            file = {
                "channel_id": f_chat_id,
                "msg_id": msg.id
            }
            og_msg += 1
            outlist.append(file)

        # Convert to file_id
        string = json.dumps(outlist)
        file_id = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")

        user_id = message.from_user.id
        user = await clonedb.get_user(user_id)
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
        await message.reply('⚠️ Invalid link specified.')
    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Clone Batch Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Clone Batch Error: {e}")

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

        # Start Menu
        if query.data == "start":
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
