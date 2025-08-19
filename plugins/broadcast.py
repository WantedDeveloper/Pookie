from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid, TimeoutError
from pyrogram.errors import TimeoutError
from plugins.dbusers import db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import OWNERS, LOG_CHANNEL
import asyncio
import datetime
import time

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

# Track broadcast state per status message
broadcast_states = {}  # {status_msg_id: {"cancel": False, "done": 0, "success": 0, "blocked": 0, "deleted": 0, "failed": 0, "total": 0, "start_time": 0}}

# Broadcast command
@Client.on_message(filters.command("broadcast") & filters.user(OWNERS))
async def verupikkals(bot, message):
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
            except TimeoutError:
                return await message.reply("<b>⏰ Timeout! You didn’t send any message in 60s.</b>")

            if b_msg.text and b_msg.text.lower() == '/cancel':
                return await message.reply('<b>🚫 Broadcast cancelled.</b>')

        sts = await message.reply_text(
            "⏳ <b>Broadcast starting...</b>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🚫 Cancel Broadcast", callback_data=f"cancel_broadcast:{message.id}")]]
            )
        )

        # init broadcast state
        broadcast_states[sts.id] = {
            "cancel": False,
            "done": 0,
            "success": 0,
            "blocked": 0,
            "deleted": 0,
            "failed": 0,
            "total": await db.total_users_count(),
            "start_time": time.time()
        }

        state = broadcast_states[sts.id]

        async for user in users:
            if state["cancel"]:  # check cancel flag
                break

            try:
                if "id" in user:
                    pti, sh = await broadcast_messages(int(user["id"]), b_msg)
                    if pti:
                        state["success"] += 1
                    else:
                        if sh == "Blocked":
                            state["blocked"] += 1
                        elif sh == "Deleted":
                            state["deleted"] += 1
                        else:
                            state["failed"] += 1
                    state["done"] += 1

                    # Update progress every 10 users
                    if not state["done"] % 10 or state["done"] == state["total"]:
                        progress = make_progress_bar(state["done"], state["total"])
                        percent = (state["done"] / state["total"]) * 100
                        elapsed = time.time() - state["start_time"]
                        speed = state["done"] / elapsed if elapsed > 0 else 0
                        remaining = state["total"] - state["done"]
                        eta = datetime.timedelta(
                            seconds=int(remaining / speed)
                        ) if speed > 0 else "∞"

                        try:
                            await sts.edit(
                                f"""
📢 <b>Broadcast in Progress...</b>

{progress} {percent:.1f}%

👥 <b>Total:</b> {state["total"]}
✅ Success: {state["success"]}
🚫 Blocked: {state["blocked"]}
❌ Deleted: {state["deleted"]}
⚠️ Failed: {state["failed"]}

⏳ <b>ETA:</b> {eta}
⚡ <b>Speed:</b> {speed:.2f} users/sec
""",
                                reply_markup=InlineKeyboardMarkup(
                                    [[InlineKeyboardButton("🚫 Cancel Broadcast", callback_data=f"cancel_broadcast:{sts.id}")]]
                                )
                            )
                        except:
                            pass
                else:
                    state["done"] += 1
                    state["failed"] += 1
            except Exception:
                state["failed"] += 1
                state["done"] += 1
                continue

        if state["cancel"]:
            elapsed = datetime.timedelta(seconds=int(time.time() - state["start_time"]))
            await sts.edit(f"""
🚫 <b>Broadcast Cancelled</b> 🚫

⏱ Duration: {elapsed}
👥 Total Users: {state["total"]}

📊 Results So Far:
✅ Success: {state["success"]}
🚫 Blocked: {state["blocked"]}
❌ Deleted: {state["deleted"]}
⚠️ Failed: {state["failed"]}
""")
        else:
            # Final summary
            time_taken = datetime.timedelta(seconds=int(time.time()-state["start_time"]))
            speed = round(state["done"] / (time.time()-state["start_time"]), 2) if state["done"] > 0 else 0
            progress_bar = "🟩" * 20

            final_text = f"""
✅ <b>Broadcast Completed</b> ✅

⏱ Duration: {time_taken}
👥 Total Users: {state["total"]}

📊 Results:
✅ Success: {state["success"]} ({(state["success"]/state["total"])*100:.1f}%)
🚫 Blocked: {state["blocked"]} ({(state["blocked"]/state["total"])*100:.1f}%)
❌ Deleted: {state["deleted"]} ({(state["deleted"]/state["total"])*100:.1f}%)
⚠️ Failed: {state["failed"]} ({(state["failed"]/state["total"])*100:.1f}%)

━━━━━━━━━━━━━━━━━━━━━━
{progress_bar} 100%
━━━━━━━━━━━━━━━━━━━━━━

⚡ Speed: {speed} users/sec
"""
            await sts.edit(final_text)

        # cleanup
        if sts.id in broadcast_states:
            del broadcast_states[sts.id]

    except Exception as e:
        await bot.send_message(
            LOG_CHANNEL,
            f"⚠️ Broadcast Error:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )

# Cancel handler
@Client.on_callback_query()
async def cancel_broadcast_handler(bot, query):
    if query.data.startswith("cancel_broadcast"):
        _, msg_id = query.data.split(":", 1) if ":" in query.data else (None, None)
        if msg_id and msg_id.isdigit():
            msg_id = int(msg_id)
            if msg_id in broadcast_states:
                broadcast_states[msg_id]["cancel"] = True
                await query.answer("🚫 Broadcast Cancelled!", show_alert=True)
