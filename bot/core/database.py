from motor.motor_asyncio import AsyncIOMotorClient  
from bot import Var  

class MongoDB:
    def __init__(self, uri, database_name):
        self.__client = AsyncIOMotorClient(uri)
        self.__db = self.__client[database_name]
        
        # Collections
        self.__animes = self.__db.animes[Var.BOT_TOKEN.split(':')[0]]
        self.__user_animes = self.__db.user_animes
        
        # ✅ NEW: Files Collection for Streaming
        self.files = self.__db.files 

    # ----------------------
    # Anime Storage
    # ----------------------
    async def getAnime(self, ani_id):
        botset = await self.__animes.find_one({'_id': ani_id})
        return botset or {}

    async def saveAnime(self, ani_id, ep, qual, post_id=None):
        quals = (await self.getAnime(ani_id)).get(ep, {qual: False for qual in Var.QUALS})
        quals[qual] = True
        await self.__animes.update_one(
            {'_id': ani_id},
            {'$set': {ep: quals}},
            upsert=True
        )
        if post_id:
            await self.__animes.update_one(
                {'_id': ani_id},
                {'$set': {"msg_id": post_id}},
                upsert=True
            )

    # ----------------------
    # User Tracking
    # ----------------------
    async def get_user_anime(self, user_id, ani_id, qual=None):
        doc = await self.__user_animes.find_one({'user_id': user_id, 'anime_id': ani_id})
        if not doc: return False if qual else None
        if qual: return doc.get("got_files", {}).get(qual, False)
        return doc

    async def mark_user_anime(self, user_id, ani_id, qual):
        doc = await self.__user_animes.find_one({'user_id': user_id, 'anime_id': ani_id})
        got_files = doc.get("got_files", {}) if doc else {}
        got_files[qual] = True
        await self.__user_animes.update_one(
            {'user_id': user_id, 'anime_id': ani_id},
            {'$set': {'got_files': got_files}},
            upsert=True
        )

    async def reboot(self):
        await self.__animes.drop()
        await self.__user_animes.drop()

    # ----------------------
    # ✅ NEW: Helper for Routes.py
    # ----------------------
    async def get_file(self, unique_id):
        try:
            return await self.files.find_one({'_id': unique_id})
        except Exception:
            return None

# Single instance
db = MongoDB(Var.MONGO_URI, "FZAutoAnimes")
