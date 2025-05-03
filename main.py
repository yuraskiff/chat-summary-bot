import os
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

from bot.handlers.user_handlers import router as user_router
from bot.handlers.chat_handlers import router as chat_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

from db.db import init_pool, close_pool
from config.config import BOT_TOKEN, PORT

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("aiogram.client.session").setLevel(logging.ERROR)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
dp.message.middleware(AuthMiddleware())

dp.include_router(user_router)
dp.include_router(chat_router)
dp.include_router(admin_router)

async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")

async def on_startup(app: web.Application):
    try:
        await init_pool()
        logging.info("✅ Пул БД успешно инициализирован")
    except Exception as e:
        logging.error(f"❌ Не удалось инициализировать БД: {e}")
        return

    setup_scheduler(dp)

    for route in app.router.routes():
        logging.info("Маршрут: %s %s -> %s", route.method, route.resource, route.handler)

    host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or os.getenv("WEBHOOK_HOST")
    if not host:
        logging.error("❌ Не задан хост для webhook (RENDER_EXTERNAL_HOSTNAME или WEBHOOK_HOST)")
        return

    webhook_path = f"/webhook/{BOT_TOKEN}"
    url = f"https://{host}{webhook_path}"
    logging.info("▶ Используем WEBHOOK_URL: %s", url)

    try:
        await bot.set_webhook(url)
        logging.info("🚀 Webhook установлен: %s", url)
    except Exception as e:
        logging.error(f"❌ Не удалось установить webhook: {e}")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await close_pool()
    await bot.session.close()
    logging.info("🛑 Бот и БД корректно завершили работу")

app = web.Application()
app.router.add_get("/", health)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=f"/webhook/{BOT_TOKEN}")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.getenv("PORT", PORT))
    web.run_app(app, host=host, port=port)
