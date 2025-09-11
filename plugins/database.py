import motor.motor_asyncio, datetime
from plugins.config import *
from plugins.script import script

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.premium = self.db.premium_users
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

    # ---------------- PREMIUM USERS ----------------
    async def add_premium_user(self, user_id: int, days: int, plan_type: str = "normal"):
        expiry_time = datetime.datetime.utcnow() + datetime.timedelta(days=days)
        await self.premium.update_one(
            {"id": int(user_id)},
            {"$set": {
                "id": int(user_id),
                "plan_type": plan_type,
                "expiry_time": expiry_time
            }},
            upsert=True
        )

    async def remove_premium_user(self, user_id: int):
        await self.premium.delete_one({"id": int(user_id)})

    async def get_premium_user(self, user_id: int):
        return await self.premium.find_one({"id": int(user_id)})

    async def is_premium(self, user_id: int, required_plan: str = "normal"):
        user = await self.get_premium_user(user_id)
        if not user:
            return False

        expiry = user.get("expiry_time")
        if not expiry or expiry < datetime.datetime.utcnow():
            return False

        if required_plan == "ultra":
            return user.get("plan_type") in ["ultra", "vip"]
        elif required_plan == "vip":
            return user.get("plan_type") == "vip"

        return True

    async def list_premium_users(self):
        cursor = self.premium.find({
            "expiry_time": {"$gt": datetime.datetime.utcnow()}
        })
        users = []
        async for user in cursor:
            users.append(user)
        return users

    # ---------------- CLONE ----------------
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
            'premium_user': [],
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
        user_id_str = str(user_id)
        try:
            user_id_int = int(user_id)
        except ValueError:
            return []

        cursor = self.bot.find({
            "$or": [
                {"user_id": user_id_int},
                {"moderators": user_id_str}
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

    # ---------------- MEDIA ----------------
    async def add_media(self, bot_id: int, msg_id: int, file_id: str, caption: str, media_type: str, date):
        await self.media.update_one(
            {"bot_id": bot_id, "file_id": file_id},
            {"$setOnInsert": {
                "bot_id": bot_id,
                "msg_id": msg_id,
                "file_id": file_id,
                "caption": caption or "",
                "media_type": media_type,
                "date": date,
                "posted": False
            }},
            upsert=True
        )

    async def is_media_exist(self, bot_id: int, file_id: str):
        media = await self.media.find_one({"bot_id": bot_id, "file_id": file_id})
        return bool(media)

    async def get_random_unposted_media(self, bot_id: int):
        item = await self.media.aggregate([
            {"$match": {"bot_id": bot_id, "posted": False}},
            {"$sample": {"size": 1}}
        ]).to_list(length=1)
        return item[0] if item else None

    async def mark_media_posted(self, bot_id: int, file_id: str):
        await self.media.update_one(
            {"bot_id": bot_id, "file_id": file_id},
            {"$set": {"posted": True}}
        )

    async def get_media_by_id(self, bot_id: int, msg_id: int):
        return await self.media.find_one({"bot_id": bot_id, "msg_id": msg_id})

    async def get_all_media(self, bot_id: int):
        return self.media.find({"bot_id": bot_id})

    async def delete_media(self, bot_id: int, msg_id: int):
        await self.media.delete_one({"bot_id": bot_id, "msg_id": msg_id})

    async def delete_all_media(self, bot_id: int):
        result = await self.media.delete_many({"bot_id": bot_id})
        return result.deleted_count

    async def reset_clone_posts(self, bot_id: int):
        result = await self.media.update_many(
            {"bot_id": bot_id},
            {"$set": {"posted": False}}
        )
        return result.modified_count

db = Database(DB_URI, DB_NAME)

class CloneDatabase:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]

    async def add_user(self, bot_id, user_id):
        user = {'user_id': int(user_id)}
        await self.db[str(bot_id)].insert_one(user)
    
    async def is_user_exist(self, bot_id, id):
        user = await self.db[str(bot_id)].find_one({'user_id': int(id)})
        return bool(user)
    
    async def total_users_count(self, bot_id):
        count = await self.db[str(bot_id)].count_documents({})
        return count

    async def get_all_users(self, bot_id):
        return self.db[str(bot_id)].find({})

    async def delete_user(self, bot_id, user_id):
        await self.db[str(bot_id)].delete_many({'user_id': int(user_id)})

    async def get_user(self, user_id):
        user_id = int(user_id)
        user = await self.db.users.find_one({"user_id": user_id})
        if not user:
            res = {
                "user_id": user_id,
                "shortener_api": None,
                "base_site": None,
            }
            await self.db.users.insert_one(res)
            user = await self.db.users.find_one({"user_id": user_id})
        return user

    async def update_user_info(self, user_id, value:dict):
        user_id = int(user_id)
        myquery = {"user_id": user_id}
        newvalues = { "$set": value }
        await self.db.users.update_one(myquery, newvalues)

clonedb = CloneDatabase(CLONE_DB_URI, CDB_NAME)

class JoinReqs:

    def __init__(self):
        if DB_URI:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
            self.db = self.client["JoinReqs"]
            self.col = self.db[str(AUTH_CHANNEL)]
        else:
            self.client = None
            self.db = None
            self.col = None

    def isActive(self):
        if self.client is not None:
            return True
        else:
            return False

    async def add_user(self, user_id, first_name, username, date):
        try:
            await self.col.insert_one({"_id": int(user_id),"user_id": int(user_id), "first_name": first_name, "username": username, "date": date})
        except:
            pass

    async def get_user(self, user_id):
        return await self.col.find_one({"user_id": int(user_id)})

    async def get_all_users(self):
        return await self.col.find().to_list(None)

    async def delete_user(self, user_id):
        await self.col.delete_one({"user_id": int(user_id)})

    async def delete_all_users(self):
        await self.col.delete_many({})

    async def get_all_users_count(self):
        return await self.col.count_documents({})
