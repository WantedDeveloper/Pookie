class script(object):
    START_TXT = """Hello {} 👋 

My Name {}

I am a permenant file store bot and users can access stored messages by using a shareable link given by me

To know more click help button"""

    HELP_TXT = """<u>✨ HELP MENU</u>

I am a permenant file store bot. you can store files from your public channel without i am admin in there. Either your channel or group is private first make me admin in there. Then you can store your files by using below mentioned commands and you can access stored files by using shareable link given by me.

📚 Available Commands:
🔻 /start - Check i am alive.
🔻 /genlink - To store a single message or file.
🔻 /batch - To store mutiple messages from a channel.
🔻 /custom_batch - To store multiple random messages.
🔻 /shortener - To shorten any shareable links.
🔻 /broadcast - Broadcast a messages to users."""

    ABOUT_TXT = """<u>✨ ABOUT ME</u>

🤖 My Name: {}

📝 Language: <a href=https://www.python.org>Python3</a>

📚 Library: <a href=https://docs.pyrogram.org>Pyrogram</a>

🧑🏻‍💻 Developer: <a href=https://t.me/PookieManagerBot>Pookie</a>

👥 Support Group: <a href=https://t.me/PookieManagerBot>Support</a>

📢 Update Channel: <a href=https://t.me/PookieManagerBot>Update</a>"""

    CABOUT_TXT = """<u>✨ ABOUT ME</u>

🤖 My Name: {}

📝 Language: <a href=https://www.python.org>Python3</a>

📚 Library: <a href=https://docs.pyrogram.org>Pyrogram</a>

🧑🏻‍💻 Developer: <a href=tg://user?id={}>Developer</a>"""

    CAPTION = """<b>📂 ғɪʟᴇɴᴀᴍᴇ : {file_name}

⚙️ sɪᴢᴇ : {file_size}

Jᴏɪɴ [ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ](https://t.me/vj_botz)</b>""" 

    SHORTENER_API_MESSAGE = """<b>Tᴏ ᴀᴅᴅ ᴏʀ ᴜᴘᴅᴀᴛᴇ ʏᴏᴜʀ Sʜᴏʀᴛɴᴇʀ Wᴇʙsɪᴛᴇ API, /api (ᴀᴘɪ)
            
<b>Ex: /api 𝟼LZǫ𝟾𝟻𝟷sXᴏғғғPHᴜɢɪKQǫ

<b>Cᴜʀʀᴇɴᴛ Wᴇʙsɪᴛᴇ: {base_site}

Cᴜʀʀᴇɴᴛ Sʜᴏʀᴛᴇɴᴇʀ API:</b> `{shortener_api}`

If You Want To Remove Api Then Copy This And Send To Bot - `/api None`"""

    LOG_TEXT = """<b>#NewUser
    
ID - <code>{}</code>

Nᴀᴍᴇ - {}</b>"""

    RESTART_TXT = """
<b>Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ !

📅 Dᴀᴛᴇ : <code>{}</code>
⏰ Tɪᴍᴇ : <code>{}</code>
🌐 Tɪᴍᴇᴢᴏɴᴇ : <code>Asia/Kolkata</code>
🛠️ Bᴜɪʟᴅ Sᴛᴀᴛᴜs: <code>v2.7.1 [ Sᴛᴀʙʟᴇ ]</code></b>"""
