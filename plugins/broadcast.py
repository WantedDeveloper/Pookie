from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
from pyrogram import Client, filters
from config import ADMINS
import asyncio
import datetime
import time

spinner_frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

def make_color_progress_bar(success, blocked, deleted, failed, total, length=50):
    """Create high-resolution emoji color-coded progress bar (50 blocks)"""
    if total == 0:
        return "⬜" * length

    users_per_block = total / length
    bar = ""
    for i in range(length):
        block_end = (i + 1) * users_per_block
        if block_end <= success:
            bar += "🟩"
        elif block_end <= success + blocked:
            bar += "🟥"
        elif block_end <= success + blocked + deleted:
            bar += "⬛"
        elif block_end <= success + blocked + deleted + failed:
            bar += "🟨"
        else:
            bar += "⬜"
    return bar

def format_eta(done, total, start_time):
    """Estimate remaining time as hh:mm:ss"""
    if done == 0:
        return "Calculating..."
    elapsed = time.time() - start_time
    rate = elapsed / done
    remaining = rate * (total - done)
    return str(datetime.timedelta(seconds=int(remaining)))

def make_summary(success, blocked, deleted, failed, total):
    """Return a mini summary with percentage for each type"""
    if total == 0:
        return "No users"
    s_pct = (success / total) * 100
    b_pct = (blocked / total) * 100
    d_pct = (deleted / total) * 100
    f_pct = (failed / total) * 100
    return f"✅ {s_pct:.1f}% 🟩  🚫 {b_pct:.1f}% 🟥  ❌ {d_pct:.1f}% ⬛  ⚠️ {f_pct:.1f}% 🟨"

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
        return False, f"Error: {e}"

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def verupikkals(bot, message):
    admin_id = message.from_user.id

    try:
        users = await db.get_all_users()

        # Ask admin for message
        b_msg = await bot.ask(
            admin_id,
            "📩 Please send the message to broadcast.\n\nSend /cancel to stop.",
            timeout=120
        )
        if b_msg.text and b_msg.text.lower() == '/cancel':
            return await b_msg.reply("<b>🚫 Broadcast process canceled.</b>")

        sts = await bot.send_message(admin_id, "📢 **Broadcasting your message...**")

        start_time = time.time()
        total_users = await db.total_users_count()
        done = blocked = deleted = failed = success = 0
        spin_index = 0

        async for user in users:
            try:
                if 'id' in user:
                    pti, sh = await broadcast_messages(int(user['id']), b_msg)
                    if pti:
                        success += 1
                    else:
                        if sh == "Blocked":
                            blocked += 1
                        elif sh == "Deleted":
                            deleted += 1
                        else:
                            failed += 1
                else:
                    failed += 1
                done += 1

                # Calculate real-time speed (users/sec)
                elapsed = time.time() - start_time
                speed = done / elapsed if elapsed > 0 else 0

                # Update every user
                try:
                    spin_index = (spin_index + 1) % len(spinner_frames)
                    spinner = spinner_frames[spin_index]
                    eta = format_eta(done, total_users, start_time)
                    progress_bar = make_color_progress_bar(success, blocked, deleted, failed, total_users, length=50)
                    summary = make_summary(success, blocked, deleted, failed, total_users)

                    await sts.edit(
                        f"{spinner} **Broadcast in progress...**\n\n"
                        f"{progress_bar}\n"
                        f"{summary}\n\n"
                        f"👥 Total: {total_users}\n"
                        f"⏳ Done: {done}/{total_users}\n"
                        f"⏱ ETA: {eta}\n"
                        f"⚡ Speed: {speed:.2f} users/sec"
                    )
                except:
                    pass

            except Exception:
                failed += 1
                done += 1

        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        final_report = (
            f"✅ **Broadcast Completed** ✅\n\n"
            f"⏱ Time Taken: {time_taken}\n\n"
            f"{make_color_progress_bar(success, blocked, deleted, failed, total_users, length=50)}\n"
            f"{make_summary(success, blocked, deleted, failed, total_users)}\n\n"
            f"👥 Total: {total_users}\n"
            f"✅ Success: {success}\n"
            f"🚫 Blocked: {blocked}\n"
            f"❌ Deleted: {deleted}\n"
            f"⚠️ Failed: {failed}\n"
            f"⚡ Speed: {speed:.2f} users/sec"
        )

        await sts.edit(final_report)

        # Log summary to LOG_CHANNEL for all admins
        try:
            await bot.send_message(LOG_CHANNEL, f"📢 **Broadcast Summary**\n\n{final_report}")
        except:
            pass

    except Exception as e:
        await bot.send_message(LOG_CHANNEL, f"⚠️ Broadcast failed: <code>{e}</code>")