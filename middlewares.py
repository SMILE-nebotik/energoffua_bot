from aiogram import BaseMiddleware
from aiogram.types import Message
from cachetools import TTLCache

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, time_limit: int = 1):

        self.limit = TTLCache(maxsize=10_000, ttl=time_limit)

    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            if event.from_user.id in self.limit:
                return 
            else:
                self.limit[event.from_user.id] = True
        
        return await handler(event, data)