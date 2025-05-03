import os
import logging
from urllib.parse import quote

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

from bot.handlers.user_handlers import router as user_router
from bot.handlers.chat_handlers import router as chat_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

from config.config import BOT_TOKEN, WEBHOOK_URL, PORT
from db.db import init_pool, close_pool

# Логи
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("aiogram.client.session").setLevel(logging.ERROR)

# Кодируем токен для URL-path
TOKEN_ENCODED = quote(BOT_TOKEN, safe="")  # двоеточие станет %3A

# Бот и диспетчер
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
dp.message.middleware(AuthMiddleware())
dp.include_router(user_router)
dp.include_router(chat_router)
dp.include_router(admin_router)

# aiohttp-приложение
app = web.Application()

# Регистрируем handler именно на «/webhook/{TOKEN_ENCODED}»
SimpleRequestHandler(dispatcher=dp, bot=bot).register(
    app, path=f"/webhook/{TOKEN_ENCODED}"
)

async def on_startup(app: web.Application):
    # Инициализация БД и планировщика
    await init_pool()
    setup_scheduler(dp)

    logging.info("▶ Полученный WEBHOOK_URL: %s", WEBHOOK_URL)
    # Ставим webhook в Telegram
    await bot.set_webhook(WEBHOOK_URL)
    logging.info("🚀 Webhook установлен: %s", WEBHOOK_URL)

    # Диагностика
    info = await bot.get_webhook_info()
    logging.info("🔍 WebhookInfo: %s", info.model_dump())  # pydantic V2

async def on_shutdown(app: web.Application):
    # Удаляем webhook
    await bot.delete_webhook()

    # Останавливаем планировщик
    sched = dp.get("scheduler")
    if sched:
        sched.shutdown()

    # Закрываем БД и сессию
    await close_pool()
    try:
        await bot.session.close()
    except AttributeError:
        session = await bot.get_session()
        await session.close()

    logging.info("🛑 Шатдаун завершён")

app.on_startup.append(on_startup)
app.on_cleanup.append(on_shutdown)

if __name__ == "__main__":
    host = "0.0.0.0"
    logging.info("Запуск aiohttp на %s:%d …", host, PORT)
    web.run_app(app, host=host, port=PORT)
