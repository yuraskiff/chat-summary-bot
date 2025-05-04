# --- START OF FILE main.py ---

import os
import logging
import sys
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.types import Update, Message
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Импортируем роутеры и функцию настройки планировщика
from bot.handlers import user_handlers, chat_handlers, admin_handlers
# from bot.middleware.auth_middleware import AuthMiddleware

# Импортируем функции для работы с БД и конфигурацию
try:
    from db.db import init_pool, close_pool
    from config.config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PATH, PORT, ADMIN_CHAT_ID
except (ImportError, ValueError) as e:
     logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s - %(levelname)s - %(message)s")
     logging.critical(f"Критическая ошибка при загрузке конфигурации или зависимостей: {e}")
     sys.exit(f"Критическая ошибка конфигурации: {e}")

load_dotenv()

# --- Настройка логирования ---
# ----> ИЗМЕНЕНИЕ: Устанавливаем уровень DEBUG и добавляем имя логгера в формат <----
logging.basicConfig(
    level=logging.DEBUG, # Ставим DEBUG, чтобы видеть больше сообщений
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s", # Добавлено имя логгера (name)
    datefmt='%Y-%m-%d %H:%M:%S',
    # Убедимся, что вывод идет в stdout/stderr (стандарт для Render)
    stream=sys.stdout,
    force=True # Принудительно перенастраиваем, если basicConfig уже вызывался где-то
)
# Уменьшаем "болтливость" библиотек, но оставляем INFO для aiogram.dispatcher
logging.getLogger("aiogram.client.session").setLevel(logging.INFO)
logging.getLogger("aiogram.webhook.aiohttp_server").setLevel(logging.DEBUG) # DEBUG для вебхук сервера
logging.getLogger("aiogram.dispatcher").setLevel(logging.DEBUG) # DEBUG для диспетчера
logging.getLogger("aiohttp.access").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO) # Оставляем INFO для планировщика
logging.getLogger("asyncpg").setLevel(logging.INFO) # INFO для asyncpg

# Логгер для нашего приложения
logger = logging.getLogger(__name__)


# ----> MIDDLEWARE С ДОПОЛНИТЕЛЬНЫМ ЛОГИРОВАНИЕМ <----
class UpdateTypeLoggerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        logger.debug(f">>> DP Update Middleware: Вход - обновление ID {event.update_id}, тип: {type(event).__name__}")
        if isinstance(event, Message):
             log_prefix = ">>> DP Update Middleware:"
             user_info = f"от user_id:{event.from_user.id}" if event.from_user else "от неизвестного пользователя"
             chat_info = f"в chat_id:{event.chat.id} (тип:{event.chat.type})"
             text_info = f"Текст: '{event.text}'" if event.text else "Нет текста"
             caption_info = f"Подпись: '{event.caption}'" if event.caption else ""
             logger.debug(f"{log_prefix} Детали Message: {user_info} {chat_info}. {text_info} {caption_info}")
        try:
            # ----> ДОБАВЛЕНО ЛОГИРОВАНИЕ ПЕРЕД ВЫЗОВОМ HANDLER <----
            logger.debug(f">>> DP Update Middleware: Передача обновления ID {event.update_id} дальше по цепочке...")
            result = await handler(event, data)
            logger.debug(f">>> DP Update Middleware: Обработка обновления ID {event.update_id} успешно завершена хэндлером.")
            return result
        except Exception as e:
             logger.exception(f">>> DP Update Middleware: Исключение во время обработки обновления ID {event.update_id}!")
             raise

# --- Инициализация Bot и Dispatcher ---
try:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    logger.info("Bot и Dispatcher инициализированы.")
except Exception as e:
    logger.exception("Критическая ошибка при инициализации Bot или Dispatcher.")
    sys.exit("Ошибка инициализации Aiogram.")

