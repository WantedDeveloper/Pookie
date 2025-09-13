import re, os

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
    SESSION_STRING = os.environ.get("SESSION_STRING", "BQDsMO8AmFb6JbgFyK7jiJtXcx3AFBuboExTZHINbxsl8_YzR0HaeAI5_BnsfUv_vN-vrB8NvarvyBvTRb80QQsTUuCahomUwfyd4lYuGyiQ3olZsxvJ-jKg_5XvfMN6DalcD2zNuWGf-FvvTeH_-t8QMcAPXpDxyt97bYsBIBtQAoTDpHu5bqf0h6XphvYAnYPBWLluo6VASKQJ2FsxPQfV0pEflImcLKiakUFNzA5Sn0AX6ZzRbP9gmGvKJg5L4aOD7SmYwaDhm6N7xR4p8jtpx4zszlxriOQB_lCjywawyWw-_O01f0roGKph7TGLkSEr_uJ0asKkJAyIQ3yDiJ751R51JwAAAABaJgrVAA")
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

    # This Is Force Subscribe Channel, also known as Auth Channel 
    auth_channel = os.environ.get('AUTH_CHANNEL', '-1002912952165') # give your force subscribe channel id here else leave it blank
    AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else None
except Exception as e:
    print("⚠️ Error loading config.py:", e)
    traceback.print_exc()
