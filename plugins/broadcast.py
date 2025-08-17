from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
from pyrogram import Client, filters
from config import ADMINS, LOG_CHANNEL
import datetime, time, asyncio

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
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def verupikkals(bot, message):
    try:
        users = await db.get_all_users()
        b_msg = await bot.ask(message.chat.id, "📩 <b>Send the message to broadcast</b>\n\n/cancel to stop.")
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
                        eta = datetime.timedelta(seconds=int(remaining / speed)) if speed > 0 else "∞"

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
            except Exception as e:
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
        try:
            await bot.send_message(LOG_CHANNEL, f"📢 **Broadcast Summary**\n\n{final_report}")
        except:
            pass

    except Exception as e:
        await bot.send_message(LOG_CHANNEL, f"⚠️ Broadcast Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance.")
