import redis.asyncio as redis
import os

redis_client = None


async def get_redis_client():
    global redis_client
    if redis_client is None:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=os.getenv('REDIS_PORT'),
            password=os.getenv("REDIS_PASS"),
        )
    return redis_client
