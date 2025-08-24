class script(object):
    START_TXT = """Hello {user} 👋 

My Name {bot}

I am a permenant file store bot and users can access stored messages by using a shareable link given by me

To know more click **help** button"""

    HELP_TXT = """<u>**✨ HELP MENU**</u>

I am a permenant file store bot. you can store files from your public channel without i am admin in there. Either your channel or group is private first make me admin in there. Then you can store your files by using below mentioned commands and you can access stored files by using shareable link given by me.

📚 Available Commands:
🔻 /start - Check i am alive.
🔻 /genlink - To store a single message or file.
🔻 /batch - To store mutiple messages from a channel.
🔻 /shortener - To shorten any shareable links.
🔻 /broadcast - Broadcast a message to users.
🔻 /contact - Send a message to admin."""

    ABOUT_TXT = """<u>**✨ ABOUT ME**</u>

🤖 My Name: {bot}

📝 Language: <a href=https://www.python.org>Python3</a>

📚 Library: <a href=https://docs.pyrogram.org>Pyrogram</a>

🧑🏻‍💻 Developer: <a href=https://t.me/PookieManagerBot>Pookie</a>

👥 Support Group: <a href=https://t.me/PookieManagerBot>Support</a>

📢 Update Channel: <a href=https://t.me/PookieManagerBot>Update</a>"""

    CABOUT_TXT = """<u>**✨ ABOUT ME**</u>

🤖 My Name: {bot}

📝 Language: <a href=https://www.python.org>Python3</a>

📚 Library: <a href=https://docs.pyrogram.org>Pyrogram</a>

🧑🏻‍💻 Developer: <a href=tg://user?id={developer}>Developer</a>"""

    MANAGEC_TXT = """<u>**✨ MANAGE CLONE**</u>

You can now manage and create your very own identical clone bot, mirroring all my awesome features, using the given buttons."""

    CLONE_TXT = """1) Send <code>/newbot</code> to @BotFather.
2) Give a name for your bot.
3) Give a unique username.
4) Then you will get a message with your bot token.
5) Forward that message to me.

Then i am try to create a clone bot of me for u only 😌"""

    CUSTOMIZEC_TXT = """<u>**✨ CUSTOMIZE CLONE**</u>

🖍️ Username: {username}

If you want to modify your clone bot then do it from here."""

    ST_MSG_TXT = """<u>**✨ START MESSAGE**</u>

customize your clone start message using the following buttons."""

    ST_TXT_TXT = """<u>**✨ START TEXT**</u>

Personalize your clone start message text to suit your preferences. Use the provided button to edit the start message text of your clone."""

    EDIT_TXT_TXT = """{user} : mention user

Eg: Hi {user} 👋
I am a file store bot.

Now send your new start message text."""

    ST_PIC_TXT = """<u>**✨ START PHOTO**</u>

You have the option to include a photo along with your start message."""

    CAPTION_TXT = """
"""

    BUTTON_TXT = """
"""

    FSUB_TXT = """<u>**✨ FORCE SUBSCRIBE**</u>

Users can only use your clone bot after joining all force sub channels. clone bots now also support join request mode.

You can add up to 4 channels."""

    TOKEN_TXT = """<u>**✨ ACCESS TOKEN**</u>

Users need to pass a shortened link to gain special access to messages from all clone shareable links. This access will be valid for the next custom validity period.

Current Status: {status}"""

    AT_VALIDITY_TXT = """<u>**✨ ACCESS TOKEN VALIDITY**</u>

You can customize the special access validty about access-token that is remove ads to users when they access the links."""

    AT_TUTORIAL_TXT = """<u>**✨ ACCESS TOKEN TUTORIAL**</u>

You can customize the special access validty about access-token that is remove ads to users when they access the links."""

    DELETE_TXT = """<u>**✨ AUTO DELETE**</u>

Current Status: {status}"""

    AD_TIME_TXT = """<u>**✨ AUTO DELETE TIME**</u>

You can customize the alert time about auto-delete that is sent last to users when they access the links."""

    AD_MSG_TXT = """<u>**✨ AUTO DELETE MESSAGE**</u>

You can customize the alert message about auto-delete that is sent last to users when they access the links."""

    AD_TXT = """<u>⚠️ IMPORTANT:</u>

All Messages will be deleted after {time}. Please save or forward these messages to your personal saved messages to avoid losing them!"""

    PREMIUM_TXT = """
"""

    FORWARD_TXT = """<u>**✨ FORWARD PROTECTION**</u>

Restrict Clone users from forwarding messages from shareable link.

Current Status: {status}"""

    MODERATOR_TXT = """<u>**✨ MODERATOR**</u>

Moderators have access to all your clone features, include broadcasting."""

    CAPTION = """<b>📂 ғɪʟᴇɴᴀᴍᴇ : {file_name}

⚙️ sɪᴢᴇ : {file_size}

Jᴏɪɴ [ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ](https://t.me/vj_botz)</b>""" 

    LOG_TEXT = """<b>#NewUser
    
Id - <code>{}</code>

Name - {}</b>"""

    RESTART_TXT = """
<b>Bot Restarted !

📅 Date : <code>{}</code>
⏰ Time : <code>{}</code>
🌐 Timezone : <code>Asia/Kolkata</code>
🛠️ Build Status : <code>v2.7.1 [ Stable ]</code></b>"""
