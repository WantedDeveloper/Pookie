import motor.motor_asyncio
from config import DB_NAME, DB_URI
from Script import script

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.bot = self.db.clone_bots
        self.settings = self.db.bot_settings

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

    async def add_clone_bot(self, bot_id, user_id, first_name, username, bot_token):
        settings = {
            'is_bot': True,
            'bot_id': bot_id,
            'user_id': user_id,
            'name': first_name,
            'username': username,
            'token': bot_token,
            'wlc': script.START_TXT,
            'pics': None
        }
        await self.bot.insert_one(settings)

    async def is_clone_exist(self, user_id):
        clone = await self.bot.find_one({'user_id': int(user_id)})
        return bool(clone)

    async def get_clone(self, user_id):
        clones = await self.bot.find({"user_id": int(user_id)}).to_list(length=100)
        return clones
    
    async def update_clone(self, bot_id, user_data):
        await self.bot.update_one({'bot_id': int(bot_id)}, {'$set': user_data}, upsert=True)

    async def delete_clone(self, bot_id):
        await self.bot.delete_one({'bot_id': int(bot_id)})
        await self.settings.delete_many({'bot_id': int(bot_id)})

    async def get_db_size(self):
        return (await self.db.command("dbstats"))['dataSize']

db = Database(DB_URI, DB_NAME)
