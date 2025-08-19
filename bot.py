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

from pyrogram import idle
from aiohttp import web
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import LOG_CHANNEL, PORT, DEBUG_MODE, BOT_USERNAME
from Script import script
from TechVJ.server import web_server
from plugins.start import restart_bots
from TechVJ.bot import StreamBot
from TechVJ.bot.clients import initialize_clients
from plugins.dbusers import db, clonedb  # make sure your db modules are imported

# ---------------- Logging Setup ----------------
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# ---------------- Plugin Setup ----------------
PLUGIN_DIR = Path("plugins")
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
    import_path = f"plugins.{plugin_name}"

    if import_path not in sys.modules:
        # First-time import
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
        print(f"✅ Loaded new plugin: {plugin_name}")
        return

    # Reload module
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
                print(f"♻️ Updated function: {plugin_name}.{f}")
    plugin_hashes[path] = current_hashes

async def watch_plugins(interval=5):
    while True:
        plugin_paths = list(PLUGIN_DIR.glob("*.py"))
        for path in plugin_paths:
            reload_plugin_functions(path)
        await asyncio.sleep(interval)

# ---------------- Main Bot Start ----------------
async def start():
    print("\nInitializing Bot...")

    # Initialize client
    await initialize_clients()

    # Import all plugins initially
    plugin_paths = list(PLUGIN_DIR.glob("*.py"))
    for path in plugin_paths:
        reload_plugin_functions(path)

    # Start plugin watcher
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

    print("Bot Started.")
    await idle()

# ---------------- Entry Point ----------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info("Service Stopped Bye 👋")
