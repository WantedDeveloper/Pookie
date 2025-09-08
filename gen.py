from pyrogram import Client

API_ID = 15479023
API_HASH = "f8f6cf547822449c29fc60dae3b31dd4"

app = Client("gen", api_id=API_ID, api_hash=API_HASH)

with app:
    print("\n✅ Your SESSION STRING:\n")
    print(app.export_session_string())
    print("\n⚠️ Copy this string and paste it into config.py as SESSION_STRING")
