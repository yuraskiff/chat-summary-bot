# --- START OF FILE main.py ---

import os
import logging
import sys # Для sys.exit
from dotenv import load_dotenv

# ----> ЗАКОММЕНТИРОВАНЫ ИМПОРТЫ MIDDLEWARE <----
# from typing import Callable, Dict, Any, Awaitable
# from aiogram import BaseMiddleware # <--- Закомментировано
# from aiogram.types import Update, Message # <--- Закомментировано (Message может понадобиться в других местах)
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message # Оставим импорт Message, если он нужен где-то еще

from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Импортируем роутеры и функцию настройки планировщика
from bot.handlers import user_handlers, chat_handlers, admin_handlers
# from bot.middleware.auth_middleware import AuthMiddleware # Оставляем закомментированным

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
# Уровень DEBUG остается, чтобы видеть логи aiogram.dispatcher
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
    force=True
)
# Уменьшаем "болтливость" библиотек, но оставляем DEBUG для диспетчера
logging.getLogger("aiogram.client.session").setLevel(logging.INFO)
logging.getLogger("aiogram.webhook.aiohttp_server").setLevel(logging.INFO) # Можно вернуть INFO
logging.getLogger("aiogram.dispatcher").setLevel(logging.DEBUG) # Оставляем DEBUG для диспетчера
logging.getLogger("aiohttp.access").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)
logging.getLogger("asyncpg").setLevel(logging.INFO)

# Логгер для нашего приложения
logger = logging.getLogger(__name__)


# ----> КЛАСС MIDDLEWARE ЗАКОММЕНТИРОВАН <----
# class UpdateTypeLoggerMiddleware(BaseMiddleware):
#     async def __call__(
#         self,
#         handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
#         event: Update, # Ловим все типы Update
#         data: Dict[str, Any]
#     ) -> Any:
#         """Логирует тип входящего обновления и текст сообщения (если есть)."""
#         # Логируем тип полученного обновления и его ID
#         logger.debug(f">>> DP Middleware: Вход - обновление ID {event.update_id}, тип: {type(event).__name__}")
#         # Если это Message, логируем дополнительную информацию
#         if isinstance(event, Message):
#              log_prefix = ">>> DP Middleware:"
#              user_info = f"от user_id:{event.from_user.id}" if event.from_user else "от неизвестного пользователя"
#              chat_info = f"в chat_id:{event.chat.id} (тип:{event.chat.type})"
#              text_info = f"Текст: '{event.text}'" if event.text else "Нет текста"
#              caption_info = f"Подпись: '{event.caption}'" if event.caption else ""
#              logger.debug(f"{log_prefix} Детали Message: {user_info} {chat_info}. {text_info} {caption_info}")
#         try:
#             # ----> ДОБАВЛЕНО ЛОГИРОВАНИЕ ПЕРЕД ВЫЗОВОМ HANDLER <----
#             logger.debug(f">>> DP Middleware: Передача обновления ID {event.update_id} дальше по цепочке...")
#             result = await handler(event, data)
#             logger.debug(f">>> DP Middleware: Обработка обновления ID {event.update_id} успешно завершена хэндлером.")
#             return result
#         except Exception as e:
#              # Логируем исключение, если оно произошло во время обработки
#              logger.exception(f">>> DP Middleware: Исключение во время обработки обновления ID {event.update_id}!")
#              # Перевыбрасываем исключение, чтобы его можно было поймать выше, если нужно
#              raise


# --- Инициализация Bot и Dispatcher ---
try:
    # Используем DefaultBotProperties для parse_mode
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    logger.info("Bot и Dispatcher инициализированы.")
except Exception as e:
    logger.exception("Критическая ошибка при инициализации Bot или Dispatcher.")
    sys.exit("Ошибка инициализации Aiogram.")

# --- Подключение Middleware ---
# dp.message.middleware(AuthMiddleware()) # Оставляем AuthMiddleware закомментированным
# ----> ПОДКЛЮЧЕНИЕ MIDDLEWARE ЗАКОММЕНТИРОВАНО <----
# dp.update.middleware(UpdateTypeLoggerMiddleware())
# logger.info("UpdateTypeLoggerMiddleware подключен ко всем обновлениям (dp.update).")


# --- Подключение роутеров ---
dp.include_router(user_handlers.router)
dp.include_router(chat_handlers.router)
dp.include_router(admin_handlers.router)
logger.info("Роутеры подключены: user, chat, admin.")

# --- Функции жизненного цикла веб-приложения ---

async def health_check(request: web.Request) -> web.Response:
    """Простая проверка доступности сервиса."""
    logger.debug("Получен запрос на health_check (/)")
    return web.Response(text="OK")

async def on_startup(app: web.Application):
    """Выполняется при старте веб-приложения."""
    logger.info("Запуск приложения on_startup...")
    current_bot = app.get('bot') or bot

    # Инициализация пула соединений с БД
    try:
        await init_pool()
    except Exception as e:
        logger.critical(f"❌ Не удалось инициализировать БД в on_startup: {e}. Завершение работы.")
        raise web.GracefulExit() from e

    # Настройка и запуск планировщика
    try:
        admin_handlers.setup_scheduler(current_bot)
    except Exception as e:
        logger.error(f"⚠️ Не удалось настроить или запустить планировщик в on_startup: {e}")

    # Определение хоста для вебхука
    webhook_host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or WEBHOOK_HOST
    if not webhook_host:
        logger.critical("❌ Не задан хост для webhook (RENDER_EXTERNAL_HOSTNAME или WEBHOOK_HOST)")
        raise web.GracefulExit("Webhook host is not set")

    # Формирование URL вебхука
    webhook_url = f"https://{webhook_host}{WEBHOOK_PATH}"
    logger.info(f"▶ Установка WEBHOOK_URL: {webhook_url}")

    # Установка вебхука
    try:
        # Указываем, какие обновления получать (автоопределение из dp)
        used_update_types = dp.resolve_used_update_types()
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
    """Выполняется при остановке веб-приложения."""
    logger.info("🏁 Завершение работы приложения on_shutdown...")
    current_bot = app.get('bot') or bot

    # Удаляем вебхук
    logger.info("Удаление вебхука...")
    try:
        # Проверяем, есть ли активный вебхук перед удалением
        webhook_info = await current_bot.get_webhook_info()
        if webhook_info.url:
            await current_bot.delete_webhook()
            logger.info("Webhook удален.")
        else:
            logger.info("Вебхук не был установлен, удаление не требуется.")
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении webhook: {e}")

    # Закрываем пул соединений с БД
    await close_pool()

    # Закрываем сессию бота
    logger.info("Закрытие сессии бота...")
    await current_bot.session.close()
    logger.info("Сессия бота закрыта.")
    logger.info("🛑 Функция on_shutdown завершена.")

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
    )
    # Регистрируем по пути из конфига
    webhook_request_handler.register(app, path=WEBHOOK_PATH)
    logger.info(f"Обработчик вебхуков Telegram зарегистрирован по пути: {WEBHOOK_PATH}")

    # Регистрируем функции startup и shutdown
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Запуск веб-сервера
    listen_host = "0.0.0.0"
    listen_port = PORT
    logger.info(f"Запуск веб-сервера на http://{listen_host}:{listen_port}")
    try:
        web.run_app(app, host=listen_host, port=listen_port, print=None) # Убираем стандартный вывод aiohttp
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
