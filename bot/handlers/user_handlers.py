# --- START OF FILE bot/handlers/admin_handlers.py ---

import io
import logging
from datetime import datetime, timedelta, timezone
# ... другие импорты ...
from aiogram import Router, Bot
from aiogram.types import Message, InputFile
from aiogram.filters import Command
# ... другие импорты ...

from db.db import (
    get_registered_chats,
    get_messages_for_summary
    # УБИРАЕМ get_setting, set_setting, если они больше не нужны
    # get_setting,
    # set_setting
)
from api_clients.openrouter import summarize_chat
from config.config import ADMIN_CHAT_ID

# ... (код настройки шрифта PDF) ...

router = Router()

# ... (Проверка ADMIN_CHAT_ID при запуске) ...
# ... (Определение ADMIN_FILTER, если нужен для /chats, /pdf) ...

# --- УДАЛИТЬ ИЛИ ЗАКОММЕНТИРОВАТЬ ХЭНДЛЕР CMD_SET_PROMPT ---
# @router.message(Command("set_prompt")) # Убрали фильтр, проверка внутри
# async def cmd_set_prompt(message: Message):
#     logging.debug(f"Хэндлер /set_prompt вызван пользователем {message.from_user.id}.")
#     if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
#         logging.warning(f"Доступ к /set_prompt запрещен для user {message.from_user.id}.")
#         return
#     logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /set_prompt")
#     new_prompt = message.text.split(maxsplit=1)[1].strip() if ' ' in message.text else ""
#     if not new_prompt:
#         await message.reply("❗️ Укажите новый шаблон после команды.\nПример: `/set_prompt Сделай краткую сводку:`")
#         return
#     try:
#         # await set_setting("summary_prompt", new_prompt) # Больше не сохраняем
#         await message.reply("✅ Команда /set_prompt больше не используется.") # Сообщаем пользователю
#     except Exception as e:
#         logging.exception(f"Ошибка при обработке отключенной команды /set_prompt: {e}")
#         await message.reply("❌ Ошибка.")


# --- Хэндлеры /chats и /pdf (остаются с внутренней проверкой) ---
@router.message(Command("chats"))
async def cmd_chats(message: Message):
    # ... (код cmd_chats с внутренней проверкой) ...

@router.message(Command("pdf"))
async def cmd_pdf(message: Message):
    # ... (код cmd_pdf с внутренней проверкой) ...


