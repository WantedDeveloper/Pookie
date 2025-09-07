import motor.motor_asyncio
from plugins.config import DB_NAME, DB_URI
from plugins.script import script

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.bot = self.db.clone_bots
        self.settings = self.db.bot_settings
        self.media = self.db.media_files

    # ---------------- USERS ----------------
    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
        )

    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    # ---------------- CLONE BOT ----------------
    async def add_clone_bot(self, bot_id, user_id, first_name, username, bot_token):
        settings = {
            'is_bot': True,
            'bot_id': bot_id,
            'user_id': user_id,
            'name': first_name,
            'username': username,
            'token': bot_token,
            # Start Message
            'wlc': script.START_TXT,
            'pics': None,
            'caption': None,
            'button': [],
            # Channel Message
            'word_filter': False,
            'media_filter': False,
            'random_captiom': False,
            'header': None,
            'footer': None,
            # Force Subscribe
            'force_subscribe': [],
            # Access Token
            'access_token': False,
            'shorten_link': None,
            'shorten_api': None,
            'access_token_validity': 24,
            'access_token_renew_log': {},
            'access_token_tutorial': None,
            # Auto Post
            'auto_post': False,
            'target_channel': None,
            # Premium User
            'premium': [],
            # Auto Delete
            'auto_delete': False,
            'auto_delete_time': 1,
            'auto_delete_msg': script.AD_TXT,
            # Forward Protect
            'forward_protect': False,
            # Moderators
            'moderators': [],
            # Status
            'users_count': 0,
            'banned_users': [],
            'storage_used': 0,
            'storage_limit': 536870912 # 512 MB default
        }
        await self.bot.insert_one(settings)

    async def is_clone_exist(self, user_id):
        clone = await self.bot.find_one({'user_id': int(user_id)})
        return bool(clone)

    async def get_clones_by_user(self, user_id):
        clones = []
        user_id_str = str(user_id)  # moderator match as string
        try:
            user_id_int = int(user_id)  # owner match as int
        except ValueError:
            return []

        cursor = self.bot.find({
            "$or": [
                {"user_id": user_id_int},    # owner
                {"moderators": user_id_str}  # moderator
            ]
        })

        async for clone in cursor:
            clones.append(clone)

        return clones

    async def get_clone_by_id(self, bot_id):
        clone = await self.bot.find_one({'bot_id': int(bot_id)})
        return clone

    async def update_clone(self, bot_id, user_data: dict, raw=False):
        if raw:
            await self.bot.update_one({'bot_id': int(bot_id)}, user_data, upsert=True)
        else:
            await self.bot.update_one({'bot_id': int(bot_id)}, {'$set': user_data}, upsert=True)

    async def delete_clone(self, bot_id):
        await self.bot.delete_one({'bot_id': int(bot_id)})

    async def get_bot(self, bot_id):
        bot_data = await self.bot.find_one({"bot_id": bot_id})
        return bot_data

    async def update_bot(self, bot_id, bot_data):
        await self.bot.update_one({"bot_id": bot_id}, {"$set": bot_data}, upsert=True)

    async def get_all_bots(self):
        return self.bot.find({})

    async def increment_users_count(self, bot_id):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$inc': {'users_count': 1}})

    async def add_storage_used(self, bot_id, size: int):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$inc': {'storage_used': size}})

    async def ban_user(self, bot_id, user_id):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$addToSet': {'banned_users': int(user_id)}})

    async def unban_user(self, bot_id, user_id):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$pull': {'banned_users': int(user_id)}})

    async def get_banned_users(self, bot_id):
        clone = await self.bot.find_one({'bot_id': int(bot_id)})
        return clone.get("banned_users", []) if clone else []

    # ---------------- PREMIUM ----------------
    async def has_premium_access(self, user_id):
        user_data = await self.get_user(user_id)
        if user_data:
            expiry_time = user_data.get("expiry_time")
            if expiry_time is None:
                return False
            elif isinstance(expiry_time, datetime.datetime) and datetime.datetime.now() <= expiry_time:
                return True
            else:
                await self.users.update_one({"id": user_id}, {"$set": {"expiry_time": None}})
        return False

    async def check_remaining_uasge(self, userid):
        user_id = userid
        user_data = await self.get_user(user_id)        
        expiry_time = user_data.get("expiry_time")
        remaining_time = expiry_time - datetime.datetime.now()
        return remaining_time

    async def get_free_trial_status(self, user_id):
        user_data = await self.get_user(user_id)
        if user_data:
            return user_data.get("has_free_trial", False)
        return False

    async def give_free_trail(self, userid):        
        user_id = userid
        seconds = 5*60         
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        user_data = {"id": user_id, "expiry_time": expiry_time, "has_free_trial": True}
        await self.users.update_one({"id": user_id}, {"$set": user_data}, upsert=True)

    async def all_premium_users(self):
        count = await self.users.count_documents({
        "expiry_time": {"$gt": datetime.datetime.now()}
        })
        return count

    # ---------------- MEDIA ----------------
    async def add_media(self, msg_id, file_id, caption, media_type, date, posted=False):
        await self.media.update_one(
            {"file_id": file_id},
            {"$setOnInsert": {
                "msg_id": msg_id,
                "file_id": file_id,
                "caption": caption or "",
                "media_type": media_type,
                "date": date,
                "posted": posted,
                "posted_by": []
            }},
            upsert=True
        )

    async def is_media_exist(self, file_id):
        media = await self.media.find_one({"file_id": file_id})
        return bool(media)

    async def get_random_unposted_media(self, bot_id: int):
        """Get a random media that this bot hasn't posted yet"""
        item = await self.media.aggregate([
            {"$match": {
                "$or": [
                    {"posted_by": {"$exists": False}},
                    {"posted_by": {"$eq": []}},
                    {"posted_by": {"$nin": [bot_id]}}
                ]
            }},
            {"$sample": {"size": 1}}
        ]).to_list(length=1)
        return item[0] if item else None

    # ------------------- Mark Media Posted -------------------
    async def mark_media_posted(self, media_id, bot_id: int):
        """Mark media as posted by this bot safely (MongoDB conflict safe)"""
        # Step 1: ensure posted_by exists
        await self.media.update_one(
            {"_id": media_id, "posted_by": {"$exists": False}},
            {"$set": {"posted_by": []}}
        )
        # Step 2: add bot_id safely
        await self.media.update_one(
            {"_id": media_id},
            {"$addToSet": {"posted_by": bot_id}}
        )

    async def get_media_by_id(self, msg_id):
        return await self.media.find_one({"msg_id": msg_id})

    async def get_all_media(self):
        return self.media.find({})

    async def delete_media(self, msg_id):
        await self.media.delete_one({"msg_id": msg_id})

    async def delete_all_media(self):
        result = await self.media.delete_many({})
        return result.deleted_count

    async def reset_clone_posts(self, bot_id: int):
        result = await self.media.update_many(
            {},
            {"$pull": {"posted_by": bot_id}}
        )
        return result.modified_count

    async def reset_all_posts(self):
        result = await self.media.update_many(
            {},
            {"$set": {"posted_by": []}}
        )
        return result.modified_count

db = Database(DB_URI, DB_NAME)