import sys
import importlib
import hashlib
from types import FunctionType
from pathlib import Path
import asyncio
import logging
import logging.config
from datetime import date, datetime
import pytz
from functools import wraps

from pyrogram import Client, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

from config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL, PORT, DEBUG_MODE, SLEEP_THRESHOLD, BOT_USERNAME
from Script import script
from TechVJ.server import web_server
from plugins.start import restart_bots
from plugins.dbusers import db  # your DB modules
from clone_plugins.dbusers import clonedb  # your DB modules

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
    no_updates=False,   # Must be False for bot to respond
    in_memory=True
)

# ---------------- Plugin Hot-Reload ----------------
PLUGIN_DIRS = [
    Path("clone_plugins"),  # Clone plugins
    Path("plugins")         # Owner plugins
]
plugin_hashes = {}  # {plugin_path: {function_name: hash}}

def func_hash(func: FunctionType) -> str:
    return hashlib.md5(func.__code__.co_code).hexdigest()

def wrap_debug(func, plugin_name):
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if DEBUG_MODE:
            print(f"🐞 Executing {plugin_name}.{func.__name__}")
        return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if DEBUG_MODE:
            print(f"🐞 Executing {plugin_name}.{func.__name__}")
        return func(*args, **kwargs)

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

def reload_plugin_functions(path: Path):
    plugin_name = path.stem
    import_path = f"{path.parent.name}.{plugin_name}"

    if import_path not in sys.modules:
        spec = importlib.util.spec_from_file_location(import_path, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[import_path] = module
        plugin_hashes[path] = {}
        for f in dir(module):
            obj = getattr(module, f)
            if isinstance(obj, FunctionType):
                wrapped = wrap_debug(obj, plugin_name)
                setattr(module, f, wrapped)
                plugin_hashes[path][f] = func_hash(obj)
        print(f"✅ Loaded new plugin: {import_path}")
        return

    module = sys.modules[import_path]
    importlib.reload(module)
    current_hashes = {}
    for f in dir(module):
        obj = getattr(module, f)
        if isinstance(obj, FunctionType):
            h = func_hash(obj)
            current_hashes[f] = h
            old_hash = plugin_hashes.get(path, {}).get(f)
            if old_hash != h:
                wrapped = wrap_debug(obj, plugin_name)
                setattr(module, f, wrapped)
                print(f"♻️ Updated function: {import_path}.{f}")
    plugin_hashes[path] = current_hashes

async def watch_plugins(interval=5):
    while True:
        for folder in PLUGIN_DIRS:
            plugin_paths = list(folder.glob("*.py"))
            for path in plugin_paths:
                reload_plugin_functions(path)
        await asyncio.sleep(interval)

# ---------------- Test Handler ----------------
@StreamBot.on_message()
async def test_ping(client, message):
    if message.text and message.text.lower() == "/ping":
        await message.reply_text("Pong ✅")

# ---------------- Main Bot Start ----------------
async def start():
    print("\nInitializing Bot...")

    # Start client first
    await StreamBot.start()
    me = await StreamBot.get_me()
    StreamBot.username = me.username
    print(f"✅ StreamBot Started: @{StreamBot.username}")

    # Load all plugins initially
    for folder in PLUGIN_DIRS:
        plugin_paths = list(folder.glob("*.py"))
        for path in plugin_paths:
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

    # Restart plugins/bots if needed
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
