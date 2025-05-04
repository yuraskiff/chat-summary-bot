# --- START OF FILE api_clients/openrouter.py ---

import httpx
import logging
# import textwrap # <--- УДАЛЕН НЕНУЖНЫЙ ИМПОРТ
from typing import List, Optional, Dict
from config.config import OPENROUTER_API_KEY

# --- Константы ---
MODEL = "deepseek/deepseek-chat" # Или "deepseek/deepseek-chat-v3-0324:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(10.0, read=60.0)
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "HTTP-Referer": "https://chat-summary-bot.onrender.com",
    "X-Title": "Chat Summary Bot",
    "Content-Type": "application/json",
}
CONTEXT_MAX_LENGTH = 15000

# --- Функция для запроса сводки ---
async def summarize_chat(
    chat_history_blocks: List[str],
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None # Этот аргумент теперь ОБЯЗАТЕЛЕН (или должен иметь проверку)
) -> Optional[str]:
    """
    Отправляет историю чата и промпты на модель через OpenRouter API.
    """
    if not OPENROUTER_API_KEY:
        logging.error("Ключ API OpenRouter (OPENROUTER_API_KEY) не установлен.")
        return None

    # Проверяем, был ли передан user_prompt (из admin_handlers он передается всегда)
    if not user_prompt:
         logging.error("Отсутствует обязательный user_prompt для функции summarize_chat.")
         # Можно вернуть None или использовать какой-то минимальный запасной промпт
         # return None
         user_prompt = "Сделай краткую сводку следующей истории чата." # Минимальный fallback

    # --- Подготовка промптов ---
    final_system_prompt = system_prompt or "Ты — ИИ-ассистент, специализирующийся на анализе и кратком изложении (summary) переписок в чатах."
    # ----> БЛОК С DEFAULT_USER_PROMPT УДАЛЕН <----
    # ----> ИСПОЛЬЗУЕМ ПЕРЕДАННЫЙ USER_PROMPT НАПРЯМУЮ <----
    final_user_prompt = user_prompt

    # --- Подготовка истории сообщений (с обрезкой) ---
    trimmed_history = ""
    current_length = 0
    for block in reversed(chat_history_blocks):
        block_len = len(block) + 1
        if current_length + block_len <= CONTEXT_MAX_LENGTH:
            trimmed_history = block + "\n" + trimmed_history
            current_length += block_len
        else:
            logging.warning(f"История чата обрезана до ~{current_length} символов из-за лимита ({CONTEXT_MAX_LENGTH}).")
            break

    if not trimmed_history:
        logging.warning("История сообщений для отправки в API пуста.")
        return None

    # --- Формирование запроса к API ---
    messages = [
        {"role": "system", "content": final_system_prompt},
        {"role": "user", "content": final_user_prompt},
        {"role": "user", "content": "Вот история сообщений для анализа:\n\n" + trimmed_history.strip()}
    ]
    request_payload = { "model": MODEL, "messages": messages }

    # --- Выполнение запроса ---
    logging.info(f"📤 Отправка запроса в OpenRouter (модель: {MODEL}, символов истории: ~{current_length})")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(API_URL, headers=HEADERS, json=request_payload)
            logging.info(f"Ответ от OpenRouter получен, статус: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            if "choices" in data and data["choices"] and "message" in data["choices"][0] and "content" in data["choices"][0]["message"]:
                summary_text = data["choices"][0]["message"]["content"].strip()
                logging.info(f"✅ Получена сводка от модели '{MODEL}' (длина: {len(summary_text)} символов).")
                logging.debug(f"Начало сводки: '{summary_text[:100]}...'")
                return summary_text
            else:
                logging.error(f"❌ Неожиданная структура ответа от OpenRouter: {data}")
                return None
    # ... (обработка ошибок остается без изменений) ...
    except httpx.HTTPStatusError as e:
        logging.exception(f"❌ HTTP ошибка от OpenRouter: Статус {e.response.status_code}")
        try: error_details = e.response.json(); logging.error(f"Детали ошибки от OpenRouter: {error_details}")
        except Exception: logging.error(f"Тело ответа при ошибке: {e.response.text}")
        if e.response.status_code == 429: logging.warning("⏳ Достигнут лимит запросов OpenRouter (429).")
        return None
    except httpx.TimeoutException as e:
         logging.error(f"❌ Таймаут при запросе к OpenRouter: {e}")
         return None
    except Exception as e:
        logging.exception(f"❌ Непредвиденная ошибка при запросе к OpenRouter: {e}")
        return None

# --- END OF FILE api_clients/openrouter.py ---
