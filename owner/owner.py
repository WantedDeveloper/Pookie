import os, logging, asyncio, re, json, base64, requests, time, datetime, motor.motor_asyncio
from validators import domain
from pyrogram import Client, filters, enums, types
from pyrogram.types import *
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from plugins.config import *
from plugins.database import db, JoinReqs
from plugins.clone_instance import set_client, get_client
from plugins.script import script
from clone.clone import auto_post_clone

logger = logging.getLogger(__name__)

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
ADD_PREMIUM = {}
AUTO_DELETE_TIME = {}
AUTO_DELETE_MESSAGE = {}
ADD_MODERATOR = {}

START_TIME = time.time()

async def is_subscribed(client, query):
    if REQUEST_TO_JOIN_MODE == True and JoinReqs().isActive():
        try:
            user = await JoinReqs().get_user(query.from_user.id)
            if user and user["user_id"] == query.from_user.id:
                return True
            else:
                try:
                    user_data = await client.get_chat_member(AUTH_CHANNEL, query.from_user.id)
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
            user = await client.get_chat_member(AUTH_CHANNEL, query.from_user.id)
        except UserNotParticipant:
            pass
        except Exception as e:
            logger.exception(e)
        else:
            if user.status != enums.ChatMemberStatus.BANNED:
                return True
        return False

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
                [InlineKeyboardButton('🌟 Buy Premium', callback_data='premium')],
                [InlineKeyboardButton('🔒 Close', callback_data='close')]
            ]
            return await message.reply_text(
                script.START_TXT.format(user=message.from_user.mention, bot=client.me.mention),
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Start Handler Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Start Handler Error: {e}")

@Client.on_message(filters.command("add_premium") & filters.user(ADMINS) & filters.private)
async def add_premium_cmd(client: Client, message: Message):
    try:
        ask_id = await client.ask(
            chat_id=message.chat.id,
            text="👤 Send the User ID to add as premium:",
            filters=filters.text,
            timeout=60
        )
        user_id = int(ask_id.text.strip())

        ask_days = await client.ask(
            chat_id=message.chat.id,
            text="📅 Send number of days for premium:",
            filters=filters.text,
            timeout=60
        )
        days = int(ask_days.text.strip())

        ask_plan = await client.ask(
            chat_id=message.chat.id,
            text="💎 Send plan type:\n\n- `normal`\n- `ultra`",
            filters=filters.text,
            timeout=60
        )
        plan = ask_plan.text.lower().strip()
        if plan not in ["normal", "ultra"]:
            return await message.reply_text("❌ Invalid plan type. Must be 'normal' or 'ultra'.")

        await db.add_premium_user(user_id, days, plan)

        expiry = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
        await message.reply_text(
            f"✅ Added **{plan.title()} Premium**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"📅 Days: {days}\n"
            f"⏳ Expiry: {expiry}"
        )

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Add Premium Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Add Premium Error: {e}")

@Client.on_message(filters.command("remove_premium") & filters.user(ADMINS) & filters.private)
async def remove_premium_cmd(client: Client, message: Message):
    try:
        ask_id = await client.ask(
            chat_id=message.chat.id,
            text="👤 Send the User ID to remove from premium:",
            filters=filters.text,
            timeout=60
        )
        
        user_id = int(ask_id.text.strip())
        user = await db.get_premium_user(user_id)
        if not user:
            return await message.reply_text(f"ℹ️ User `{user_id}` is **not premium**.")

        await db.remove_premium_user(user_id)
        await message.reply_text(f"✅ Removed premium from {user_id}.")
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Remove Premium Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Remove Premium Error: {e}")

@Client.on_message(filters.command("list_premium") & filters.user(ADMINS) & filters.private)
async def list_premium_cmd(client: Client, message: Message):
    try:
        users = await db.list_premium_users()
        if not users:
            return await message.reply_text("ℹ️ No premium users found.")

        text = "👑 **Premium Users List** 👑\n\n"
        for u in users:
            user_id = u["id"]
            plan = u.get("plan_type", "normal").title()
            expiry = u.get("expiry_time")
            if expiry:
                exp_str = expiry.strftime("%Y-%m-%d %H:%M")
                remaining = expiry - datetime.datetime.utcnow()
                days_left = remaining.days
                text += f"• `{user_id}` | {plan} | Expires: {exp_str} ({days_left} days left)\n"
            else:
                text += f"• `{user_id}` | {plan} | ❌ Expired\n"

        if len(text) > 4000:
            await message.reply_document(
                document=("premium_users.txt", text.encode("utf-8")),
                caption="📄 Premium Users List"
            )
        else:
            await message.reply_text(text)

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ List Premium Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ List Premium Error: {e}")

@Client.on_message(filters.command("check_premium") & filters.user(ADMINS) & filters.private)
async def check_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text("❌ Usage: /check_premium <user_id>")

        user_id = int(message.command[1])
        user = await db.get_premium_user(user_id)

        if not user:
            return await message.reply_text(f"ℹ️ User `{user_id}` is **not premium**.")

        plan = user.get("plan_type", "normal").title()
        expiry = user.get("expiry_time")

        if expiry and expiry > datetime.datetime.utcnow():
            remaining = expiry - datetime.datetime.utcnow()
            days_left = remaining.days
            exp_str = expiry.strftime("%Y-%m-%d %H:%M")
            await message.reply_text(
                f"👤 **User:** `{user_id}`\n"
                f"💎 **Plan:** {plan}\n"
                f"📅 **Expiry:** {exp_str}\n"
                f"⏳ **Remaining:** {days_left} days"
            )
        else:
            await message.reply_text(
                f"👤 **User:** `{user_id}`\n"
                f"💎 **Plan:** {plan}\n"
                f"❌ Premium expired."
            )

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Check Premium Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Check Premium Error: {e}")

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

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.private)
async def broadcast(client, message):
    try:
        try:
            await message.delete()
        except:
            pass

        if message.reply_to_message:
            b_msg = message.reply_to_message
        else:
            b_msg = await client.ask(
                message.chat.id,
                "📩 Send the message to broadcast\n\n/cancel to stop.",
            )

            if b_msg.text and b_msg.text.lower() == '/cancel':
                return await message.reply('🚫 Broadcast cancelled.')

        sts = await message.reply_text("⏳ Broadcast starting...")
        start_time = time.time()
        total_users = await db.total_users_count()

        done = blocked = deleted = failed = success = 0

        users = await db.get_all_users()
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

                    if done % 10 == 0 or done == total_users:
                        progress = broadcast_progress_bar(done, total_users)
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
            except Exception:
                failed += 1
                done += 1
                continue

        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        #speed = round(done / (time.time()-start_time), 2) if done > 0 else 0
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

        is_ultra = await db.is_premium(user_id, required_plan="vip")
        if is_ultra or not clones:
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

        user_id = message.from_user.id
        user_data = await db.get_premium_user(user_id)
        is_premium = bool(user_data)

        if is_premium or len(buttons_data) < 3:
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

        user_id = message.from_user.id
        user_data = await db.get_premium_user(user_id)
        is_premium = bool(user_data)
        if is_premium or len(fsub_data) < 4:
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

