import asyncio
import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, SLEEP_THRESHOLD
from . import StreamBot

async def initialize_clients():
    """
    Initialize the default bot client (StreamBot).
    """
    try:
        StreamBot = Client(
            name="StreamBot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            sleep_threshold=SLEEP_THRESHOLD,
            no_updates=True,
            in_memory=True
        )
        await StreamBot.start()
        print("✅ StreamBot Client Started")
    except Exception as e:
        logging.error(f"Failed to start StreamBot: {e}", exc_info=True)