# --- Подключение Middleware ---
# dp.message.middleware(AuthMiddleware()) # Оставляем закомментированным
dp.update.middleware(UpdateTypeLoggerMiddleware())
logger.info("UpdateTypeLoggerMiddleware подключен ко всем обновлениям (dp.update).")

# --- Подключение роутеров ---
dp.include_router(user_handlers.router)
dp.include_router(chat_handlers.router)
dp.include_router(admin_handlers.router)
logger.info("Роутеры подключены: user, chat, admin.")

# --- Функции жизненного цикла веб-приложения ---

async def health_check(request: web.Request) -> web.Response:
    logger.debug("Получен запрос на health_check (/)")
    return web.Response(text="OK")

async def on_startup(app: web.Application):
    logger.info("Запуск приложения on_startup...")
    current_bot = app.get('bot') or bot

    try:
        await init_pool()
    except Exception as e:
        logger.critical(f"❌ Не удалось инициализировать БД в on_startup: {e}. Завершение работы.")
        raise web.GracefulExit() from e

    try:
        admin_handlers.setup_scheduler(current_bot)
    except Exception as e:
        logger.error(f"⚠️ Не удалось настроить или запустить планировщик в on_startup: {e}")

    webhook_host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or WEBHOOK_HOST
    if not webhook_host:
        logger.critical("❌ Не задан хост для webhook (RENDER_EXTERNAL_HOSTNAME или WEBHOOK_HOST)")
        raise web.GracefulExit("Webhook host is not set")

    webhook_url = f"https://{webhook_host}{WEBHOOK_PATH}"
    logger.info(f"▶ Установка WEBHOOK_URL: {webhook_url}")

    try:
        used_update_types = dp.resolve_used_update_types()
        # ----> ДОБАВЛЕНО ЛОГИРОВАНИЕ ТИПОВ ОБНОВЛЕНИЙ <----
        logger.info(f"Типы обновлений, используемые диспетчером: {used_update_types}")
        await current_bot.set_webhook(
            webhook_url,
            allowed_updates=used_update_types
        )
        logger.info(f"🚀 Webhook успешно установлен: {webhook_url}")
    except Exception as e:
        logger.critical(f"❌ Не удалось установить webhook ({webhook_url}): {e}")
        raise web.GracefulExit() from e
    logger.info("Функция on_startup завершена.")


async def on_shutdown(app: web.Application):
    logger.info("🏁 Завершение работы приложения on_shutdown...")
    current_bot = app.get('bot') or bot

    logger.info("Удаление вебхука...")
    try:
        webhook_info = await current_bot.get_webhook_info()
        if webhook_info.url:
            await current_bot.delete_webhook()
            logger.info("Webhook удален.")
        else:
            logger.info("Вебхук не был установлен, удаление не требуется.")
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении webhook: {e}")

    await close_pool()

    logger.info("Закрытие сессии бота...")
    await current_bot.session.close()
    logger.info("Сессия бота закрыта.")
    logger.info("🛑 Функция on_shutdown завершена.")

# --- Настройка и запуск веб-приложения ---
def main():
    app = web.Application()
    app.router.add_get("/", health_check)

    webhook_request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_request_handler.register(app, path=WEBHOOK_PATH)
    logger.info(f"Обработчик вебхуков Telegram зарегистрирован по пути: {WEBHOOK_PATH}")

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    listen_host = "0.0.0.0"
    listen_port = PORT
    logger.info(f"Запуск веб-сервера на http://{listen_host}:{listen_port}")
    try:
        web.run_app(app, host=listen_host, port=listen_port, print=None)
    except OSError as e:
        logger.critical(f"Не удалось запустить веб-сервер на порту {listen_port}: {e}")
        sys.exit(f"Порт {listen_port} занят.")
    except Exception as e:
        logger.exception(f"Критическая ошибка при запуске веб-сервера: {e}")
        sys.exit("Ошибка запуска веб-сервера.")

if __name__ == "__main__":
    logger.info("Запуск main функции...")
    main()

# --- END OF FILE main.py ---
