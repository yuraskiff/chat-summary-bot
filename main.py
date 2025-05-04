# --- START OF FILE main.py ---

import os
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Импортируем роутеры и функцию настройки планировщика
from bot.handlers.user_handlers import router as user_router
from bot.handlers.chat_handlers import router as chat_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

# Импортируем функции для работы с БД и конфигурацию
from db.db import init_pool, close_pool
from config.config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PATH, PORT, ADMIN_CHAT_ID

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
    # Если нужно писать в файл:
    # handlers=[
    #     logging.FileHandler("bot.log"),
    #     logging.StreamHandler()
    # ]
)
# Уменьшаем уровень логирования для слишком "болтливых" библиотек
logging.getLogger("aiogram.client.session").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

# Проверяем наличие токена и ID админа
if not BOT_TOKEN:
    logging.critical("❌ Не задан токен бота (переменная BOT_TOKEN)")
    exit("BOT_TOKEN is not set")
if not ADMIN_CHAT_ID:
    logging.warning("⚠️ Не задан ID администратора (переменная ADMIN_CHAT_ID). Некоторые админ-команды не будут работать.")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# Подключение middleware
dp.message.middleware(AuthMiddleware()) # Пример middleware, убедитесь, что он вам нужен

# Подключение роутеров
dp.include_router(user_router)
dp.include_router(chat_router)
dp.include_router(admin_router)
logging.info("Роутеры подключены")

# Функция для проверки состояния (health check)
async def health_check(request: web.Request) -> web.Response:
    # Можно добавить проверки доступности БД или OpenAI API при необходимости
    return web.Response(text="OK")

# Действия при запуске приложения
async def on_startup(app: web.Application):
    # В Aiohttp принято передавать объекты через контекст приложения
    # app['bot'] = bot
    # app['dp'] = dp
    # app['config'] = ... и т.д. если нужно

    # Инициализация пула соединений с БД
    try:
        await init_pool()
        logging.info("✅ Пул БД успешно инициализирован")
    except Exception as e:
        logging.critical(f"❌ Не удалось инициализировать БД: {e}. Завершение работы.")
        # Останавливаем запуск, если БД недоступна
        raise web.GracefulExit() from e

    # ----> ИЗМЕНЕНИЕ ЗДЕСЬ: ПЕРЕДАЕМ bot В setup_scheduler <----
    # Настройка и запуск планировщика
    try:
        setup_scheduler(bot)
    except Exception as e:
        logging.error(f"❌ Не удалось настроить или запустить планировщик: {e}")
        # Решите, критична ли эта ошибка для работы бота

    # Определение хоста для вебхука
    # Предпочтение отдается Render, затем переменной WEBHOOK_HOST
    webhook_host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or WEBHOOK_HOST
    if not webhook_host:
        logging.critical("❌ Не задан хост для webhook (RENDER_EXTERNAL_HOSTNAME или WEBHOOK_HOST)")
        raise web.GracefulExit("Webhook host is not set")

    # Формирование URL вебхука
    # WEBHOOK_PATH должен начинаться со слеша, например /webhook
    webhook_url = f"https://{webhook_host}{WEBHOOK_PATH}"
    logging.info(f"▶ Используем WEBHOOK_URL: {webhook_url}")

    # Установка вебхука
    try:
        # Передаем секретный токен для проверки запросов от Telegram
        # SECRET_TOKEN = os.getenv("WEBHOOK_SECRET", "your_strong_secret") # Лучше задать через .env
        # await bot.set_webhook(webhook_url, secret_token=SECRET_TOKEN)
        # Если секрет не используется:
        await bot.set_webhook(webhook_url)
        logging.info(f"🚀 Webhook установлен: {webhook_url}")
    except Exception as e:
        logging.critical(f"❌ Не удалось установить webhook: {e}")
        raise web.GracefulExit() from e

# Действия при завершении работы приложения
async def on_shutdown(app: web.Application):
    logging.info("🏁 Завершение работы...")
    # Удаляем вебхук
    try:
        await bot.delete_webhook()
        logging.info("Webhook удален")
    except Exception as e:
        logging.error(f"❌ Ошибка при удалении webhook: {e}")

    # Закрываем пул соединений с БД
    await close_pool()

    # Закрываем сессию бота
    await bot.session.close()
    logging.info("🛑 Бот и БД корректно завершили работу")

# Настройка веб-приложения aiohttp
app = web.Application()

# Добавляем маршрут для health check
app.router.add_get("/", health_check)

# Регистрируем обработчик вебхуков Telegram
# Путь должен совпадать с WEBHOOK_PATH из config.py
webhook_request_handler = SimpleRequestHandler(
    dispatcher=dp,
    bot=bot,
    # secret_token=os.getenv("WEBHOOK_SECRET", "your_strong_secret") # Если используете секрет
)
webhook_request_handler.register(app, path=WEBHOOK_PATH)
logging.info(f"Обработчик вебхуков зарегистрирован по пути: {WEBHOOK_PATH}")

# Упрощенная настройка приложения с помощью хелпера aiogram
# Он автоматически добавляет 'bot' и 'dp' в контекст приложения, если нужно
# setup_application(app, dp, bot=bot)

# Регистрируем функции startup и shutdown
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# Запуск приложения
if __name__ == "__main__":
    # Определяем хост и порт для запуска веб-сервера
    # '0.0.0.0' слушает на всех интерфейсах (важно для Docker/Render)
    listen_host = "0.0.0.0"
    # PORT берется из config.py (значение по умолчанию или из .env)
    listen_port = int(os.getenv("PORT", PORT))

    logging.info(f"Запуск веб-сервера на {listen_host}:{listen_port}")
    web.run_app(app, host=listen_host, port=listen_port)

# --- END OF FILE main.py ---
