# --- START OF FILE bot/handlers/admin_handlers.py ---

import io
import logging
from datetime import datetime, timedelta, timezone
# ... другие импорты ...
from aiogram import Router, Bot, F # Убираем F, если не используем Magic Filter
from aiogram.types import Message, InputFile
from aiogram.filters import Command
# ... остальные импорты ...
from config.config import ADMIN_CHAT_ID # Импортируем ID админа

# ... (код настройки шрифта PDF) ...
PDF_FONT = 'Helvetica'
PDF_FONT_PATH = 'DejaVuSans.ttf'
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', PDF_FONT_PATH))
    PDF_FONT = 'DejaVuSans'
    logging.info(f"Шрифт '{PDF_FONT_PATH}' успешно зарегистрирован для PDF.")
except Exception as e:
    logging.warning(f"Не удалось загрузить шрифт '{PDF_FONT_PATH}' ({e}). Используется '{PDF_FONT}'.")

router = Router()

# --- Проверка ADMIN_CHAT_ID при запуске ---
if ADMIN_CHAT_ID is None:
    logging.warning("ADMIN_CHAT_ID не задан. Админ-команды будут недоступны.")
elif not isinstance(ADMIN_CHAT_ID, int):
     logging.error(f"ADMIN_CHAT_ID '{ADMIN_CHAT_ID}' не является числом. Админ-команды не будут работать.")
     ADMIN_CHAT_ID = None # Устанавливаем в None, чтобы проверки ниже работали корректно
else:
     logging.info(f"ADMIN_CHAT_ID для проверки прав администратора: {ADMIN_CHAT_ID}")

# --- УДАЛЕНЫ Magic Filter и Pre-handler ---
# ADMIN_FILTER = ...
# @router.message(Command("set_prompt", "chats", "pdf")) ...


# --- Основные хэндлеры админских команд с внутренней проверкой ---

# ----> CMD_SET_PROMPT: Убран фильтр, добавлена проверка <----
@router.message(Command("set_prompt"))
async def cmd_set_prompt(message: Message):
    """Устанавливает системный промпт для OpenAI (проверка админа внутри)."""
    logging.info(f"Хэндлер /set_prompt вызван пользователем {message.from_user.id}.")
    # ----> ЯВНАЯ ПРОВЕРКА ПРАВ <----
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /set_prompt запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /set_prompt")

    new_prompt = message.text.split(maxsplit=1)[1].strip() if ' ' in message.text else ""
    if not new_prompt:
        await message.reply("❗️ Укажите новый шаблон после команды.\nПример: `/set_prompt Сделай краткую сводку:`")
        return
    try:
        await set_setting("summary_prompt", new_prompt)
        await message.reply("✅ Шаблон сводки обновлён.")
    except Exception as e:
        logging.exception(f"Ошибка при сохранении настройки summary_prompt: {e}")
        await message.reply("❌ Не удалось сохранить настройку.")

# ----> CMD_CHATS: Оставляем без фильтра, с внутренней проверкой <----
@router.message(Command("chats"))
async def cmd_chats(message: Message):
    """Показывает список активных чатов (проверка админа внутри)."""
    logging.info(f"Хэндлер /chats вызван пользователем {message.from_user.id}.")
    # ----> ЯВНАЯ ПРОВЕРКА ПРАВ <----
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /chats запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /chats")
    try:
        logging.info("Запрашиваю список зарегистрированных чатов из БД...")
        chat_ids = await get_registered_chats()
        logging.info(f"Получено {len(chat_ids)} ID чатов из БД.")
        if not chat_ids:
            await message.reply("Нет зарегистрированных чатов.")
            logging.info("Список чатов пуст.")
            return
        lines = ["<b>Активные чаты:</b>"]
        logging.info("Начинаю получать информацию о чатах от Telegram API...")
        processed_count = 0
        for cid in chat_ids:
            try:
                logging.debug(f"Получение информации для chat_id: {cid}")
                chat_info = await message.bot.get_chat(chat_id=cid)
                title = chat_info.title or chat_info.full_name or f"ID: {cid}"
                link_part = ""
                if chat_info.type in ('group', 'supergroup', 'channel'):
                    invite_link = chat_info.invite_link
                    if invite_link: link_part = f" (<a href='{invite_link}'>ссылка</a>)"
                lines.append(f"• {title} (<code>{cid}</code>){link_part}")
                logging.debug(f"Успешно получена информация для chat_id: {cid}")
                processed_count += 1
            except Exception as e:
                logging.warning(f"Не удалось получить информацию о чате {cid}: {e}")
                lines.append(f"• ID: <code>{cid}</code> (ошибка доступа или чат не существует)")
        logging.info(f"Информация о {processed_count} из {len(chat_ids)} чатов собрана.")
        full_text = "\n".join(lines)
        MAX_LEN = 4096
        logging.info(f"Отправляю список чатов пользователю {message.from_user.id}...")
        for i in range(0, len(full_text), MAX_LEN):
            await message.reply(full_text[i:i + MAX_LEN], parse_mode="HTML")
        logging.info("Список чатов успешно отправлен.")
    except Exception as e:
        logging.exception(f"Критическая ошибка при выполнении команды /chats: {e}")
        await message.reply("❌ Произошла ошибка при получении списка чатов.")

