import os
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

from bot.handlers.user_handlers import router as user_router
from bot.handlers.chat_handlers import router as chat_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware
from config.config import BOT_TOKEN, WEBHOOK_URL
from db.db import init_pool, close_pool

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger("aiogram.client.session").setLevel(logging.ERROR)

# --- Создаём бота и диспетчер ---
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp  = Dispatcher()

# Регистрируем middleware и роутеры
dp.message.middleware(AuthMiddleware())
dp.include_router(user_router)
dp.include_router(chat_router)
dp.include_router(admin_router)

# --- aiohttp-приложение для webhook ---
app = web.Application()

# Точка входа для Telegram: /webhook/{BOT_TOKEN}
SimpleRequestHandler(dispatcher=dp, bot=bot).register(
    app, path=f"/webhook/{BOT_TOKEN}"
)

# --- Функции старта и остановки ---
async def on_startup(app: web.Application):
    # Инициализируем пул БД и планировщик автосводок
    await init_pool()
    setup_scheduler(dp)
    # Устанавливаем webhook в Telegram
    await bot.set_webhook(WEBHOOK_URL)
    logging.info("🚀 Webhook установлен: %s", WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    # Удаляем webhook
    await bot.delete_webhook()
    # Останавливаем планировщик, пул и закрываем сессию бота
    sched = dp.get("scheduler")
    if sched:
        sched.shutdown()
    await close_pool()
    try:
        await bot.session.close()
    except AttributeError:
        session = await bot.get_session()
        await session.close()
    logging.info("🛑 Шатдаун завершён")

# Привязываем стартап/шатдаун
app.on_startup.append(on_startup)
app.on_cleanup.append(on_shutdown)

# --- Запуск aiohttp-сервера ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"
    logging.info("Запуск aiohttp на %s:%d …", host, port)
    web.run_app(app, host=host, port=port)
