from pyrogram.types import Message
from pyrogram import Client, filters

@Client.on_message(filters.private & filters.incoming)
async def useless(_,message: Message):
    message.reply("❌ Don't send me messages directly I'm only File Store bot!")
