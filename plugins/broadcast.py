from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
from pyrogram import Client, filters
from config import ADMINS, LOG_CHANNEL
import asyncio
import datetime
import time

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
        print(f"Broadcast error for {user_id}: {e}")
        return False, "Error"

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def verupikkals(bot, message):
    users_cursor = await db.get_all_users()
    b_msg = await bot.ask(message.chat.id, "📢 Send the message to broadcast.\n\nSend /cancel to stop.")

    if b_msg.text and b_msg.text.lower() == '/cancel':
        return await message.reply('<b>🚫 Broadcast canceled.</b>')

    sts = await message.reply_text(text='**Broadcasting your message...**')
    start_time = time.time()

    total_users = await db.total_users_count()
    done = success = blocked = deleted = failed = 0

    async for user in users_cursor:
        user_id = user.get("user_id")
        if not user_id:
            failed += 1
            done += 1
            continue

        pti, sh = await broadcast_messages(int(user_id), b_msg)
        if pti:
            success += 1
        else:
            if sh == "Blocked":
                blocked += 1
            elif sh == "Deleted":
                deleted += 1
            elif sh == "Error":
                failed += 1

        done += 1

        # Update progress every 20 users
        if not done % 20:
            percent = int((done / total_users) * 100)
            bar = "▓" * (percent // 10) + "░" * (10 - (percent // 10))
            try:
                await sts.edit(
                    f"📢 Broadcast in progress...\n\n"
                    f"👥 Total: {total_users}\n"
                    f"📊 Progress: {bar} {percent}%\n\n"
                    f"✅ Success: {success}\n"
                    f"⛔ Blocked: {blocked}\n"
                    f"🗑️ Deleted: {deleted}\n"
                    f"⚠️ Failed: {failed}"
                )
            except:
                pass

    # Final summary
    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))

    admin = message.from_user
    admin_name = f"{admin.first_name or ''} {admin.last_name or ''}".strip()
    admin_mention = f"<a href='tg://user?id={admin.id}'>{admin_name}</a>"

    final_report = (
        f"✅ <b>Broadcast Completed</b>\n"
        f"👤 By: {admin_mention} (<code>{admin.id}</code>)\n"
        f"🕒 Started: {datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏱️ Duration: {time_taken}\n\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Success: {success}\n"
        f"⛔ Blocked: {blocked}\n"
        f"🗑️ Deleted: {deleted}\n"
        f"⚠️ Failed: {failed}"
    )

    # Edit in user chat
    await sts.edit(final_report)

    # Also send to admin log channel with original message
    try:
        await bot.send_message(LOG_CHANNEL, final_report, disable_web_page_preview=True)
        await b_msg.copy(LOG_CHANNEL)  # copy the original broadcast message
    except Exception as e:
        print(f"Failed to send broadcast report to log channel: {e}")
