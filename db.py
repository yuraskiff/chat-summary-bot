import os
import motor.motor_asyncio
from config import DATABASE_URL

client = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URL)
db = client.chat_db
collection = db.messages

async def save_message(username: str, text: str, timestamp):
    await collection.insert_one({
        "username": username,
        "text": text,
        "timestamp": timestamp
    })

async def get_messages_for_summary(since):
    cursor = collection.find({"timestamp": {"$gte": since}})
    return await cursor.to_list(length=1000)
