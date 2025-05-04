# --- START OF FILE api_clients/openrouter.py ---

import httpx
import logging
import textwrap
from typing import List, Optional, Dict # Добавили типизацию
from config.config import OPENROUTER_API_KEY

# --- Константы ---
# Модель можно вынести в config.py или .env при желании
# MODEL = "openai/gpt-3.5-turbo" # Используем стандартную модель для начала
MODEL = "deepseek/deepseek-chat-v3-0324:free" # Если хотите DeepSeek
API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Таймауты: 10с на соединение, 60с на чтение ответа
TIMEOUT = httpx.Timeout(10.0, read=60.0)

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    # Рекомендуется указывать реферер и название приложения
    "HTTP-Referer": "https://chat-summary-bot.onrender.com", # Замените на ваш URL или просто оставьте
    "X-Title": "Chat Summary Bot",
    "Content-Type": "application/json",
}

# Примерный лимит символов для контекста модели (зависит от модели)
# Лучше ориентироваться на токены, но для простоты используем символы
CONTEXT_MAX_LENGTH = 8000 # Для gpt-3.5-turbo можно и больше, для free моделей - меньше

# --- Функция для запроса сводки ---
async def summarize_chat(
    chat_history_blocks: List[str],
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None
) -> Optional[str]:
    """
    Отправляет историю чата и промпты на модель через OpenRouter API.
    Возвращает текст сводки или None при ошибке.

    :param chat_history_blocks: Список строк, каждая строка - сообщение из чата.
    :param system_prompt: Системное сообщение для модели (опционально).
    :param user_prompt: Пользовательский промпт для задачи (опционально, используется дефолтный).
    :return: Текст ответа модели или None.
    """
    if not OPENROUTER_API_KEY:
        logging.error("Ключ API OpenRouter (OPENROUTER_API_KEY) не установлен.")
        return None

    # --- Подготовка промптов ---
    final_system_prompt = system_prompt or "Ты — ИИ-ассистент, специализирующийся на анализе и кратком изложении (summary) переписок в чатах."

    default_user_prompt = textwrap.dedent("""
        Проанализируй следующую историю сообщений из группового чата за последние 24 часа.
        Создай краткую сводку (summary), включающую:
        - Основные темы обсуждения.
        - Ключевые решения или выводы (если были).
        - Наиболее активные участники.
        - Общее настроение или тон дискуссии.
        Ответ дай на русском языке. Не включай в ответ приветствия или вступительные фразы, только саму сводку.
    """).strip()
    final_user_prompt = user_prompt or default_user_prompt

    # --- Подготовка истории сообщений (с обрезкой) ---
    trimmed_history = ""
    current_length = 0
    # Собираем историю с конца (самые свежие сообщения важнее)
    for block in reversed(chat_history_blocks):
        block_len = len(block) + 1 # +1 за перенос строки
        if current_length + block_len <= CONTEXT_MAX_LENGTH:
            trimmed_history = block + "\n" + trimmed_history
            current_length += block_len
        else:
            # Если добавление следующего блока превысит лимит, останавливаемся
            logging.warning(f"История чата обрезана до {current_length} символов из-за лимита ({CONTEXT_MAX_LENGTH}).")
            break

    if not trimmed_history:
        logging.warning("История сообщений для отправки в OpenAI пуста.")
        return None

    # --- Формирование запроса к API ---
    messages = [
        {"role": "system", "content": final_system_prompt},
        # Сначала даем инструкцию
        {"role": "user", "content": final_user_prompt},
        # Потом саму историю как одно сообщение от пользователя
        # (можно разделить, но так проще для многих моделей)
        {"role": "user", "content": "Вот история сообщений для анализа:\n\n" + trimmed_history.strip()}
    ]

    request_payload = {
        "model": MODEL,
        "messages": messages,
        # Можно добавить другие параметры, например, temperature
        # "temperature": 0.7,
    }

    # --- Выполнение запроса ---
    logging.info(f"📤 Отправка запроса в OpenRouter (модель: {MODEL}, символов истории: {current_length})")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(API_URL, headers=HEADERS, json=request_payload)

            # Логируем код ответа
            logging.info(f"Ответ от OpenRouter получен, статус: {response.status_code}")

            # Проверяем на ошибки HTTP
            response.raise_for_status()

            data = response.json()

            # Проверяем наличие ответа в ожидаемой структуре
            if "choices" in data and data["choices"] and "message" in data["choices"][0] and "content" in data["choices"][0]["message"]:
                summary_text = data["choices"][0]["message"]["content"].strip()
                logging.info(f"✅ Получена сводка от модели (длина: {len(summary_text)} символов).")
                # Логируем начало ответа для отладки
                logging.debug(f"Начало сводки: '{summary_text[:100]}...'")
                return summary_text
            else:
                logging.error(f"❌ Неожиданная структура ответа от OpenRouter: {data}")
                return None

    except httpx.HTTPStatusError as e:
        logging.exception(f"❌ HTTP ошибка от OpenRouter: Статус {e.response.status_code}")
        try:
            # Пытаемся прочитать тело ответа для диагностики
            error_details = e.response.json()
            logging.error(f"Детали ошибки от OpenRouter: {error_details}")
        except Exception:
            logging.error(f"Тело ответа при ошибке: {e.response.text}")
        # Специально обрабатываем rate limit
        if e.response.status_code == 429:
            logging.warning("⏳ Достигнут лимит запросов OpenRouter (429). Попробуйте позже.")
        return None # Возвращаем None при любой HTTP ошибке
    except httpx.TimeoutException as e:
         logging.error(f"❌ Таймаут при запросе к OpenRouter: {e}")
         return None
    except Exception as e:
        logging.exception(f"❌ Непредвиденная ошибка при запросе к OpenRouter: {e}")
        return None

# --- END OF FILE api_clients/openrouter.py ---