async def show_premium_menu(client, message, bot_id):
    try:
        clone = await db.get_clone_by_id(bot_id)
        premium_user = clone.get("premium_user", [])

        pu_list_lines = []
        for pu in premium_user:
            try:
                user_id_int = int(pu)
            except ValueError:
                user_id_int = pu

            user = await db.col.find_one({"id": user_id_int})
            name = user.get("name") if user else pu
            pu_list_lines.append(f"👤 {name} (`{pu}`)")

        pu_list_text = "\n".join(pu_list_lines)

        buttons = [
            [
                InlineKeyboardButton("➕ Add", callback_data=f"add_pu_{bot_id}"),
                InlineKeyboardButton("➖ Remove", callback_data=f"remove_premium_user_{bot_id}"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")]
        ]

        text = script.PREMIUM_TXT
        if pu_list_text:
            text += f"\n\n👥 **Current Premium Users:**\n{pu_list_text}"

        await message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Show Premium User Menu Error:\n<code>{e}</code>\nClone Data: {clone}\n\nKindly check this message to get assistance."
        )
        print(f"⚠️ Show Premium User Menu Error: {e}")

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

        buttons = [
            [
                InlineKeyboardButton("➕ Add", callback_data=f"add_moderator_{bot_id}"),
                InlineKeyboardButton("➖ Remove", callback_data=f"remove_moderator_{bot_id}"),
                InlineKeyboardButton("🔁 Transfer", callback_data=f"transfer_moderator_{bot_id}")
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{bot_id}")]
        ]

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

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

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
                [InlineKeyboardButton('🌟 Buy Premium', callback_data='premium')],
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
                 InlineKeyboardButton('🌟 Premium User', callback_data=f'premium_user_{bot_id}')],
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
            "premium_user_", "add_pu_", "cancel_addpu_", "remove_premium_user_", "remove_pu_",
            "auto_delete_", "ad_status_", "ad_time_", "edit_adtime_", "cancel_editadtime_", "see_adtime_", "default_adtime_", "ad_message_", "edit_admessage_", "cancel_editadmessage_", "see_admessage_", "default_admessage_",
            "forward_protect_", "fp_status_",
            "moderator_", "add_moderator_", "cancel_addmoderator_", "remove_moderator_", "remove_mod_", "transfer_moderator_", "transfer_mod_",
            "status_", "activate_deactivate_", "restart_", "delete_", "delete_clone_"
        ]):

            data = query.data

            action = None
            bot_id = None
            pu_id = None
            mod_id = None

            if data.startswith("remove_pu_"):
                _, _, bot_id, pu_id = data.split("_", 3)
                action = "remove_pu"
            elif data.startswith("remove_mod_"):
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
                if not await db.is_premium(user_id):
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
                    text="⏱ Please provide the new **Access Token Validity** in **hours** (e.g., `24` for 1 day):",
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
                    text="🔗 Please provide the updated **Access Token Tutorial** link:",
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

                user_data = await db.get_premium_user(user_id)
                if not user_data:
                    return await query.answer(
                        "🚫 This feature is for premium users only.\n\n"
                        "Contact @Admin to upgrade.",
                        show_alert=True
                    )

                plan_type = user_data.get("plan_type", "normal")

                if plan_type not in ["ultra", "vip"]:
                    return await query.answer(
                        "🚫 This feature is available only for ultra & vip premium users.\n\n"
                        "Upgrade to access.",
                        show_alert=True
                    )

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

                await show_premium_menu(client, query.message, bot_id)

            # Add Premium User
            elif action == "add_pu":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ADD_PREMIUM[user_id] = (query.message, bot_id)
                buttons = [[InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_addpu_{bot_id}')]]
                await query.message.edit_text(
                    text="✏️ Please provide the User ID of the new **premium user**:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Cancel Premium User
            elif action == "cancel_addpu":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                ADD_PREMIUM(user_id, None)
                await show_premium_menu(client, query.message, bot_id)

            # Remove Premium User Menu
            elif action == "remove_premium_user":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                premium_user = clone.get("premium_user", [])
                if not premium_user:
                    return await query.answer("❌ No premium user found!", show_alert=True)

                buttons = []

                for pu in premium_user:
                    try:
                        user_id_int = int(pu)
                    except ValueError:
                        user_id_int = pu

                    user = await db.col.find_one({"id": user_id_int})
                    name = user.get("name") if user else pu

                    buttons.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"remove_pu_{bot_id}_{pu}")])

                buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"premium_user_{bot_id}")])
                await query.message.edit_text(
                    "👥 Please select a **premium user** to remove from the list:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Remove Premium User
            elif action == "remove_pu":
                if not clone:
                    return await query.answer("Clone not found!", show_alert=True)

                premium_user = clone.get("premium_user", [])
                if not premium_user:
                    return await query.answer("❌ No premium user found!", show_alert=True)

                await db.update_clone(bot_id, {"$pull": {"premium_user": pu_id}}, raw=True)
                await query.answer("✅ Premium user removed!", show_alert=True)
                await show_premium_menu(client, query.message, bot_id)

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
                    text="⏱ Please provide the new **auto-delete time** in **hours** (e.g., `24` for 1 day):",
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
                    text="📄 Please provide the new **auto-delete message**:",
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
                    text="✏️ Please provide the User ID of the new **moderator**:",
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
                    "👥 Please select a **moderator** to remove from the list:",
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
                    "🔁 Please select a **moderator** to transfer ownership rights:",
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
                await db.delete_all_media()

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

        # Premium Menu
        elif query.data == "premium":
            text = (
                "💎 **Premium Features** 💎\n\n"
                "**Normal Premium:**\n"
                "- Unlimited Button\n"
                "- Unlimited FSub Channel\n\n"
                "**Ultra Premium:**\n"
                "- Unlimited Button\n"
                "- Unlimited FSub Channel\n"
                "- Auto Posting\n\n"
                "**Vip Premium:**\n"
                "- Unlimited Clone Bot\n"
                "- Unlimited Button\n"
                "- Unlimited FSub Channel\n"
                "- Auto Posting\n\n"
            )

            buttons = [
                [InlineKeyboardButton("💰 Buy Normal Premium", callback_data="buy_normal")],
                [InlineKeyboardButton("🚀 Buy Ultra Premium", callback_data="buy_ultra")],
                [InlineKeyboardButton("👑 Buy VIP Premium", callback_data="buy_vip")],
                [InlineKeyboardButton("⬅️ Back", callback_data="start")]
            ]

            await query.message.edit_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.MARKDOWN
            )

        # Payment Flow
        elif query.data in ["buy_normal", "buy_ultra", "buy_vip"]:
            if query.data == "buy_normal":
                price = "₹100"
                feature_type = "Normal Premium"
            elif query.data == "buy_ultra":
                price = "₹300"
                feature_type = "Ultra Premium"
            else:
                price = "₹500"
                feature_type = "VIP Premium"


            text = (
                f"💳 **{feature_type} Payment** 💳\n\n"
                f"Amount: {price}\n"
                "UPI ID: `your-upi@bank`\n"
                "Send payment to UPI ID\n\n"
                "After payment, click the **Payment Done** button below to confirm."
            )

            buttons = [
                [InlineKeyboardButton("✅ Payment Done", callback_data=f"paid_{feature_type.replace(' ', '_')}")],
                [InlineKeyboardButton("⬅️ Back", callback_data="premium")]
            ]

            await query.message.edit_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.MARKDOWN
            )

        # User clicked Payment Done
        elif query.data.startswith("paid_"):
            feature_type = query.data.replace("paid_", "").replace("_", " ")

            await query.message.edit_text(
                f"⏳ Payment received for **{feature_type}**.\n"
                "Waiting for admin approval...",
                parse_mode=enums.ParseMode.MARKDOWN
            )

            approve_buttons = [
                [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{feature_type.replace(' ', '_')}")],
                [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}_{feature_type.replace(' ', '_')}")]
            ]

            for admin_id in ADMINS:
                await client.send_message(
                    admin_id,
                    f"💰 Payment confirmation request:\n\n"
                    f"User: {query.from_user.mention} (`{user_id}`)\n"
                    f"Feature: {feature_type}\n\n"
                    "Click Approve or Reject:",
                    reply_markup=InlineKeyboardMarkup(approve_buttons)
                )

        # Owner approves
        elif query.data.startswith("approve_") and user_id in ADMINS:
            parts = query.data.split("_", 2)
            target_user_id = int(parts[1])
            feature_type = parts[2].replace("_", " ")

            if "Normal" in feature_type:
                plan_type = "normal"
                days = 30
            elif "Ultra" in feature_type:
                plan_type = "ultra"
                days = 30
            elif "VIP" in feature_type:
                plan_type = "vip"
                days = 30
            else:
                plan_type = "normal"
                days = 30

            expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=days)
            await db.add_premium_user(target_user_id, days, plan_type)

            await query.message.edit_text(f"✅ Payment approved for user `{target_user_id}` ({feature_type})")

            try:
                await client.send_message(
                    target_user_id,
                    f"✅ Your **{feature_type}** has been activated!\n"
                    f"Expires on: {expiry_date.strftime('%d-%m-%Y')}\n"
                    "Use /start to continue."
                )
            except:
                pass

        # Owner rejects
        elif query.data.startswith("reject_") and user_id in ADMINS:
            parts = query.data.split("_", 2)
            target_user_id = int(parts[1])
            feature_type = parts[2].replace("_", " ")

            await query.message.edit_text(f"❌ Payment rejected for user `{target_user_id}` ({feature_type})")

            try:
                await client.send_message(
                    target_user_id,
                    f"❌ Your payment for **{feature_type}** was rejected.\nContact @Admin for assistance."
                )
            except:
                pass

        # Close
        elif query.data == "close":
            await query.message.delete()
            await query.message.reply_text("❌ Menu closed. Send /start again.")

        else:
            await client.send_message(
                LOG_CHANNEL,
                f"⚠️ Unknown Callback Data Received:\n\n{query.data}\n\nUser: {query.from_user.id}\n\nKindly check this message for assistance."
            )
            await query.answer("⚠️ Unknown action.", show_alert=True)

    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"⚠️ Callback Handler Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"⚠️ Callback Handler Error: {e}")
        await query.answer("❌ An error occurred. The admin has been notified.", show_alert=True)

