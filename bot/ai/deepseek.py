"""
Анализ текста проблемы через DeepSeek.
"""
import asyncio
from openai import AsyncOpenAI

from bot.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_REQUEST_TIMEOUT,
    DEEPSEEK_MAX_RETRIES,
    DEEPSEEK_RETRY_DELAY,
)
from bot.logger import log
from bot.instructions import INSTRUCTIONS

_deepseek_client: AsyncOpenAI | None = None


def _get_deepseek_client() -> AsyncOpenAI:
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
    return _deepseek_client


DEEPSEEK_KEYS_LIST = """
- 'нет связи'
- 'весы'
- '115'
- 'команда не поддерживается в данном режиме'
- 'ошибка при печати на фр: смена на фр кончилась! 24 часа с момента первой продажи истекли! необходимо снять отчет с гашением или закрыть смену!'
- '69'
- 'Сумма всех меньше итога'
- 'не прогружаются весы, прогрузить весы, прогрузка весов'
- 'не работает интернет'
- '34'
- 'неверная дата'
- 'печать отключена'
- 'терминал каспи'
- 'терминал джусан'
- 'чек'
- 'Kaspi'
- 'Halyk'
- 'не удалось выгрузить товары в весы'
- 'ошибка печати полного чека: Field 'note' not found'
- 'модуль печати'
""".strip()


async def analyze_text_with_deepseek(text: str) -> dict | None:
    """Анализирует текст с помощью DeepSeek, возвращает инструкцию или None."""
    try:
        client = _get_deepseek_client()
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты ассистент техподдержки. "
                    "По описанию проблемы выбери ОДИН ключ инструкции из списка и верни только его, без пояснений. "
                    "Если ничего не подходит — верни 'не найдено'."
                ),
            },
            {
                "role": "user",
                "content": f"Проблема: {text}\n\nСписок допустимых ключей:\n{DEEPSEEK_KEYS_LIST}",
            },
        ]
        last_error = None
        response = None
        for attempt in range(DEEPSEEK_MAX_RETRIES + 1):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        max_tokens=40,
                        temperature=0.1,
                        stream=False,
                    ),
                    timeout=DEEPSEEK_REQUEST_TIMEOUT,
                )
                break
            except Exception as e:
                last_error = e
                log(f"⚠️ Ошибка DeepSeek (попытка {attempt + 1}/{DEEPSEEK_MAX_RETRIES + 1}): {e}", "ERROR")
                if attempt < DEEPSEEK_MAX_RETRIES:
                    await asyncio.sleep(DEEPSEEK_RETRY_DELAY * (attempt + 1))

        if not response or not response.choices:
            log(f"✗ Не удалось получить ответ DeepSeek: {last_error}", "ERROR")
            return None

        result = (response.choices[0].message.content or "").strip().lower()
        log(f"🤖 DeepSeek анализ текста: '{result}'")
        if result in INSTRUCTIONS:
            return INSTRUCTIONS[result]
        if result == "не найдено":
            return None
        for key in INSTRUCTIONS:
            if key in result:
                return INSTRUCTIONS[key]
        return None
    except Exception as e:
        log(f"✗ Ошибка DeepSeek анализ текста: {e}", "ERROR")
        return None
