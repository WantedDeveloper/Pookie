from pyrogram import Client

API_ID = 15479023
API_HASH = "f8f6cf547822449c29fc60dae3b31dd4"

app = Client("gen", api_id=API_ID, api_hash=API_HASH)
print(app.export_session_string())
