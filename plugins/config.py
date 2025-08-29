import re, os
from plugins.script import script

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
    DB_NAME = os.environ.get("DB_NAME", "main")

    # Clone Database Information
    CLONE_DB_URI = os.environ.get("CLONE_DB_URI", "mongodb+srv://testclone:test123@testclone.gnnmw7g.mongodb.net/?retryWrites=true&w=majority&appName=testclone")
    CDB_NAME = os.environ.get("CDB_NAME", "clone")

    # Moderator Information
    ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMINS', '1512442581').split()]

    # Channel Information
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1002855763957"))

    # auth_channel means force subscribe channel.
    # if REQUEST_TO_JOIN_MODE is true then force subscribe work like request to join fsub, else if false then work like normal fsub.
    REQUEST_TO_JOIN_MODE = bool(os.environ.get('REQUEST_TO_JOIN_MODE', False)) # Set True Or False
    TRY_AGAIN_BTN = bool(os.environ.get('TRY_AGAIN_BTN', False)) # Set True Or False (This try again button is only for request to join fsub not for normal fsub)

    # This Is Force Subscribe Channel, also known as Auth Channel 
    auth_channel = os.environ.get('AUTH_CHANNEL', '-1002855763957') # give your force subscribe channel id here else leave it blank
    AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else None

    # Enable - True or Disable - False
    PUBLIC_FILE_STORE = is_enabled((os.environ.get('PUBLIC_FILE_STORE', "True")), True)

    # Verify Info :-
    VERIFY_MODE = bool(os.environ.get('VERIFY_MODE', False)) # Set True or False

    # If Verify Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
    SHORTLINK_URL = os.environ.get("SHORTLINK_URL", "") # shortlink domain without https://
    SHORTLINK_API = os.environ.get("SHORTLINK_API", "") # shortlink api
    VERIFY_TUTORIAL = os.environ.get("VERIFY_TUTORIAL", "") # how to open link 

    # Auto Delete Information
    AUTO_DELETE_MODE = bool(os.environ.get('AUTO_DELETE_MODE', True)) # Set True or False

    # If Auto Delete Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
    AUTO_DELETE = int(os.environ.get("AUTO_DELETE", "30")) # Time in Minutes
    AUTO_DELETE_TIME = int(os.environ.get("AUTO_DELETE_TIME", "1800")) # Time in Seconds

    # Forward Protect Information
    FORWARD_PROTECT_MODE = bool(os.environ.get('FORWARD_PROTECT_MODE', True)) # Set True or False

    # File Caption Information
    CUSTOM_FILE_CAPTION = os.environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
    BATCH_FILE_CAPTION = os.environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)

    # File Stream Config
    STREAM_MODE = bool(os.environ.get('STREAM_MODE', True)) # Set True or False

    # If Stream Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
    MULTI_CLIENT = False
    SLEEP_THRESHOLD = int(os.environ.get('SLEEP_THRESHOLD', '60'))
    
except Exception as e:
    print("⚠️ Error loading config.py:", e)
    traceback.print_exc()