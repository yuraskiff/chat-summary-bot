import os
import logging
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram import types
from aiohttp import web

from bot.handlers.user_handlers import router as user_router
from bot.handlers.chat_handlers import router as chat_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

from db.db import init_pool, close_pool
from config.config import BOT_TOKEN, PORT

load_dotenv()

# Логи
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger("aiogram.client.session").setLevel(logging.ERROR)

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# Регистрируем middleware
dp.message.middleware(AuthMiddleware())

# Включаем роутеры
dp.include_router(user_router)
dp.include_router(chat_router)
dp.include_router(admin_router)

# Хэндлер для health-check
async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")

# Сигналы старта и завершения
async def on_startup(app: web.Application):
    # Инициализация БД
    await init_pool()
    logging.info("✅ Пул БД успешно инициализирован")

    # Планировщик автосводок
    setup_scheduler(dp)

    # Логируем маршруты
    for route in app.router.routes():
        logging.info("Маршрут: %s %s -> %s", route.method, route.resource, route.handler)

    # Устанавливаем webhook
    webhook_path = f"/webhook/{BOT_TOKEN}"
    url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{webhook_path}"
    logging.info("▶ Используем WEBHOOK_URL: %s", url)
    await bot.set_webhook(url)
    logging.info("🚀 Webhook установлен: %s", url)

async def on_shutdown(app: web.Application):
    # Сбрасываем webhook
    await bot.delete_webhook()
    # Закрываем БД и сессии
    await close_pool()
    await bot.session.close()
    logging.info("Бот и БД корректно завершили работу")

# Создаем приложение aiohttp
app = web.Application()
app.router.add_get('/', health)
# Регистрируем webhook хэндлер Aiogram
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=f"/webhook/{BOT_TOKEN}")

# Подписываемся на сигналы
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# Запускаем сервер
if __name__ == '__main__':
    host = '0.0.0.0'
    port = int(os.getenv('PORT', PORT))
    web.run_app(app, host=host, port=port)