if SESSION_STRING and len(SESSION_STRING) > 30:
    assistant = Client(
        "assistant",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )
else:
    assistant = Client(
        "assistant",
        api_id=API_ID,
        api_hash=API_HASH
    )

async def add_clone_to_log_channel(bot_username: str):
    try:
        if not assistant.is_connected:
            await assistant.start()

        await assistant.promote_chat_member(
            LOG_CHANNEL,
            bot_username,
            privileges=types.ChatPrivileges(
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_manage_chat=True,
                can_manage_video_chats=True
            )
        )

        print(f"✅ Clone bot @{bot_username} promoted as admin in LOG_CHANNEL")

    except Exception as e:
        print(f"❌ Failed to promote clone bot @{bot_username}: {e}")

@Client.on_message(filters.all)
async def message_capture(client: Client, message: Message):
    try:
        chat = message.chat
        if chat and (chat.type == enums.ChatType.PRIVATE):
            user_id = message.from_user.id if message.from_user else None

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
                    await add_clone_to_log_channel(bot.username)
                    await client.send_message(
                        LOG_CHANNEL,
                        f"✅ New Clone Bot Created\n\n"
                        f"Bot Id: {bot.id}\n"
                        f"User Id: {user_id}\n"
                        f"Username: @{message.from_user.username}\n"
                        f"Bot Name: {bot.first_name}\n"
                        f"Bot Username: @{bot.username}\n"
                        f"Bot Token: <code>{token}</code>"
                    )
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
                    return

            # -------------------- AUTO POST --------------------
            if user_id in AUTO_POST:
                orig_msg, bot_id = AUTO_POST[user_id]
                try:
                    await message.delete()
                except:
                    pass

                new_text = message.text.strip() if message.text else ""
                if not new_text:
                    await db.update_clone(bot_id, {"auto_post": False})
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
                    await db.update_clone(bot_id, {"auto_post": False})
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
                    await db.update_clone(bot_id, {"auto_post": False})
                    await orig_msg.edit_text(f"❌ Failed to get channel info: {e}")
                    await asyncio.sleep(2)
                    await show_post_menu(client, orig_msg, bot_id)
                    AUTO_POST.pop(user_id, None)
                    return

                try:
                    me = await clone_client.get_me()
                    member = await clone_client.get_chat_member(chat.id, me.id)
                    if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                        await db.update_clone(bot_id, {"auto_post": False})
                        await orig_msg.edit_text("❌ The clone bot is NOT an admin in this channel. Add it as admin first.")
                        await asyncio.sleep(2)
                        await show_post_menu(client, orig_msg, bot_id)
                        AUTO_POST.pop(user_id, None)
                        return
                except Exception as e:
                    await db.update_clone(bot_id, {"auto_post": False})
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
        await client.send_message(LOG_CHANNEL, f"⚠️ Unexpected Error in message_capture:\n\n<code>{e}</code>\n\nKindly check this message to get assistance.")
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

            fresh = await db.get_clone_by_id(bot.id)
            if fresh and fresh.get("auto_post", False):
                target_channel = fresh.get("target_channel")
                if target_channel:
                    asyncio.create_task(
                        auto_post_clone(bot.id, db, target_channel)
                    )
                    print(f"▶️ Auto-post started for @{bot.username}")
                    
        except Exception as e:
            print(f"Error while restarting bot with token {bot.id}: {e}")
