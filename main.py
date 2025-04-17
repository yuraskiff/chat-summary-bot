import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import asyncio

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FastAPI приложение
app = FastAPI()

# Webhook handler
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = types.Update(**await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    # Удалим старый webhook
    await bot.delete_webhook(drop_pending_updates=True)

    # Установим новый webhook (Render автоматически подставляет домен)
    render_external_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_external_url:
        await bot.set_webhook(f"{render_external_url}{WEBHOOK_PATH}", secret_token=WEBHOOK_SECRET)

# Подключение aiogram к FastAPI (для graceful shutdown)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