# ----> CMD_PDF: Убран фильтр, добавлена проверка <----
@router.message(Command("pdf"))
async def cmd_pdf(message: Message):
    """Создает PDF с историей сообщений за 24ч (проверка админа внутри)."""
    logging.info(f"Хэндлер /pdf вызван пользователем {message.from_user.id}.")
    # ----> ЯВНАЯ ПРОВЕРКА ПРАВ <----
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /pdf запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /pdf")

    args = message.text.split()
    if len(args) < 2 or not args[1].lstrip('-').isdigit():
        await message.reply("❗️ Укажите ID чата после команды.\nПример: `/pdf -1001234567890`")
        return
    try: chat_id_to_fetch = int(args[1])
    except ValueError:
        await message.reply("❗️ Некорректный ID чата.")
        return
    try:
        since_time = datetime.now(timezone.utc) - timedelta(days=1)
        logging.info(f"Запрос PDF для чата {chat_id_to_fetch} с {since_time.isoformat()}")
        messages_data = await get_messages_for_summary(chat_id_to_fetch, since_time)
        if not messages_data:
            await message.reply(f"Сообщений в чате <code>{chat_id_to_fetch}</code> за последние 24 часа не найдено.")
            return
        # ... (остальной код генерации и отправки PDF без изменений) ...
        logging.info(f"Найдено {len(messages_data)} сообщений для PDF в чате {chat_id_to_fetch}.")
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter; margin = 40
        textobject = c.beginText(); textobject.setTextOrigin(margin, height - margin)
        textobject.setFont(PDF_FONT, 8); line_height = 10
        for msg in messages_data:
            msg_timestamp = msg["timestamp"]
            if msg_timestamp.tzinfo is None: msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
            elif msg_timestamp.tzinfo != timezone.utc: msg_timestamp = msg_timestamp.astimezone(timezone.utc)
            msg_time_str = msg_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
            sender = msg.get("username", "Unknown User"); text = msg.get("text", "") or "[пустое сообщение]"
            header = f"[{msg_time_str}] {sender}:"; lines = simpleSplit(text, PDF_FONT, 8, width - 2 * margin)
            required_lines = 1 + len(lines) + 1
            if textobject.getY() < margin + line_height * required_lines:
                c.drawText(textobject); c.showPage()
                textobject = c.beginText(margin, height - margin); textobject.setFont(PDF_FONT, 8)
            textobject.textLine(header)
            for line in lines: textobject.textLine(f"  {line}")
            textobject.moveCursor(0, line_height / 2)
        c.drawText(textobject); c.save(); buf.seek(0)
        pdf_filename = f"history_{chat_id_to_fetch}_{since_time.strftime('%Y%m%d')}.pdf"
        logging.info(f"Отправка PDF {pdf_filename} пользователю {message.from_user.id}")
        await message.reply_document(InputFile(buf, filename=pdf_filename), caption=f"История чата <code>{chat_id_to_fetch}</code> за последние 24 часа.")
        logging.info("PDF успешно отправлен.")
    except Exception as e:
        logging.exception(f"Ошибка при создании или отправке PDF для чата {chat_id_to_fetch}: {e}")
        await message.reply("❌ Произошла ошибка при создании PDF.")


# --- Функция отправки сводки ---
# (код send_summary без изменений)
async def send_summary(bot: Bot, chat_id: int):
    logging.info(f"Начало генерации сводки для чата {chat_id}")
    # ... (код без изменений) ...

# --- Настройка планировщика ---
# (код setup_scheduler и trigger_all_summaries без изменений)
def setup_scheduler(bot: Bot):
    # ... (код без изменений) ...

async def trigger_all_summaries(bot: Bot):
    # ... (код без изменений) ...

# --- END OF FILE admin_handlers.py ---
