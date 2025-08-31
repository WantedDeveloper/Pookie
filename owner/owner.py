import os, logging, asyncio, re, json, base64, requests, time, datetime, motor.motor_asyncio
from validators import domain
from pyrogram import Client, filters, enums
from pyrogram.types import *
from pyrogram.errors import ChatAdminRequired, InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid, ChannelInvalid, UsernameInvalid, UsernameNotModified
from plugins.config import *
from plugins.database import db
from plugins.clone_instance import set_client, get_client
from plugins.script import script
from clone.clone import auto_post_clone

class JoinReqs:

    def __init__(self):
        if DB_URI:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(OTHER_DB_URI)
            self.db = self.client["JoinReqs"]
            self.col = self.db[str(AUTH_CHANNEL)]
        else:
            self.client = None
            self.db = None
            self.col = None

    def isActive(self):
        if self.client is not None:
            return True
        else:
            return False

    async def add_user(self, user_id, first_name, username, date):
        try:
            await self.col.insert_one({"_id": int(user_id),"user_id": int(user_id), "first_name": first_name, "username": username, "date": date})
        except:
            pass

    async def get_user(self, user_id):
        return await self.col.find_one({"user_id": int(user_id)})

    async def get_all_users(self):
        return await self.col.find().to_list(None)

    async def delete_user(self, user_id):
        await self.col.delete_one({"user_id": int(user_id)})

    async def delete_all_users(self):
        await self.col.delete_many({})

    async def get_all_users_count(self):
        return await self.col.count_documents({})

join_db = JoinReqs

logger = logging.getLogger(__name__)

BATCH_FILES = {}
CLONE_TOKEN = {}
START_TEXT = {}
START_PHOTO = {}
CAPTION_TEXT = {}
ADD_BUTTON = {}
HEADER_TEXT = {}
FOOTER_TEXT = {}
ADD_FSUB = {}
ACCESS_TOKEN = {}
ACCESS_TOKEN_VALIDITY = {}
ACCESS_TOKEN_TUTORIAL = {}
AUTO_POST = {}
AUTO_DELETE_TIME = {}
AUTO_DELETE_MESSAGE = {}
ADD_MODERATOR = {}

START_TIME = time.time()

async def is_subscribed(bot, query):
    if REQUEST_TO_JOIN_MODE == True and join_db().isActive():
        try:
            user = await join_db().get_user(query.from_user.id)
            if user and user["user_id"] == query.from_user.id:
                return True
            else:
                try:
                    user_data = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
                except UserNotParticipant:
                    pass
                except Exception as e:
                    logger.exception(e)
                else:
                    if user_data.status != enums.ChatMemberStatus.BANNED:
                        return True
        except Exception as e:
            logger.exception(e)
            return False
    else:
        try:
            user = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
        except UserNotParticipant:
            pass
        except Exception as e:
            logger.exception(e)
        else:
            if user.status != enums.ChatMemberStatus.BANNED:
                return True
        return False

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
        try:
            await message.delete()
        except:
            pass

        username = client.me.username

        # --- Save user in DB ---
        if not await db.is_user_exist(message.from_user.id):
            await db.add_user(message.from_user.id, message.from_user.first_name)
            await client.send_message(
                LOG_CHANNEL,
                script.LOG_TEXT.format(message.from_user.id, message.from_user.mention)
            )

        if AUTH_CHANNEL and not await is_subscribed(client, message):
            await asyncio.sleep(2)
            if not await is_subscribed(client, message):
                if REQUEST_TO_JOIN_MODE:
                    invite_link = await client.create_chat_invite_link(chat_id=int(AUTH_CHANNEL), creates_join_request=True)
                else:
                    invite_link = await client.create_chat_invite_link(int(AUTH_CHANNEL))

                btn = [[InlineKeyboardButton("🔔 Join Channel", url=invite_link.invite_link)]]
                if len(message.command) > 1:
                    start_arg = message.command[1]
                    try:
                        kk, file_id = start_arg.split("_", 1)
                        btn.append([InlineKeyboardButton("♻️ Try Again", callback_data=f"checksub#{kk}#{file_id}")])
                    except:
                        btn.append([InlineKeyboardButton("♻️ Try Again", url=f"https://t.me/{BOT_USERNAME}?start={start_arg}")])

                return await client.send_message(
                    message.from_user.id,
                    "🚨 You must join the channel first to use this bot.",
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.MARKDOWN
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
                return await message.reply_text("❌ Invalid or expired link!", protect_content=True)

            if await check_token(client, parts[1], parts[2]):
                await verify_user(client, parts[1], parts[2])
                return await message.reply_text(
                    f"Hey {message.from_user.mention}, **verification** successful! ✅",
                    protect_content=True
                )
            else:
                return await message.reply_text("❌ Invalid or expired link!", protect_content=True)

        # --- Batch Handler ---
        if data.startswith("BATCH-"):
            if VERIFY_MODE and not await check_verification(client, message.from_user.id):
                btn = [
                    [InlineKeyboardButton("✅ Verify", url=await get_token(client, message.from_user.id, f"https://t.me/{username}?start="))],
                    [InlineKeyboardButton("ℹ️ How To Open Link & Verify", url=VERIFY_TUTORIAL)]
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
                [InlineKeyboardButton("✅ Verify", url=await get_token(client, message.from_user.id, f"https://t.me/{username}?start="))],
                [InlineKeyboardButton("ℹ️ How To Open Link & Verify", url=VERIFY_TUTORIAL)]
            ]
            return await message.reply_text(
                "🚫 You are not **verified**! Kindly **verify** to continue.",
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
        print(f"⚠️ Start Handler Error: {e}")

@Client.on_message(filters.command(['genlink']) & filters.user(ADMINS) & filters.private)
async def link(bot, message):
    try:
        try:
            await message.delete()
        except:
            pass

        username = (await bot.get_me()).username

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
                return await message.reply("⏰ Timeout! You didn’t send any message in 60s.")

            if g_msg.text and g_msg.text.lower() == '/cancel':
                return await message.reply('🚫 Process has been cancelled.')

        post = await g_msg.copy(LOG_CHANNEL)

        file_id = str(post.id)
        string = f"file_{file_id}"
        outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")

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
        print(f"⚠️ Generate Link Error: {e}")

@Client.on_message(filters.command(['batch']) & filters.user(ADMINS) & filters.private)
async def batch(bot, message):
    try:
        try:
            await message.delete()
        except:
            pass

        username = (await bot.get_me()).username

        usage_text = f"Use correct format.\nExample:\n/batch https://t.me/{username}/10 https://t.me/{username}/20"

        if " " not in message.text:
            return await message.reply(usage_text)

        links = message.text.strip().split(" ")
        if len(links) != 3:
            return await message.reply(usage_text)

        cmd, first, last = links
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")

        match = regex.match(first)
        if not match:
            return await message.reply('Invalid first link.')
        f_chat_id = match.group(4)
        f_msg_id = int(match.group(5))
        f_chat_id = int(f"-100{f_chat_id}") if f_chat_id.isnumeric() else f_chat_id

        match = regex.match(last)
        if not match:
            return await message.reply('Invalid last link.')
        l_chat_id = match.group(4)
        l_msg_id = int(match.group(5))
        l_chat_id = int(f"-100{l_chat_id}") if l_chat_id.isnumeric() else l_chat_id

        if f_chat_id != l_chat_id:
            return await message.reply("❌ Chat IDs do not match.")

        chat_id = (await bot.get_chat(f_chat_id)).id

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
        print(f"⚠️ Batch Error: {e}")

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

def make_progress_bar(done, total):
    filled = int((done / total) * 20)
    empty = 20 - filled
    return "🟩" * filled + "⬛" * empty

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.private)
async def broadcast(bot, message):
    try:
        try:
            await message.delete()
        except:
            pass

        users = await db.get_all_users()

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

    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Broadcast Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Broadcast Error: {e}")

async def show_clone_menu(client, message, user_id):
    try:
        clones = await db.get_clones_by_user(user_id)
        buttons = []

        if clones:
            for clone in clones:
                bot_name = clone.get("name", f"Clone {clone['bot_id']}")
                buttons.append([InlineKeyboardButton(
                    f'⚙️ {bot_name}', callback_data=f'manage_{clone["bot_id"]}'
                )])
        else:
            buttons.append([InlineKeyboardButton("➕ Add Clone", callback_data="add_clone")])

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
        print(f"⚠️ Show Clone Menu Error: {e}")

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
        print(f"⚠️ Show Text Menu Error: {e}")

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
        print(f"⚠️ Show Photo Menu Error: {e}")

async def show_caption_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('➕ Add', callback_data=f'add_caption_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_caption_{bot_id}'),
            InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_caption_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'start_message_{bot_id}')]
        ]
        await message.edit_text(
            text=script.CAPTION_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Caption Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Caption Menu Error: {e}")

async def show_button_menu(client, message, bot_id):
    try:
        clone = await db.get_clone_by_id(bot_id)
        buttons_data = clone.get("button", [])
        buttons = []

        for i, btn in enumerate(buttons_data):
            buttons.append(
                [InlineKeyboardButton(btn["name"], url=btn["url"]),
                  InlineKeyboardButton("❌", callback_data=f"remove_button_{i}_{bot_id}")]
            )

        if len(buttons_data) < 3:
            buttons.append([InlineKeyboardButton("➕ Add Button", callback_data=f"add_button_{bot_id}")])

        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"start_message_{bot_id}")])

        await message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Button Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Button Menu Error: {e}")

