import sys
import importlib
from pathlib import Path
import asyncio
import logging
import logging.config
from datetime import date, datetime
import pytz

from pyrogram import Client, idle
from aiohttp import web

from config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL, PORT, DEBUG_MODE, SLEEP_THRESHOLD
from Script import script
from TechVJ.server import web_server
from plugins.start import restart_bots

# ---------------- Logging Setup ----------------
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# ---------------- StreamBot Client ----------------
StreamBot = Client(
    name="StreamBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=SLEEP_THRESHOLD,
    no_updates=False,   # Must be False for handlers to work
    in_memory=True
)

# ---------------- Plugin Hot-Reload ----------------
PLUGIN_DIRS = [
    Path("clone_plugins"),
    Path("plugins")
]

def reload_plugin_functions(path: Path):
    plugin_name = path.stem
    import_path = f"{path.parent.name}.{plugin_name}"

    if import_path not in sys.modules:
        spec = importlib.util.spec_from_file_location(import_path, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[import_path] = module
        print(f"✅ Loaded plugin: {import_path}")
        return

    module = sys.modules[import_path]
    importlib.reload(module)
    print(f"♻️ Reloaded plugin: {import_path}")

async def watch_plugins(interval=5):
    while True:
        for folder in PLUGIN_DIRS:
            for path in folder.glob("*.py"):
                reload_plugin_functions(path)
        await asyncio.sleep(interval)

# ---------------- Test Handler ----------------
from pyrogram import filters

@StreamBot.on_message()
async def test_ping(client, message):
    if message.text and message.text.lower() == "/ping":
        await message.reply_text("Pong ✅")

# ---------------- Main Bot Start ----------------
async def start():
    print("\nInitializing Bot...")

    # Start StreamBot client
    await StreamBot.start()
    me = await StreamBot.get_me()
    print(f"✅ StreamBot Started: @{me.username}")

    # Load all plugins initially
    for folder in PLUGIN_DIRS:
        for path in folder.glob("*.py"):
            reload_plugin_functions(path)

    # Start plugin watcher in background
    asyncio.create_task(watch_plugins(interval=5))

    # Start web server
    app = await web_server()
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

    # Send restart log
    tz = pytz.timezone("Asia/Kolkata")
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")
    await StreamBot.send_message(LOG_CHANNEL, script.RESTART_TXT.format(today, time))

    # Restart bots/plugins if needed
    await restart_bots()

    print("Bot Started and Ready ✅")
    await idle()

# ---------------- Entry Point ----------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info("Service Stopped Bye 👋")