# --- Функция отправки сводки (ИЗМЕНЕНА) ---
async def send_summary(bot: Bot, chat_id: int):
    logging.info(f"Начало генерации сводки для чата {chat_id}")
    now_aware = datetime.now(timezone.utc)
    since_aware = now_aware - timedelta(days=1)

    logging.info(f"Запрос сообщений для сводки чата {chat_id} с {since_aware.isoformat()}")
    try:
        messages_data = await get_messages_for_summary(chat_id, since=since_aware)
        logging.info(f"📥 Получено сообщений: {len(messages_data)} для чата {chat_id}")
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении сообщений для сводки чата {chat_id}: {e}")
        return

    MIN_MESSAGES_FOR_SUMMARY = 5
    if not messages_data or len(messages_data) < MIN_MESSAGES_FOR_SUMMARY:
        logging.info(f"Недостаточно сообщений ({len(messages_data)}) для сводки в чате {chat_id}.")
        return

    message_blocks = []
    for m in messages_data:
        # ... (код формирования блоков сообщений остается) ...
        msg_timestamp = m["timestamp"]
        if msg_timestamp.tzinfo is None: msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
        elif msg_timestamp.tzinfo != timezone.utc: msg_timestamp = msg_timestamp.astimezone(timezone.utc)
        ts = msg_timestamp.strftime('%H:%M')
        sender = m.get("username", "Unknown")
        text = m.get("text", "") or "[пусто]"
        MAX_MSG_LEN = 1000
        message_blocks.append(f"[{ts}] {sender}: {text[:MAX_MSG_LEN]}")

    # ----> ИЗМЕНЕНИЕ ЗДЕСЬ: УСТАНАВЛИВАЕМ ТОЛЬКО ОДИН ПРОМПТ <----
    # Замените текст ниже на ваш желаемый промпт
    summary_prompt = """
Сделай краткую и структурированную сводку (summary) сообщений из этого чата за последние 24 часа.
Включи следующие пункты:
1.  **Основные темы:** Перечисли 2-3 главные темы, которые обсуждались.
2.  **Ключевые моменты/Решения:** Были ли приняты какие-то решения или озвучены важные идеи?
3.  **Настроение:** Кратко опиши общую атмосферу чата (например, деловая, дружелюбная, напряженная).
Ответ должен быть только на русском языке. Будь лаконичен.
    """.strip()
    logging.info(f"Используется стандартный промпт для чата {chat_id}.")
    # ----> КОНЕЦ ИЗМЕНЕНИЯ <----

    logging.info(f"⏳ Отправляем {len(message_blocks)} блоков сообщений в OpenAI для чата {chat_id}...")
    summary_text = None
    try:
        # Передаем только один системный промпт
        summary_text = await summarize_chat(message_blocks, system_prompt=summary_prompt)
    except Exception as e:
        logging.exception(f"❌ Ошибка при запросе к OpenAI для чата {chat_id}: {e}")
        try: await bot.send_message(chat_id, "⚠️ Произошла ошибка при генерации сводки.")
        except Exception: pass
        return

    if not summary_text:
        logging.warning(f"OpenAI вернул пустую сводку для чата {chat_id}.")
        return

    try:
        full_summary_text = f"📝 <b>Сводка за последние 24 часа:</b>\n\n{summary_text}"
        MAX_LEN = 4096
        for i in range(0, len(full_summary_text), MAX_LEN):
            await bot.send_message(chat_id, full_summary_text[i:i + MAX_LEN], parse_mode="HTML")
        logging.info(f"✅ Сводка успешно отправлена в чат {chat_id}")
        # Убрали сохранение времени последней сводки, т.к. set_setting больше не нужен
        # await set_setting(f"last_summary_ts_{chat_id}", now_aware.isoformat())
    except Exception as e:
        logging.exception(f"❌ Ошибка при отправке сводки в чат {chat_id}: {e}")


# --- Настройка планировщика ---
# (код setup_scheduler без изменений)
def setup_scheduler(bot: Bot):
    # ...

# --- Функция запуска сводок по расписанию ---
# (код trigger_all_summaries без изменений, НО теперь он не будет проверять last_summary_ts)
async def trigger_all_summaries(bot: Bot):
    logging.info("🚀 Запуск ежедневной рассылки сводок по расписанию...")
    try:
        registered_chats = await get_registered_chats()
        logging.info(f"Найдено {len(registered_chats)} зарегистрированных чатов для отправки сводки.")
        if not registered_chats:
            logging.info("Нет зарегистрированных чатов, рассылка не требуется.")
            return

        # Убрали проверку времени последней сводки, т.к. больше не сохраняем его
        # current_time = datetime.now(timezone.utc)

        for chat_id in registered_chats:
            # should_send = True
            # ... (код проверки удален) ...

            # if should_send: # Всегда отправляем
            logging.info(f"Запуск задачи отправки сводки для чата {chat_id}...")
            try:
                await send_summary(bot, chat_id)
            except Exception as e:
                logging.exception(f"❌ Исключение при вызове send_summary для чата {chat_id} в планировщике: {e}")

    except Exception as e:
        logging.exception(f"❌ Критическая ошибка при выполнении trigger_all_summaries: {e}")
    finally:
        logging.info("🏁 Ежедневная рассылка сводок завершена.")

# --- END OF FILE admin_handlers.py ---