async def show_header_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('➕ Add', callback_data=f'add_header_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_header_{bot_id}'),
            InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_header_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'link_message_{bot_id}')]
        ]
        await message.edit_text(
            text=script.HEADER_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Header Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Header Menu Error: {e}")

async def show_footer_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('➕ Add', callback_data=f'add_footer_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_footer_{bot_id}'),
            InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_footer_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'link_message_{bot_id}')]
        ]
        await message.edit_text(
            text=script.FOOTER_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Footer Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Footer Menu Error: {e}")

async def show_fsub_menu(client, message, bot_id):
    try:
        clone = await db.get_clone_by_id(bot_id)
        fsub_data = clone.get("force_subscribe", [])

        buttons = []
        changed = False
        new_fsub_data = []
        text = ""

        for i, btn in enumerate(fsub_data):
            target = btn.get("limit", 0)
            joined = btn.get("joined", 0)

            if target != 0 and joined >= target:
                changed = True
                continue  

            new_fsub_data.append(btn)

        if changed:
            await db.update_clone(bot_id, {"force_subscribe": new_fsub_data})
            fsub_data = new_fsub_data

        for i, btn in enumerate(fsub_data):
            target = btn.get("limit", 0)
            joined = btn.get("joined", 0)
            ch_name = btn.get("name", "Unknown")
            ch_link = btn.get("link", None)
            mode = btn.get("mode", "normal")

            if target == 0:
                status = "♾️ Unlimited"
                progress = f"👥 {joined} joined"
            else:
                status = "⏳ Active"
                progress = f"👥 {joined}/{target}"

            text += f"**{ch_name}** ({'✅ Normal' if mode=='normal' else '📝 Request'})\n{progress} | {status}\n\n"

            row = []
            if ch_link:
                row.append(InlineKeyboardButton(ch_name, url=ch_link))
            else:
                row.append(InlineKeyboardButton(ch_name, callback_data="noop"))

            row.append(InlineKeyboardButton("❌", callback_data=f"remove_fsub_{i}_{bot_id}"))
            buttons.append(row)

        if len(fsub_data) < 4:
            buttons.append([InlineKeyboardButton("➕ Add Channel", callback_data=f"add_fsub_{bot_id}")])

        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")])

        if fsub_data:
            text = text
        else:
            text = '📢 No active Force Subscribe channels.\n\n➕ Add one below:'

        await message.edit_text(
            text=f"{script.FSUB_TXT}\n\n{text}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Force Subscribe Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Force Subscribe Menu Error: {e}")

async def show_token_menu(client, message, bot_id):
    try:
        clone = await db.get_clone_by_id(bot_id)
        current = clone.get("access_token", False)
        shorten_link = clone.get("shorten_link", None)
        shorten_api = clone.get("shorten_api", None)
        validity = clone.get("access_token_validity", 24)
        tutorial = clone.get("access_token_tutorial", None)
        renew_log = clone.get("access_token_renew_log", {})

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_count = renew_log.get(today, 0)

        if current:
            buttons = [
                [InlineKeyboardButton("⏱ Validity", callback_data=f"at_validty_{bot_id}"),
                InlineKeyboardButton("📘 Tutorial", callback_data=f"at_tutorial_{bot_id}"),
                InlineKeyboardButton("❌ Disable", callback_data=f"at_status_{bot_id}")]
            ]

            if tutorial:
                text_msg = f"📘 Tutorial: <a href='{tutorial_url}'>Click Here</a>\n"
            else:
                text_msg = f"📘 Tutorial: Not Set\n"

            status = (
                f"🟢 Enabled\n\n"
                f"🔗 Shorten Link: {shorten_link or 'Not Set'}\n"
                f"🛠 Shorten API: {shorten_api or 'Not Set'}\n"
                f"⏱ Validity: {validity} hour\n"
                f"{text_msg}"
                f"🔄 Renewed Today: {today_count} times\n\n"
            )
        else:
            buttons = []
            buttons.append([InlineKeyboardButton("✅ Enable", callback_data=f"at_status_{bot_id}")])
            status = "🔴 Disabled"

        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")])
        await message.edit_text(
            text=script.TOKEN_TXT.format(status=f"{status}"),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Token Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Token Menu Error: {e}")

async def show_validity_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('✏️ Edit', callback_data=f'edit_atvalidity_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_atvalidity_{bot_id}'),
            InlineKeyboardButton('🔄 Default', callback_data=f'default_atvalidity_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'access_token_{bot_id}')]
        ]
        await message.edit_text(
            text=script.AT_VALIDITY_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Validity Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Validity Menu Error: {e}")

async def show_tutorial_menu(client, message, bot_id):
    try:
        buttons = [
            [InlineKeyboardButton('➕ Add', callback_data=f'add_attutorial_{bot_id}'),
            InlineKeyboardButton('👁️ See', callback_data=f'see_attutorial_{bot_id}'),
            InlineKeyboardButton('🗑️ Delete', callback_data=f'delete_attutorial_{bot_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'access_token_{bot_id}')]
        ]
        await message.edit_text(
            text=script.AT_TUTORIAL_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Tutorial Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Tutorial Menu Error: {e}")

async def show_post_menu(client, message, bot_id):
    try:
        clone = await db.get_clone_by_id(bot_id)
        current = clone.get("auto_post", False)
        if current:
            buttons = [[InlineKeyboardButton("❌ Disable", callback_data=f"ap_status_{bot_id}")]]
            status = "🟢 Enabled"
        else:
            buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"ap_status_{bot_id}")]]
            status = "🔴 Disabled"

        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")])
        await message.edit_text(
            text=script.AUTO_POST_TXT.format(status=f"{status}"),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Post Menu Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Post Menu Error: {e}")

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
        print(f"⚠️ Show Time Menu Error: {e}")

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
        print(f"⚠️ Show Message Menu Error: {e}")

async def show_moderator_menu(client, message, bot_id):
    try:
        clone = await db.get_clone_by_id(bot_id)
        moderators = clone.get("moderators", [])

        # Build moderator list text
        mod_list_lines = []
        for mod in moderators:
            try:
                user_id_int = int(mod)
            except ValueError:
                user_id_int = mod

            user = await db.col.find_one({"id": user_id_int})
            name = user.get("name") if user else mod
            mod_list_lines.append(f"👤 {name} (`{mod}`)")

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
        print(f"⚠️ Show Moderator Menu Error: {e}")

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    try:
        user_id = query.from_user.id

        if query.data.startswith("checksub"):
            if AUTH_CHANNEL and not await is_subscribed(client, query):
                await query.answer("Join our channel first.", show_alert=True)
                return
            
            _, kk, file_id = query.data.split("#")
            await query.answer(url=f"https://t.me/{BOT_USERNAME}?start={kk}_{file_id}")

        # Start Menu
        elif query.data == "start":
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
            CLONE_TOKEN[user_id] = query.message
            buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_clone")]]
            await query.message.edit_text(
                text=script.CLONE_TXT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Cancel Add Clone
        elif query.data == "cancel_add_clone":
            CLONE_TOKEN.pop(user_id, None)
            await show_clone_menu(client, query.message, user_id)

        # Clone Manage Menu
        elif query.data.startswith("manage_"):
            bot_id = query.data.split("_", 1)[1]
            clone = await db.get_clone_by_id(bot_id)
            buttons = [
                [InlineKeyboardButton('📝 Start Message', callback_data=f'start_message_{bot_id}'),
                 InlineKeyboardButton('📢 Channel Message', callback_data=f'link_message_{bot_id}')],
                [InlineKeyboardButton('🔔 Force Subscribe', callback_data=f'force_subscribe_{bot_id}'),
                 InlineKeyboardButton('🔑 Access Token', callback_data=f'access_token_{bot_id}')],
                [InlineKeyboardButton('📤 Auto Post', callback_data=f'auto_post_{bot_id}'),
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
            "start_message_", "start_text_", "edit_text_", "cancel_edit_", "see_text_", "default_text_", "start_photo_", "add_photo_", "cancel_addphoto_", "see_photo_", "delete_photo_", "start_caption_", "add_caption_", "cancel_addcaption_", "see_caption_", "delete_caption_", "start_button_", "add_button_", "cancel_addbutton_", "remove_button_",
            "link_message_", "word_filter_", "wf_status_", "media_filter_", "mf_status_", "random_caption_", "rc_status_", "header_", "add_header_", "cancel_addheader_", "see_header_", "delete_header_", "footer_", "add_footer_", "cancel_addfooter_", "see_footer_", "delete_footer_",
            "force_subscribe_", "add_fsub_", "fsub_mode_", "cancel_addfsub_", "remove_fsub_",
            "access_token_", "at_status_", "cancel_at_", "at_validty_", "edit_atvalidity_", "cancel_editatvalidity_", "see_atvalidity_", "default_atvalidity_", "at_tutorial_", "add_attutorial_", "cancel_addattutorial_", "see_attutorial_", "delete_attutorial_",
            "auto_post_", "ap_status_", "cancel_autopost_",
            "premium_user_",
            "auto_delete_", "ad_status_", "ad_time_", "edit_adtime_", "cancel_editadtime_", "see_adtime_", "default_adtime_", "ad_message_", "edit_admessage_", "cancel_editadmessage_", "see_admessage_", "default_admessage_",
            "forward_protect_", "fp_status_",
            "moderator_", "add_moderator_", "cancel_addmoderator_", "remove_moderator_", "remove_mod_", "transfer_moderator_", "transfer_mod_",
            "status_", "activate_deactivate_", "restart_", "delete_", "delete_clone_"
        ]):

            data = query.data

            action = None
            bot_id = None
            mod_id = None

            if data.startswith("remove_mod_"):
                _, _, bot_id, mod_id = data.split("_", 3)
                action = "remove_mod"
            elif data.startswith("transfer_mod_"):
                _, _, bot_id, mod_id = data.split("_", 3)
                action = "transfer_mod"
            elif data.startswith("remove_button_"):
                _, _, index, bot_id = data.split("_", 3)
                action = "remove_button"
                index = int(index)
            elif data.startswith("fsub_mode_"):
                mode, bot_id = data[len("fsub_mode_"):].rsplit("_", 1)
                if mode not in ["normal", "request"]:
                    mode = "normal"
                action = "fsub_mode"
            elif data.startswith("remove_fsub_"):
                _, _, index, bot_id = data.split("_", 3)
                action = "remove_fsub"
                index = int(index)
            else:
                action, bot_id = data.rsplit("_", 1)

            clone = await db.get_clone_by_id(bot_id)

            # Start Message Menu
            if action == "start_message":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                buttons = [
                    [InlineKeyboardButton('✏️ Start Text', callback_data=f'start_text_{bot_id}'),
                     InlineKeyboardButton('🖼️ Start Photo', callback_data=f'start_photo_{bot_id}')],
                    [InlineKeyboardButton('💬 Start Caption', callback_data=f'start_caption_{bot_id}'),
                     InlineKeyboardButton('🔘 Start Button', callback_data=f'start_button_{bot_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(
                    text=script.ST_MSG_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Start Text Menu
            elif action == "start_text":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_text_menu(client, query.message, bot_id)

            # Edit Text
            elif action == "edit_text":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                START_TEXT[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_edit_{bot_id}')]]
                await query.message.edit_text(
                    text=script.EDIT_ST_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Edit Text
            elif action == "cancel_edit":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                START_TEXT.pop(user_id, None)
                await show_text_menu(client, query.message, bot_id)

            # See Start Text
            elif action == "see_text":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                start_text = clone.get("wlc", script.START_TXT)
                await query.answer(f"📝 Current Start Text:\n\n{start_text}", show_alert=True)

            # Default Start Text
            elif action == "default_text":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await db.update_clone(bot_id, {"wlc": script.START_TXT})
                await query.answer(f"🔄 Start text reset to default.", show_alert=True)

            # Start Photo Menu
            elif action == "start_photo":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                #await show_photo_menu(client, query.message, bot_id)
                await query.answer("soon...", show_alert=True)
        
            # Add Start Photo
            elif action == "add_photo":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                START_PHOTO[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_addphoto_{bot_id}')]]
                await query.message.edit_text(
                    text=script.EDIT_ST_PIC,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Add Photo
            elif action == "cancel_addphoto":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                START_PHOTO.pop(user_id, None)
                await show_photo_menu(client, query.message, bot_id)
        
            # See Start Photo
            elif action == "see_photo":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                start_photo = clone.get("pics", None)
                if start_photo:
                    await query.answer("✅ Clone bot has sent the start photo.", show_alert=True)
                else:
                    await query.answer("❌ No start photo set for this clone.", show_alert=True)

            # Delete Start Photo
            elif action == "delete_photo":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                start_photo = clone.get("pics", None)
                if start_photo:
                    await db.update_clone(bot_id, {"pics": None})
                    await query.answer("✨ Successfully deleted your clone start photo.", show_alert=True)
                else:
                    await query.answer("❌ No start photo set for this clone.", show_alert=True)

            # Caption Menu
            elif action == "start_caption":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_caption_menu(client, query.message, bot_id)

            # Add Caption
            elif action == "add_caption":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                CAPTION_TEXT[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_addcaption_{bot_id}')]]
                await query.message.edit_text(
                    text=script.EDIT_CAPTION_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Add Caption
            elif action == "cancel_addcaption":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                CAPTION_TEXT.pop(user_id, None)
                await show_caption_menu(client, query.message, bot_id)

            # See Caption
            elif action == "see_caption":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                caption = clone.get("caption", None)
                if caption:
                    await query.answer(f"📝 Current Caption Text:\n\n{caption}", show_alert=True)
                else:
                    await query.answer("❌ No caption text set for this clone.", show_alert=True)

            # Delete Caption
            elif action == "delete_caption":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                caption = clone.get("caption", None)
                if caption:
                    await db.update_clone(bot_id, {"caption": None})
                    await query.answer("✨ Successfully deleted your caption text.", show_alert=True)
                else:
                    await query.answer("❌ No caption text set for this clone.", show_alert=True)

            # Button Menu
            elif action == "start_button":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_button_menu(client, query.message, bot_id)

            # Add Button
            elif action == "add_button":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                buttons_data = clone.get("button", [])
                if len(buttons_data) >= 3:
                    return await query.answer("❌ You can only add up to 3 buttons.", show_alert=True)

                ADD_BUTTON[user_id] = {
                        "orig_msg": query.message,
                        "bot_id": bot_id,
                        "step": "name"
                    }
                buttons = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_addbutton_{bot_id}")]]
                await query.message.edit_text(
                    text=script.EDIT_BUTTON_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Button
            elif action == "cancel_addbutton":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ADD_BUTTON.pop(user_id, None)
                await show_button_menu(client, query.message, bot_id)

            # Delete Button
            elif action == "remove_button":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                buttons_data = clone.get("button", [])
                if 0 <= index < len(buttons_data):
                    deleted_btn = buttons_data.pop(index)
                    await db.update_clone(bot_id, {"button": buttons_data})
                    await query.answer(f"❌ Deleted button: {deleted_btn['name']}", show_alert=True)
                else:
                    await query.answer("Invalid button index!", show_alert=True)

                await show_button_menu(client, query.message, bot_id)

            # Link Message Menu
            elif action == "link_message":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                buttons = [
                    [InlineKeyboardButton('🚫 Word Filter', callback_data=f'word_filter_{bot_id}'),
                     InlineKeyboardButton('🎲 Random Caption', callback_data=f'random_caption_{bot_id}')],
                    [InlineKeyboardButton('🔺 Header Text', callback_data=f'header_{bot_id}'),
                     InlineKeyboardButton('🔻 Footer Text', callback_data=f'footer_{bot_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(
                    text=script.ST_MSG_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Offensive Word Filter
            elif action == "word_filter":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                current = clone.get("word_filter", False)
                if current:
                    buttons = [[InlineKeyboardButton("❌ Disable", callback_data=f"wf_status_{bot_id}")]]
                    status = "🟢 Enabled"
                else:
                    buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"wf_status_{bot_id}")]]
                    status = "🔴 Disabled"

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"link_message_{bot_id}")])
                await query.message.edit_text(
                    text=script.WORD_FILTER_TXT.format(status=f"{status}"),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Offensive Word Filter Status
            elif action == "wf_status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                new_value = not clone.get("word_filter", False)
                await db.update_clone(bot_id, {"word_filter": new_value})

                if new_value:
                    status_text = "🟢 **Offensive Word Filter** has been successfully ENABLED!"
                else:
                    status_text = "🔴 **Offensive Word Filter** has been successfully DISABLED!"

                buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=f"word_filter_{bot_id}")]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Offensive Media Filter
            elif action == "media_filter":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                current = clone.get("media_filter", False)
                if current:
                    buttons = [[InlineKeyboardButton("❌ Disable", callback_data=f"mf_status_{bot_id}")]]
                    status = "🟢 Enabled"
                else:
                    buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"mf_status_{bot_id}")]]
                    status = "🔴 Disabled"

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"link_message_{bot_id}")])
                await query.message.edit_text(
                    text=script.MEDIA_FILTER_TXT.format(status=f"{status}"),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Offensive Media Filter Status
            elif action == "mf_status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                new_value = not clone.get("media_filter", False)
                await db.update_clone(bot_id, {"media_filter": new_value})

                if new_value:
                    status_text = "🟢 **Offensive Media Filter** has been successfully ENABLED!"
                else:
                    status_text = "🔴 **Offensive Media Filter** has been successfully DISABLED!"

                buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=f"media_filter_{bot_id}")]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Random Caption
            elif action == "random_caption":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                current = clone.get("random_caption", False)
                if current:
                    buttons = [[InlineKeyboardButton("❌ Disable", callback_data=f"rc_status_{bot_id}")]]
                    status = "🟢 Enabled"
                else:
                    buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"rc_status_{bot_id}")]]
                    status = "🔴 Disabled"

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"link_message_{bot_id}")])
                await query.message.edit_text(
                    text=script.RANDOM_CAPTION_TXT.format(status=f"{status}"),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Random Caption Status
            elif action == "rc_status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                new_value = not clone.get("random_caption", False)
                await db.update_clone(bot_id, {"random_caption": new_value})

                if new_value:
                    status_text = "🟢 **Random Caption** has been successfully ENABLED!"
                else:
                    status_text = "🔴 **Random Caption** has been successfully DISABLED!"

                buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=f"random_caption_{bot_id}")]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Header Menu
            elif action == "header":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_header_menu(client, query.message, bot_id)

            # Add Header
            elif action == "add_header":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                HEADER_TEXT[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_addheader_{bot_id}')]]
                await query.message.edit_text(
                    text=script.EDIT_HEADER_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Add Header
            elif action == "cancel_addheader":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                HEADER_TEXT.pop(user_id, None)
                await show_header_menu(client, query.message, bot_id)

            # See Header
            elif action == "see_header":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                header = clone.get("header", None)
                if header:
                    await query.answer(f"📝 Current Header Text:\n\n{header}", show_alert=True)
                else:
                    await query.answer("❌ No header text set for this clone.", show_alert=True)

            # Delete Header
            elif action == "delete_header":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                header = clone.get("header", None)
                if header:
                    await db.update_clone(bot_id, {"header": None})
                    await query.answer("✨ Successfully deleted your header text.", show_alert=True)
                else:
                    await query.answer("❌ No header text set for this clone.", show_alert=True)

            # Footer Menu
            elif action == "footer":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_footer_menu(client, query.message, bot_id)

            # Add Footer
            elif action == "add_footer":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                FOOTER_TEXT[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_addfooter_{bot_id}')]]
                await query.message.edit_text(
                    text=script.EDIT_FOOTER_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Add Footer
            elif action == "cancel_addfooter":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                FOOTER_TEXT.pop(user_id, None)
                await show_footer_menu(client, query.message, bot_id)

            # See Footer
            elif action == "see_footer":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                footer = clone.get("footer", None)
                if footer:
                    await query.answer(f"📝 Current Footer Text:\n\n{footer}", show_alert=True)
                else:
                    await query.answer("❌ No footer text set for this clone.", show_alert=True)

            # Delete Footer
            elif action == "delete_footer":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                footer = clone.get("footer", None)
                if footer:
                    await db.update_clone(bot_id, {"footer": None})
                    await query.answer("✨ Successfully deleted your footer text.", show_alert=True)
                else:
                    await query.answer("❌ No footer text set for this clone.", show_alert=True)

            # Force Subscribe Menu
            elif action == "force_subscribe":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_fsub_menu(client, query.message, bot_id)

            # Add Force Subscribe
            elif action == "add_fsub":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                fsub_data = clone.get("force_subscribe", [])
                if len(fsub_data) >= 4:
                    return await query.answer("❌ You can only add up to 4 channel.", show_alert=True)

                ADD_FSUB[user_id] = {
                    "orig_msg": query.message,
                    "bot_id": bot_id,
                    "step": "channel"
                }
                buttons = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_addfsub_{bot_id}")]]
                await query.message.edit_text(
                    text=script.EDIT_FSUB_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            elif action == "fsub_mode":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                data = ADD_FSUB.get(user_id)
                if not data:
                    return await query.answer("Session expired. Please try again.", show_alert=True)

                mode = mode
                data["mode"] = mode
                bot_id = data["bot_id"]
                ch = data["channel"]
                target = data["target"]
                link = data.get("link")
                name = data.get("name", "Channel")

                await query.message.edit_text("✏️ Updating your clone's **force subscribe channel**, please wait...")
                try:
                    fsub_data = clone.get("force_subscribe", [])
                    existing = next((x for x in fsub_data if x["channel"] == ch), None)
                    if existing:
                        existing.update({
                            "name": name,
                            "limit": target,
                            "mode": mode,
                            "link": existing.get("link")
                        })
                    else:
                        fsub_data.append({
                            "channel": ch,
                            "name": name,
                            "link": None,
                            "limit": target,
                            "joined": 0,
                            "mode": mode
                        })
                    await db.update_clone(bot_id, {"force_subscribe": fsub_data})
                    await query.message.edit_text("✅ Successfully updated **force subscribe channel**!")
                    await asyncio.sleep(2)
                    await show_fsub_menu(client, query.message, bot_id)
                    ADD_FSUB.pop(user_id, None)
                except Exception as e:
                    await client.send_message(
                        LOG_CHANNEL,
                        f"⚠️ Update Force Subscribe Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
                    )
                    print(f"⚠️ Update Force Subscribe Error: {e}")
                    await query.message.edit_text(f"❌ Failed to update **force subscribe channel**: {e}")
                    await asyncio.sleep(2)
                    await show_fsub_menu(client, query.message, bot_id)
                    ADD_FSUB.pop(user_id, None)
                finally:
                    ADD_FSUB.pop(user_id, None)

            # Cancel Force Subscribe
            elif action == "cancel_addfsub":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ADD_FSUB.pop(user_id, None)
                await show_fsub_menu(client, query.message, bot_id)

            # Delete Force Subscribe
            elif action == "remove_fsub":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                fsub_data = clone.get("force_subscribe", [])
                if 0 <= index < len(fsub_data):
                    deleted_btn = fsub_data.pop(index)
                    await db.update_clone(bot_id, {"force_subscribe": fsub_data})
                    await query.answer(f"❌ Deleted Channel: {deleted_btn['name']}", show_alert=True)
                else:
                    await query.answer("Invalid Channel index!", show_alert=True)

                await show_fsub_menu(client, query.message, bot_id)

            # Access Token
            elif action == "access_token":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_token_menu(client, query.message, bot_id)

            # Access Token Status
            elif action == "at_status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                new_value = not clone.get("access_token", False)
                await db.update_clone(bot_id, {"access_token": new_value})

                if new_value:
                    ACCESS_TOKEN[user_id] = {
                        "orig_msg": query.message,
                        "bot_id": bot_id,
                        "step": "link",
                        "shorten_link": None
                    }
                    status_text = "🔗 Please send your **Shorten Link** now."
                    text = "❌ Cancel"
                    callback = f"cancel_at_{bot_id}"
                else:
                    await db.update_clone(
                        bot_id,
                        {"access_token": False, "shorten_link": None, "shorten_api": None}
                    )
                    status_text = "🔴 Access Token has been successfully DISABLED!"
                    text = "⬅️ Back"
                    callback = f"access_token_{bot_id}"

                buttons = [[InlineKeyboardButton(text, callback_data=callback)]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Access Token
            elif action == "cancel_at":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ACCESS_TOKEN.pop(user_id, None)
                await db.update_clone(bot_id, {"access_token": False})
                await show_token_menu(client, query.message, bot_id)

            # Access Token Validity Menu
            elif action == "at_validty":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_validity_menu(client, query.message, bot_id)

            # Edit Access Token Validity
            elif action == "edit_atvalidity":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ACCESS_TOKEN_VALIDITY[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editatvalidity_{bot_id}')]]
                await query.message.edit_text(
                    text="⏱ Send me the new **access token validity** in **hour** (e.g. `24` for 1 day).",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Access Token Validity
            elif action == "cancel_editatvalidity":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ACCESS_TOKEN_VALIDITY.pop(user_id, None)
                await show_validity_menu(client, query.message, bot_id)

            # See Access Token Validity
            elif action == "see_atvalidity":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                at_validity = clone.get("access_token_validity", 24)
                unit = "hour" if at_validity == 24 else "hours"
                await query.answer(f"📝 Current Access Token Validity:\n\n{at_validity} {unit}", show_alert=True)

            # Default Access Token Validity
            elif action == "default_atvalidity":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await db.update_clone(bot_id, {"access_token_validity": 24})
                await query.answer(f"🔄 Access token validity reset to default.", show_alert=True)

            # Access Token Tutorial
            elif action == "at_tutorial":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_tutorial_menu(client, query.message, bot_id)

            # Add Access Token Tutorial
            elif action == "add_attutorial":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ACCESS_TOKEN_TUTORIAL[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editadmessage_{bot_id}')]]
                await query.message.edit_text(
                    text="✏️ Send me the new **access token tutorial** link.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Access Token Tutorial
            elif action == "cancel_addattutorial":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ACCESS_TOKEN_TUTORIAL.pop(user_id, None)
                await show_tutorial_menu(client, query.message, bot_id)

            # See Access Token Tutorial
            elif action == "see_attutorial":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                at_tutorial = clone.get("access_token_tutorial", None)
                if at_tutorial:
                    await query.answer(f"📝 Current Access Token Tutorial:\n\n{at_tutorial}", show_alert=True)
                else:
                    await query.answer("❌ No access token tutorial set for this clone.", show_alert=True)

            # Delete Access Token Tutorial
            elif action == "delete_attutorial":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                at_tutorial = clone.get("access_token_tutorial", None)
                if at_tutorial:
                    await db.update_clone(bot_id, {"access_token_tutorial": None})
                    await query.answer("✨ Successfully deleted your clone access token tutorial link.", show_alert=True)
                else:
                    await query.answer("❌ No access token tutorial set for this clone.", show_alert=True)

            # Auto Post
            elif action == "auto_post":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_post_menu(client, query.message, bot_id)

            # Auto Post Status
            elif action == "ap_status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                new_value = not clone.get("auto_post", False)
                await db.update_clone(bot_id, {"auto_post": new_value})

                if new_value:
                    AUTO_POST[user_id] = (query.message, bot_id)
                    status_text = "🔗 Please send your **Target Channel I'd** now."
                    text = "❌ Cancel"
                    callback = f"cancel_autopost_{bot_id}"
                else:
                    await db.update_clone(bot_id, {"auto_post": False})
                    status_text = "🔴 Auto Post has been successfully DISABLED!"
                    text = "⬅️ Back"
                    callback = f"auto_post_{bot_id}"

                buttons = [[InlineKeyboardButton(text, callback_data=callback)]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Auto Post
            elif action == "cancel_autopost":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                AUTO_POST.pop(user_id, None)
                await db.update_clone(bot_id, {"auto_post": False})
                await show_post_menu(client, query.message, bot_id)

            # Premium User
            elif action == "premium_user":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                buttons = [[InlineKeyboardButton('⬅️ Back', callback_data=f'manage_{bot_id}')]]
                await query.message.edit_text(
                    text=script.PREMIUM_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Auto Delete Menu
            elif action == "auto_delete":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                current = clone.get("auto_delete", False)
                time_set = clone.get("auto_delete_time", 1)
                msg_set = clone.get("auto_delete_msg", script.AD_TXT)

                if current:
                    buttons = [
                        [InlineKeyboardButton("⏱ Time", callback_data=f"ad_time_{bot_id}"),
                        InlineKeyboardButton("📝 Message", callback_data=f"ad_message_{bot_id}"),
                        InlineKeyboardButton("❌ Disable", callback_data=f"ad_status_{bot_id}")]
                    ]
                    status = f"🟢 Enabled\n\n⏱ Time: {time_set} hour\n\n📝 Message: {msg_set.format(time=f'{time_set}')}"
                else:
                    buttons = [[InlineKeyboardButton("✅ Enable", callback_data=f"ad_status_{bot_id}")]]
                    status = "🔴 Disabled"

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")])
                await query.message.edit_text(
                    text=script.DELETE_TXT.format(status=f"{status}"),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Auto Delete Status
            elif action == "ad_status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

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

            # Auto Delete Time Menu
            elif action == "ad_time":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_time_menu(client, query.message, bot_id)

            # Edit Auto Delete Time
            elif action == "edit_adtime":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                AUTO_DELETE_TIME[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editadtime_{bot_id}')]]
                await query.message.edit_text(
                    text="⏱ Send me the new **auto delete time** in **hour** (e.g. `24` for 1 day).",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Auto Delete Time
            elif action == "cancel_editadtime":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                AUTO_DELETE_TIME.pop(user_id, None)
                await show_time_menu(client, query.message, bot_id)

            # See Auto Delete Time
            elif action == "see_adtime":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ad_time = clone.get("auto_delete_time", 1)
                unit = "hour" if ad_time == 1 else "hours"
                await query.answer(f"📝 Current Auto Delete Time:\n\n{ad_time} {unit}", show_alert=True)

            # Default Auto Delete Time
            elif action == "default_adtime":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await db.update_clone(bot_id, {"auto_delete_time": 1})
                await query.answer(f"🔄 Auto delete time reset to default.", show_alert=True)

            # Auto Delete Message Menu
            elif action == "ad_message":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_message_menu(client, query.message, bot_id)

            # Edit Auto Delete Message
            elif action == "edit_admessage":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                AUTO_DELETE_MESSAGE[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_editadmessage_{bot_id}')]]
                await query.message.edit_text(
                    text="✏️ Send me the new **auto delete message**.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Auto Delete Message
            elif action == "cancel_editadmessage":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                AUTO_DELETE_MESSAGE.pop(user_id, None)
                await show_message_menu(client, query.message, bot_id)

            # See Auto Delete Message
            elif action == "see_admessage":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ad_message = clone.get("auto_delete_msg", script.AD_TXT)
                await query.answer(f"📝 Current Auto Delete Message:\n\n{ad_message}", show_alert=True)

            # Default Auto Delete Message
            elif action == "default_admessage":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await db.update_clone(bot_id, {"auto_delete_msg": script.AD_TXT})
                await query.answer(f"🔄 Auto delete message reset to default.", show_alert=True)

            # Forward Protect
            elif action == "forward_protect":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

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

            # Forward Protect Status
            elif action == "fp_status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                new_value = not clone.get("forward_protect", False)
                await db.update_clone(bot_id, {"forward_protect": new_value})

                if new_value:
                    status_text = "🟢 **Forward Protect** has been successfully ENABLED!"
                else:
                    status_text = "🔴 **Forward Protect** has been successfully DISABLED!"

                buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=f"forward_protect_{bot_id}")]]
                await query.message.edit_text(
                    text=status_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Moderator Menu
            elif action == "moderator":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await show_moderator_menu(client, query.message, bot_id)

            # Add Moderator
            elif action == "add_moderator":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ADD_MODERATOR[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_addmoderator_{bot_id}')]]
                await query.message.edit_text(
                    text="✏️ Send me the new **moderator** user id.",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Moderator
            elif action == "cancel_addmoderator":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ADD_MODERATOR(user_id, None)
                await show_moderator_menu(client, query.message, bot_id)

            # Remove Moderator Menu
            elif action == "remove_moderator":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                buttons = []

                for mod in moderators:
                    try:
                        user_id_int = int(mod)
                    except ValueError:
                        user_id_int = mod

                    user = await db.col.find_one({"id": user_id_int})
                    name = user.get("name") if user else mod

                    buttons.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"remove_mod_{bot_id}_{mod}")])

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"moderator_{bot_id}")])
                await query.message.edit_text(
                    "👥 Select a moderator to remove:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Remove Moderator
            elif action == "remove_mod":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                await db.update_clone(bot_id, {"$pull": {"moderators": mod_id}}, raw=True)
                await query.answer("✅ Moderator removed!", show_alert=True)
                await show_moderator_menu(client, query.message, bot_id)

            # Transfer Moderator Menu
            elif action == "transfer_moderator":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                buttons = []

                for mod in moderators:
                    try:
                        user_id_int = int(mod)
                    except ValueError:
                        user_id_int = mod

                    user = await db.col.find_one({"id": user_id_int})
                    name = user.get("name") if user else mod

                    buttons.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"transfer_mod_{bot_id}_{mod}")])

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"moderator_{bot_id}")])
                await query.message.edit_text(
                    "🔁 Select a moderator to transfer ownership:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Transfer Moderator
            elif action == "transfer_mod":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                moderators = clone.get("moderators", [])
                if not moderators:
                    return await query.answer("❌ No moderators found!", show_alert=True)

                old_owner = int(clone.get("user_id"))
                if int(user_id) != old_owner:
                    return await query.answer("❌ Only the owner can transfer ownership!", show_alert=True)

                mod_id = int(mod_id)
                await db.update_clone(bot_id, {"$set": {"user_id": mod_id}}, raw=True)

                if str(old_owner) not in clone.get("moderators", []):
                    await db.update_clone(bot_id, {"$addToSet": {"moderators": str(old_owner)}}, raw=True)

                await db.update_clone(bot_id, {"$pull": {"moderators": str(mod_id)}}, raw=True)
                await client.send_message(
                    mod_id,
                    f"✅ You are now the owner of the bot **{clone.get('name')}** (ID: {clone.get('bot_id')})"
                )
                await query.answer("✅ Ownership transferred!", show_alert=True)
                await show_clone_menu(client, query.message, old_owner)

            # Status
            elif action == "status":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

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
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                await query.message.delete()

            # Restart
            elif action == "restart":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

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
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                buttons = [
                    [InlineKeyboardButton('✅ Yes, Sure', callback_data=f'delete_clone_{bot_id}')],
                    [InlineKeyboardButton('❌ No, Go Back', callback_data=f'manage_{bot_id}')]
                ]
                await query.message.edit_text(
                    text='⚠️ Are You Sure? Do you want **delete** your clone bot.',
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Delete Clone
            elif action == "delete_clone":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

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
        print(f"⚠️ Callback Handler Error: {e}")
        # Optionally notify user
        await query.answer("❌ An error occurred. The admin has been notified.", show_alert=True)

@Client.on_message((filters.text | filters.photo) & filters.private)
async def message_capture(client: Client, message: Message):
    try:
        user_id = message.from_user.id

        if not (
            user_id in CLONE_TOKEN
            or user_id in START_TEXT
            or user_id in START_PHOTO
            or user_id in CAPTION_TEXT
            or user_id in ADD_BUTTON
            or user_id in HEADER_TEXT
            or user_id in FOOTER_TEXT
            or user_id in ADD_FSUB
            or user_id in ACCESS_TOKEN
            or user_id in ACCESS_TOKEN_VALIDITY
            or user_id in ACCESS_TOKEN_TUTORIAL
            or user_id in AUTO_POST
            or user_id in AUTO_DELETE_TIME
            or user_id in AUTO_DELETE_MESSAGE
            or user_id in ADD_MODERATOR
        ):
            return

        # -------------------- CLONE CREATION --------------------
        if user_id in CLONE_TOKEN:
            msg = CLONE_TOKEN[user_id]
            try:
                await message.delete()
            except:
                pass

            if await db.is_clone_exist(user_id):
                await msg.edit_text("You have already cloned a **bot**. Delete it first.")
                await asyncio.sleep(2)
                await show_clone_menu(client, msg, user_id)
                CLONE_TOKEN.pop(user_id, None)
                return

            if not (message.forward_from and message.forward_from.id == 93372553):
                await msg.edit_text("❌ Please forward the BotFather message containing your **bot token**.")
                await asyncio.sleep(2)
                await show_clone_menu(client, msg, user_id)
                CLONE_TOKEN.pop(user_id, None)
                return

            try:
                token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", message.text or "")[0]
            except IndexError:
                await msg.edit_text("❌ Could not detect **bot token**. Forward the correct BotFather message.")
                await asyncio.sleep(2)
                await show_clone_menu(client, msg, user_id)
                CLONE_TOKEN.pop(user_id, None)
                return

            await msg.edit_text("👨‍💻 Creating your **bot**, please wait...")
            try:
                xd = Client(
                    f"{token}", API_ID, API_HASH,
                    bot_token=token,
                    plugins={"root": "clone"}
                )
                await xd.start()
                bot = await xd.get_me()
                set_client(bot.id, xd)
                await db.add_clone_bot(bot.id, user_id, bot.first_name, bot.username, token)
                await client.send_message(LOG_CHANNEL, f"Bot Id: <code>{bot.id}</code>\nUser Id: <code>{user_id}</code>\nBot First Name: <code>{bot.first_name}</code>\nBot Username: <code>{bot.username}</code>\nBot Token: <code>{token}</code>")
                await msg.edit_text(f"✅ Successfully cloned your **bot**: @{bot.username}")
                await asyncio.sleep(2)
                await show_clone_menu(client, msg, user_id)
                CLONE_TOKEN.pop(user_id, None)
            except Exception as e:
                await client.send_message(LOG_CHANNEL, f"⚠️ Create Bot Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")
                await msg.edit_text(f"❌ Failed to create **bot**: {e}")
                await asyncio.sleep(2)
                await show_clone_menu(client, msg, user_id)
                CLONE_TOKEN.pop(user_id, None)
            finally:
                CLONE_TOKEN.pop(user_id, None)
            return

        # -------------------- GENERIC TEXT/PHOTO HANDLERS --------------------
        handlers = [
            ("START_TEXT", START_TEXT, "text", "wlc", "show_text_menu"),
            ("START_PHOTO", START_PHOTO, "photo", "pics", "show_photo_menu"),
            ("CAPTION_TEXT", CAPTION_TEXT, "text", "caption", "show_caption_menu"),
            ("HEADER_TEXT", HEADER_TEXT, "text", "header", "show_header_menu"),
            ("FOOTER_TEXT", FOOTER_TEXT, "text", "footer", "show_footer_menu"),
            ("ACCESS_TOKEN_VALIDITY", ACCESS_TOKEN_VALIDITY, "text", "access_token_validity", "show_validity_menu"),
            ("ACCESS_TOKEN_TUTORIAL", ACCESS_TOKEN_TUTORIAL, "text", "access_token_tutorial", "show_tutorial_menu"),
            ("AUTO_DELETE_TIME", AUTO_DELETE_TIME, "text", "auto_delete_time", "show_time_menu"),
            ("AUTO_DELETE_MESSAGE", AUTO_DELETE_MESSAGE, "text", "auto_delete_msg", "show_message_menu"),
            ("ADD_MODERATOR", ADD_MODERATOR, "text", "moderators", "show_moderator_menu")
        ]

        for name, handler_dict, input_type, db_field, menu_func in handlers:
            if user_id in handler_dict:
                orig_msg, bot_id = handler_dict[user_id]
                try:
                    await message.delete()
                except:
                    pass

                if input_type == "text":
                    content = message.text.strip() if message.text else ""
                    if not content:
                        await orig_msg.edit_text("❌ Empty message. Please send a valid text.")
                        await asyncio.sleep(2)
                        await globals()[menu_func](client, orig_msg, bot_id)
                        handler_dict.pop(user_id, None)
                        return
                elif input_type == "photo":
                    if not message.photo:
                        await orig_msg.edit_text("❌ Please send a valid photo.")
                        await asyncio.sleep(2)
                        await globals()[menu_func](client, orig_msg, bot_id)
                        handler_dict.pop(user_id, None)
                        return
                    content = message.photo[-1].file_id

                await orig_msg.edit_text(f"✏️ Updating **{db_field.replace('_', ' ')}**, please wait...")
                try:
                    if db_field == "moderators":
                        clone = await db.get_clone_by_id(bot_id)
                        moderators = clone.get("moderators", [])
                        moderators.append(content)
                        await db.update_clone(bot_id, {db_field: moderators})
                    elif db_field in ["auto_delete_time", "access_token_validity"]:
                        await db.update_clone(bot_id, {db_field: int(content)})
                    else:
                        await db.update_clone(bot_id, {db_field: content})

                    await orig_msg.edit_text(f"✅ Successfully updated **{db_field.replace('_', ' ')}**!")
                    await asyncio.sleep(2)
                    await globals()[menu_func](client, orig_msg, bot_id)
                    handler_dict.pop(user_id, None)
                except Exception as e:
                    await client.send_message(LOG_CHANNEL, f"⚠️ Error updating {db_field}:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")
                    await orig_msg.edit_text(f"❌ Failed to update **{db_field.replace('_', ' ')}**: {e}")
                    await asyncio.sleep(2)
                    await globals()[menu_func](client, orig_msg, bot_id)
                    handler_dict.pop(user_id, None)
                finally:
                    handler_dict.pop(user_id, None)
                return

        # -------------------- ADD BUTTON --------------------
        if user_id in ADD_BUTTON:
            data = ADD_BUTTON[user_id]
            orig_msg, bot_id, step = data["orig_msg"], data["bot_id"], data["step"]
            try:
                await message.delete()
            except:
                pass

            new_text = message.text.strip() if message.text else ""
            if not new_text:
                await orig_msg.edit_text("❌ Empty message. Please send valid text.")
                await asyncio.sleep(2)
                await show_button_menu(client, orig_msg, bot_id)
                ADD_BUTTON.pop(user_id, None)
                return

            if step == "name":
                ADD_BUTTON[user_id]["btn_name"] = new_text
                ADD_BUTTON[user_id]["step"] = "url"
                await orig_msg.edit_text(f"✅ Button name saved: **{new_text}**\n\nNow send the URL.")
            elif step == "url":
                if not (new_text.startswith("https://") or new_text.startswith("http://")):
                    new_text = "https://" + new_text
                    await orig_msg.edit_text(f"⚠️ URL missing scheme. Automatically added `https://` → `{new_text}`")
                btn_name = data["btn_name"]
                btn_url = new_text
                await orig_msg.edit_text("✏️ Updating **start button**, please wait...")
                try:
                    clone = await db.get_clone_by_id(bot_id)
                    buttons_data = clone.get("button", [])
                    buttons_data.append({"name": btn_name, "url": btn_url})
                    await db.update_clone(bot_id, {"button": buttons_data})
                    await orig_msg.edit_text("✅ Successfully updated **start button**!")
                    await asyncio.sleep(2)
                    await show_button_menu(client, orig_msg, bot_id)
                    ADD_BUTTON.pop(user_id, None)
                except Exception as e:
                    await client.send_message(LOG_CHANNEL, f"⚠️ Update Start Button Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")
                    await orig_msg.edit_text(f"❌ Failed to update **start button**: {e}")
                    await asyncio.sleep(2)
                    await show_button_menu(client, orig_msg, bot_id)
                    ADD_BUTTON.pop(user_id, None)
                finally:
                    ADD_BUTTON.pop(user_id, None)
            return

        # -------------------- FORCE SUBSCRIBE --------------------
        if user_id in ADD_FSUB:
            data = ADD_FSUB[user_id]
            orig_msg, bot_id, step = data["orig_msg"], data["bot_id"], data["step"]
            try:
                await message.delete()
            except:
                pass

            new_text = message.text.strip() if message.text else ""
            if not new_text:
                await orig_msg.edit_text("❌ Empty message. Please send valid text.")
                await asyncio.sleep(2)
                await show_fsub_menu(client, orig_msg, bot_id)
                ADD_FSUB.pop(user_id, None)
                return

            # Steps: channel -> target -> mode
            if step == "channel":
                try:
                    channel_id_int = int(new_text)
                except ValueError:
                    channel_id_int = new_text

                clone_client = get_client(bot_id)
                if not clone_client:
                    await orig_msg.edit_text("❌ Clone bot not running, please restart it.")
                    await asyncio.sleep(2)
                    await show_fsub_menu(client, orig_msg, bot_id)
                    ADD_FSUB.pop(user_id, None)
                    return

                try:
                    chat = await clone_client.get_chat(channel_id_int)
                    ch_name = chat.title or "Unknown"
                    ch_link = f"https://t.me/{chat.username}" if chat.username else None
                except Exception as e:
                    await orig_msg.edit_text(f"❌ Failed to get channel info: {e}")
                    await asyncio.sleep(2)
                    await show_fsub_menu(client, orig_msg, bot_id)
                    ADD_FSUB.pop(user_id, None)
                    return

                try:
                    me = await clone_client.get_me()
                    member = await clone_client.get_chat_member(chat.id, me.id)
                    if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                        await orig_msg.edit_text("❌ The clone bot is NOT an admin in this channel. Add it as admin first.")
                        await asyncio.sleep(2)
                        await show_fsub_menu(client, orig_msg, bot_id)
                        ADD_FSUB.pop(user_id, None)
                        return
                except Exception as e:
                    await orig_msg.edit_text(f"❌ Failed to check clone bot in channel: {e}")
                    await asyncio.sleep(2)
                    await show_fsub_menu(client, orig_msg, bot_id)
                    ADD_FSUB.pop(user_id, None)
                    return
                
                ADD_FSUB[user_id]["channel"] = int(chat.id)
                ADD_FSUB[user_id]["name"] = ch_name
                ADD_FSUB[user_id]["link"] = ch_link
                ADD_FSUB[user_id]["step"] = "target"
                await orig_msg.edit_text(f"✅ Channel saved: `{new_text}`\n\nNow send the target number of users.")
            elif step == "target":
                try:
                    target = int(new_text)
                    if target < 0:
                        raise ValueError
                    ADD_FSUB[user_id]["target"] = target
                    ADD_FSUB[user_id]["step"] = "mode"
                    await orig_msg.edit_text(f"✅ Target saved: `{target}`\n\nNow choose the mode.")
                    buttons = [
                        [
                            InlineKeyboardButton("✅ Normal Join", callback_data=f"fsub_mode_normal_{bot_id}"),
                            InlineKeyboardButton("📝 Request Join", callback_data=f"fsub_mode_request_{bot_id}")
                        ],
                        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_addfsub_{bot_id}")]
                    ]
                    await orig_msg.edit_text(
                        f"🎯 Target saved: `{target}`\n\nNow choose the **mode** for this channel:",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except:
                    await orig_msg.edit_text("❌ Invalid number! Send 0 or a positive integer.")
                    await asyncio.sleep(2)
                    await show_fsub_menu(client, orig_msg, bot_id)
                    ADD_FSUB.pop(user_id, None)
                    return

        # -------------------- ACCESS TOKEN --------------------
        if user_id in ACCESS_TOKEN:
            data = ACCESS_TOKEN[user_id]
            orig_msg, bot_id, step = data["orig_msg"], data["bot_id"], data["step"]
            try:
                await message.delete()
            except:
                pass

            new_text = message.text.strip() if message.text else ""
            if not new_text:
                await orig_msg.edit_text("❌ Empty message. Please send valid text.")
                await asyncio.sleep(2)
                await show_token_menu(client, orig_msg, bot_id)
                ACCESS_TOKEN.pop(user_id, None)
                return

            if step == "link":
                new_text = new_text.removeprefix("https://").removeprefix("http://")
                ACCESS_TOKEN[user_id]["shorten_link"] = new_text
                ACCESS_TOKEN[user_id]["step"] = "api"
                await orig_msg.edit_text("✅ Shorten link saved! Now send your API key.")
            elif step == "api":
                await orig_msg.edit_text("✏️ Updating **access token**, please wait...")
                try:
                    await db.update_clone(bot_id, {"shorten_link": data["shorten_link"], "shorten_api": new_text})
                    await orig_msg.edit_text("✅ Successfully updated **access token**!")
                    await asyncio.sleep(2)
                    await show_token_menu(client, orig_msg, bot_id)
                    ACCESS_TOKEN.pop(user_id, None)
                except Exception as e:
                    await client.send_message(LOG_CHANNEL, f"⚠️ Update Access Token Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")
                    await orig_msg.edit_text(f"❌ Failed to update **access token**: {e}")
                    await asyncio.sleep(2)
                    await show_token_menu(client, orig_msg, bot_id)
                    ACCESS_TOKEN.pop(user_id, None)
                finally:
                    ACCESS_TOKEN.pop(user_id, None)

        # -------------------- AUTO POST --------------------
        if user_id in AUTO_POST:
            orig_msg, bot_id = AUTO_POST[user_id]
            try:
                await message.delete()
            except:
                pass

            new_text = message.text.strip() if message.text else ""
            if not new_text:
                await orig_msg.edit_text("❌ You sent an empty message. Please send a valid text.")
                await asyncio.sleep(2)
                await show_post_menu(client, orig_msg, bot_id)
                AUTO_POST.pop(user_id, None)
                return

            try:
                channel_id_int = int(new_text)
            except ValueError:
                channel_id_int = new_text

            clone_client = get_client(bot_id)
            if not clone_client:
                await orig_msg.edit_text("❌ Clone bot not running, please restart it.")
                await asyncio.sleep(2)
                await show_post_menu(client, orig_msg, bot_id)
                AUTO_POST.pop(user_id, None)
                return

            try:
                chat = await clone_client.get_chat(channel_id_int)
                ch_name = chat.title or "Unknown"
                ch_link = f"https://t.me/{chat.username}" if chat.username else None
            except Exception as e:
                await orig_msg.edit_text(f"❌ Failed to get channel info: {e}")
                await asyncio.sleep(2)
                await show_post_menu(client, orig_msg, bot_id)
                AUTO_POST.pop(user_id, None)
                return

            try:
                me = await clone_client.get_me()
                member = await clone_client.get_chat_member(chat.id, me.id)
                if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    await orig_msg.edit_text("❌ The clone bot is NOT an admin in this channel. Add it as admin first.")
                    await asyncio.sleep(2)
                    await show_post_menu(client, orig_msg, bot_id)
                    AUTO_POST.pop(user_id, None)
                    return
            except Exception as e:
                await orig_msg.edit_text(f"❌ Failed to check clone bot in channel: {e}")
                await asyncio.sleep(2)
                await show_post_menu(client, orig_msg, bot_id)
                AUTO_POST.pop(user_id, None)
                return

            await orig_msg.edit_text("✏️ Updating **auto post**, please wait...")
            try:
                await db.update_clone(bot_id, {
                    "auto_post": True,
                    "target_channel": int(chat.id)
                })
                asyncio.create_task(auto_post_clone(bot_id, db, int(chat.id)))
                await orig_msg.edit_text("✅ Successfully updated **auto post**!")
                await asyncio.sleep(2)
                await show_post_menu(client, orig_msg, bot_id)
                AUTO_POST.pop(user_id, None)
            except Exception as e:
                await client.send_message(LOG_CHANNEL, f"⚠️ Update Auto Post Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")
                await orig_msg.edit_text(f"❌ Failed to update **auto post**: {e}")
                await asyncio.sleep(2)
                await show_post_menu(client, orig_msg, bot_id)
                AUTO_POST.pop(user_id, None)
            finally:
                AUTO_POST.pop(user_id, None)
            return

    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"⚠️ Unexpected Error in message_capture:\n<code>{e}</code>")
        print(f"⚠️ Unexpected Error in message_capture: {e}")

async def restart_bots():
    bots_cursor = await db.get_all_bots()
    bots = await bots_cursor.to_list(None)
    for bot in bots:
        bot_token = bot['token']
        bot_id = bot['_id']
        try:
            xd = Client(
                name=f"clone_{bot_id}",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=bot_token,
                plugins={"root": "clone"},
            )
            await xd.start()
            bot = await xd.get_me()
            set_client(bot.id, xd)
            print(f"✅ Restarted clone bot @{bot.username} ({bot.id})")
        except Exception as e:
            print(f"Error while restarting bot with token {bot.id}: {e}")
