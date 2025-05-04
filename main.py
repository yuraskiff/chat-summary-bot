# --- START OF FILE main.py ---

import os
import logging
import sys # Для sys.exit
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
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
     # Ловим ошибки импорта или ValueErrors из config.py на самом раннем этапе
     logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s - %(levelname)s - %(message)s")
     logging.critical(f"Критическая ошибка при загрузке конфигурации или зависимостей: {e}")
     sys.exit(f"Критическая ошибка конфигурации: {e}")

# Загружаем переменные окружения из .env файла (на случай локального запуска)
load_dotenv()

# --- Настройка логирования ---
# Устанавливаем базовую конфигурацию
logging.basicConfig(
    level=logging.INFO, # Уровень логирования по умолчанию
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
    # handlers=[ # Можно настроить вывод в файл
    #     logging.FileHandler("bot.log", encoding='utf-8'),
    #     logging.StreamHandler(sys.stdout) # Вывод в консоль
    # ]
)
# Уменьшаем "болтливость" библиотек
logging.getLogger("aiogram.client.session").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.INFO) # Оставляем INFO для access логов aiohttp
logging.getLogger("apscheduler.scheduler").setLevel(logging.INFO)
logging.getLogger("asyncpg").setLevel(logging.WARNING)

# --- Инициализация Bot и Dispatcher ---
try:
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()
    logging.info("Bot и Dispatcher инициализированы.")
except Exception as e:
    logging.exception("Критическая ошибка при инициализации Bot или Dispatcher.")
    sys.exit("Ошибка инициализации Aiogram.")

# --- Подключение Middleware ---
# Middleware применяется ко всем Message обновлениям
# Убедитесь, что AuthMiddleware написан корректно
if ADMIN_CHAT_ID: # Подключаем middleware только если админ ID задан
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
    # TODO: Добавить проверку доступности БД и OpenAI, если нужно
    return web.Response(text="OK")

async def on_startup(app: web.Application):
    """Выполняется при старте веб-приложения."""
    logging.info("Запуск приложения...")
    # Получаем объект бота из контекста приложения (если используем setup_application)
    # Или используем глобальный объект bot, как сейчас
    current_bot = app.get('bot') or bot # Используем bot из app или глобальный

    # Инициализация пула соединений с БД
    try:
        await init_pool()
        logging.info("✅ Пул БД успешно инициализирован")
    except Exception as e:
        logging.critical(f"❌ Не удалось инициализировать БД: {e}. Завершение работы.")
        raise web.GracefulExit() from e

    # Настройка и запуск планировщика
    try:
        admin_handlers.setup_scheduler(current_bot)
    except Exception as e:
        logging.error(f"⚠️ Не удалось настроить или запустить планировщик: {e}")
        # Не останавливаем работу, но логируем

    # Определение хоста для вебхука
    webhook_host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or WEBHOOK_HOST
    if not webhook_host:
        logging.critical("❌ Не задан хост для webhook (RENDER_EXTERNAL_HOSTNAME или WEBHOOK_HOST)")
        raise web.GracefulExit("Webhook host is not set")

    # Формирование URL вебхука
    webhook_url = f"https://{webhook_host}{WEBHOOK_PATH}"
    logging.info(f"▶ Используем WEBHOOK_URL: {webhook_url}")

    # Установка вебхука
    try:
        # webhook_secret = os.getenv("WEBHOOK_SECRET") # Получаем секрет, если он есть
        await current_bot.set_webhook(
            webhook_url,
            # secret_token=webhook_secret, # Передаем секрет, если используем
            allowed_updates=dp.resolve_used_update_types() # Автоматически определяем нужные типы обновлений
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

    # Удаляем вебхук
    logging.info("Удаление вебхука...")
    try:
        await current_bot.delete_webhook()
        logging.info("Webhook удален.")
    except Exception as e:
        logging.error(f"❌ Ошибка при удалении webhook: {e}")

    # Остановка планировщика (если он был сохранен в app)
    scheduler = app.get('scheduler') # Пример, если сохраняли планировщик
    if scheduler and scheduler.running:
         try:
             scheduler.shutdown()
             logging.info("Планировщик остановлен.")
         except Exception as e:
             logging.error(f"Ошибка при остановке планировщика: {e}")

    # Закрываем пул соединений с БД
    await close_pool()

    # Закрываем сессию бота
    logging.info("Закрытие сессии бота...")
    await current_bot.session.close()
    logging.info("Сессия бота закрыта.")
    logging.info("🛑 Приложение корректно завершило работу.")

# --- Настройка и запуск веб-приложения ---
def main():
    """Основная функция для настройки и запуска."""
    app = web.Application()

    # Добавляем маршрут для health check
    app.router.add_get("/", health_check)

    # Настройка обработчика вебхуков Telegram
    webhook_request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        # secret_token=os.getenv("WEBHOOK_SECRET") # Если используете секрет
    )
    # Регистрируем по пути из конфига
    webhook_request_handler.register(app, path=WEBHOOK_PATH)
    logging.info(f"Обработчик вебхуков зарегистрирован по пути: {WEBHOOK_PATH}")

    # Можно использовать setup_application для добавления bot и dp в контекст app
    # setup_application(app, dp, bot=bot)

    # Регистрируем функции startup и shutdown
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Запуск веб-сервера
    listen_host = "0.0.0.0"
    listen_port = PORT
    logging.info(f"Запуск веб-сервера на http://{listen_host}:{listen_port}")
    try:
        web.run_app(app, host=listen_host, port=listen_port)
    except OSError as e:
        # Ловим ошибку "address already in use"
        logging.critical(f"Не удалось запустить веб-сервер на порту {listen_port}: {e}")
        sys.exit(f"Порт {listen_port} занят.")
    except Exception as e:
        logging.exception(f"Критическая ошибка при запуске веб-сервера: {e}")
        sys.exit("Ошибка запуска веб-сервера.")

if __name__ == "__main__":
    main()

# --- END OF FILE main.py ---
