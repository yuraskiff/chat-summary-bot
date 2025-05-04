# --- START OF FILE main.py ---

import os
import logging
import sys # Для sys.exit
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
# ----> ДОБАВЛЕН ИМПОРТ <----
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Импортируем роутеры и функцию настройки планировщика
from bot.handlers import user_handlers, chat_handlers, admin_handlers
from bot.middleware.auth_middleware import AuthMiddleware

# Импортируем функции для работы с БД и конфигурацию
try:
    from db.db import init_pool, close_pool
    from config.config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PATH, PORT, ADMIN_CHAT_ID
except (ImportError, ValueError) as e:
     logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s - %(levelname)s - %(message)s")
     logging.critical(f"Критическая ошибка при загрузке конфигурации или зависимостей: {e}")
     sys.exit(f"Критическая ошибка конфигурации: {e}")

# Загружаем переменные окружения из .env файла
load_dotenv()

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
)
logging.getLogger("aiogram.client.session").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.INFO)
logging.getLogger("apscheduler.scheduler").setLevel(logging.INFO)
logging.getLogger("asyncpg").setLevel(logging.WARNING)

# --- Инициализация Bot и Dispatcher ---
try:
    # ----> ИЗМЕНЕНА СТРОКА ИНИЦИАЛИЗАЦИИ BOT <----
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    logging.info("Bot и Dispatcher инициализированы.")
except Exception as e:
    logging.exception("Критическая ошибка при инициализации Bot или Dispatcher.")
    sys.exit("Ошибка инициализации Aiogram.")

# --- Подключение Middleware ---
if ADMIN_CHAT_ID:
    dp.message.middleware(AuthMiddleware())
    logging.info("AuthMiddleware подключен.")
else:
    logging.warning("AuthMiddleware не подключен, т.к. ADMIN_CHAT_ID не задан.")

# --- Подключение роутеров ---
dp.include_router(user_handlers.router)
dp.include_router(chat_handlers.router)
dp.include_router(admin_handlers.router)
logging.info("Роутеры подключены: user, chat, admin.")

# --- Функции жизненного цикла веб-приложения ---

async def health_check(request: web.Request) -> web.Response:
    """Простая проверка доступности сервиса."""
    return web.Response(text="OK")

async def on_startup(app: web.Application):
    """Выполняется при старте веб-приложения."""
    logging.info("Запуск приложения...")
    current_bot = app.get('bot') or bot

    try:
        await init_pool()
        logging.info("✅ Пул БД успешно инициализирован")
    except Exception as e:
        logging.critical(f"❌ Не удалось инициализировать БД: {e}. Завершение работы.")
        raise web.GracefulExit() from e

    try:
        admin_handlers.setup_scheduler(current_bot)
    except Exception as e:
        logging.error(f"⚠️ Не удалось настроить или запустить планировщик: {e}")

    webhook_host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or WEBHOOK_HOST
    if not webhook_host:
        logging.critical("❌ Не задан хост для webhook (RENDER_EXTERNAL_HOSTNAME или WEBHOOK_HOST)")
        raise web.GracefulExit("Webhook host is not set")

    webhook_url = f"https://{webhook_host}{WEBHOOK_PATH}"
    logging.info(f"▶ Используем WEBHOOK_URL: {webhook_url}")

    try:
        await current_bot.set_webhook(
            webhook_url,
            allowed_updates=dp.resolve_used_update_types()
        )
        logging.info(f"🚀 Webhook установлен: {webhook_url}")
        logging.info(f"Разрешенные типы обновлений: {dp.resolve_used_update_types()}")
    except Exception as e:
        logging.critical(f"❌ Не удалось установить webhook ({webhook_url}): {e}")
        raise web.GracefulExit() from e

async def on_shutdown(app: web.Application):
    """Выполняется при остановке веб-приложения."""
    logging.info("🏁 Завершение работы приложения...")
    current_bot = app.get('bot') or bot

    logging.info("Удаление вебхука...")
    try:
        await current_bot.delete_webhook()
        logging.info("Webhook удален.")
    except Exception as e:
        logging.error(f"❌ Ошибка при удалении webhook: {e}")

    scheduler = app.get('scheduler')
    if scheduler and scheduler.running:
         try:
             scheduler.shutdown()
             logging.info("Планировщик остановлен.")
         except Exception as e:
             logging.error(f"Ошибка при остановке планировщика: {e}")

    await close_pool()

    logging.info("Закрытие сессии бота...")
    await current_bot.session.close()
    logging.info("Сессия бота закрыта.")
    logging.info("🛑 Приложение корректно завершило работу.")

# --- Настройка и запуск веб-приложения ---
def main():
    """Основная функция для настройки и запуска."""
    app = web.Application()
    app.router.add_get("/", health_check)

    webhook_request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_request_handler.register(app, path=WEBHOOK_PATH)
    logging.info(f"Обработчик вебхуков зарегистрирован по пути: {WEBHOOK_PATH}")

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    listen_host = "0.0.0.0"
    listen_port = PORT
    logging.info(f"Запуск веб-сервера на http://{listen_host}:{listen_port}")
    try:
        web.run_app(app, host=listen_host, port=listen_port)
    except OSError as e:
        logging.critical(f"Не удалось запустить веб-сервер на порту {listen_port}: {e}")
        sys.exit(f"Порт {listen_port} занят.")
    except Exception as e:
        logging.exception(f"Критическая ошибка при запуске веб-сервера: {e}")
        sys.exit("Ошибка запуска веб-сервера.")

if __name__ == "__main__":
    main()

# --- END OF FILE main.py ---
