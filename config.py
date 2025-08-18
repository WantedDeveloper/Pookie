import re, os
from Script import script

def is_enabled(value, default):
    try:
        if value.lower() in ["true", "yes", "1", "enable", "y"]:
            return True
        elif value.lower() in ["false", "no", "0", "disable", "n"]:
            return False
        else:
            return default
    except Exception as e:
        print("⚠️ Error in is_enabled:", e)
        return default

try:
    id_pattern = re.compile(r'^.\d+$')

    PORT = os.environ.get("PORT", "8080")

    # Bot Information
    API_ID = int(os.environ.get("API_ID", "15479023"))
    API_HASH = os.environ.get("API_HASH", "f8f6cf547822449c29fc60dae3b31dd4")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "7845374433:AAGsstCb801Ry-pQSNF-gNbdARqZqKH913I")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "Testaf1bot") # without @

    # Database Information
    DB_URI = os.environ.get("DB_URI", "mongodb+srv://test:test123@test.eccvyc9.mongodb.net/?retryWrites=true&w=majority&appName=test")
    DB_NAME = os.environ.get("DB_NAME", "techvjbotz")

    # Clone Database Information
    CLONE_DB_URI = os.environ.get("CLONE_DB_URI", "mongodb+srv://testclone:test123@testclone.gnnmw7g.mongodb.net/?retryWrites=true&w=majority&appName=testclone")
    CDB_NAME = os.environ.get("CDB_NAME", "clonetechvj")

    # Moderator Information
    OWNERS = [int(owner) if id_pattern.search(owner) else owner for owner in os.environ.get('OWNERS', '1512442581').split()]
    ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMINS', '1512442581').split()]

    # Channel Information
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1002855763957"))

    # Start Information
    WLC = os.environ.get("WLC", None)
    PICS = os.environ.get("PICS", None)

    # Auto Delete Information
    AUTO_DELETE_MODE = bool(os.environ.get('AUTO_DELETE_MODE', True)) # Set True or False

    # If Auto Delete Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
    AUTO_DELETE = int(os.environ.get("AUTO_DELETE", "30")) # Time in Minutes
    AUTO_DELETE_TIME = int(os.environ.get("AUTO_DELETE_TIME", "1800")) # Time in Seconds

    # File Caption Information
    CUSTOM_FILE_CAPTION = os.environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
    BATCH_FILE_CAPTION = os.environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)

    # Enable - True or Disable - False
    PUBLIC_FILE_STORE = is_enabled((os.environ.get('PUBLIC_FILE_STORE', "True")), True)

    # Verify Info :-
    VERIFY_MODE = bool(os.environ.get('VERIFY_MODE', False)) # Set True or False

    # If Verify Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
    SHORTLINK_URL = os.environ.get("SHORTLINK_URL", "") # shortlink domain without https://
    SHORTLINK_API = os.environ.get("SHORTLINK_API", "") # shortlink api
    VERIFY_TUTORIAL = os.environ.get("VERIFY_TUTORIAL", "") # how to open link 

    # File Stream Config
    STREAM_MODE = bool(os.environ.get('STREAM_MODE', True)) # Set True or False

    # If Stream Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
    MULTI_CLIENT = False
    SLEEP_THRESHOLD = int(os.environ.get('SLEEP_THRESHOLD', '60'))
    PING_INTERVAL = int(os.environ.get("PING_INTERVAL", "1200"))  # 20 minutes
    
except Exception as e:
    print("⚠️ Error loading config.py:", e)
    traceback.print_exc()