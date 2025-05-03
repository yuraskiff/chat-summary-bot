import os
import logging

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

from bot.handlers.user_handlers import router as user_router
from bot.handlers.chat_handlers import router as chat_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

from config.config import BOT_TOKEN, WEBHOOK_URL, PORT
from db.db import init_pool, close_pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("aiogram.client.session").setLevel(logging.ERROR)

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
dp.message.middleware(AuthMiddleware())
dp.include_router(user_router)
dp.include_router(chat_router)
dp.include_router(admin_router)

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=f"/webhook/{BOT_TOKEN}")

async def on_startup(app: web.Application):
    await init_pool()
    setup_scheduler(dp)

    logging.info("▶ Полученный WEBHOOK_URL: %s", WEBHOOK_URL)
    await bot.set_webhook(WEBHOOK_URL)
    logging.info("🚀 Webhook установлен: %s", WEBHOOK_URL)

    info = await bot.get_webhook_info()
    logging.info("🔍 WebhookInfo: %s", info.to_python())

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
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

app.on_startup.append(on_startup)
app.on_cleanup.append(on_shutdown)

if __name__ == "__main__":
    host = "0.0.0.0"
    logging.info("Запуск aiohttp на %s:%d …", host, PORT)
    web.run_app(app, host=host, port=PORT)
