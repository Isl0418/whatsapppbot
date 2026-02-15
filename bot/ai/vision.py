"""
Анализ фото: EasyOCR + OpenAI GPT-4o-mini (vision).
"""
import asyncio
import base64
from openai import AsyncOpenAI

from bot.config import (
    OPENAI_API_KEY,
    OPENAI_REQUEST_TIMEOUT,
    OPENAI_MAX_RETRIES,
    OPENAI_RETRY_DELAY,
)
from bot.logger import log
from bot.instructions import find_by_keywords

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://api.openai.com/v1",
        )
    return _openai_client


def extract_text_easyocr(image_path: str) -> str | None:
    """Локальный OCR через EasyOCR (опционально)."""
    try:
        import easyocr
    except Exception as e:
        log(f"⚠️ EasyOCR недоступен: {e}", "WARNING")
        return None
    try:
        reader = easyocr.Reader(["ru", "en"])
        results = reader.readtext(image_path, detail=0, paragraph=True)
        full_text = " ".join(results).strip()
        if full_text:
            log(f"📝 EasyOCR распознал: {full_text[:120]}...")
            return full_text
        return None
    except Exception as e:
        log(f"✗ Ошибка EasyOCR: {e}", "ERROR")
        return None


async def _openai_chat_with_retry(**kwargs):
    """Вызов OpenAI с ретраями и таймаутами."""
    client = _get_openai_client()
    last_error = None
    for attempt in range(OPENAI_MAX_RETRIES + 1):
        try:
            return await asyncio.wait_for(
                client.chat.completions.create(**kwargs),
                timeout=OPENAI_REQUEST_TIMEOUT,
            )
        except Exception as e:
            last_error = e
            log(f"⚠️ Ошибка запроса к OpenAI (попытка {attempt + 1}/{OPENAI_MAX_RETRIES + 1}): {e}", "ERROR")
            if attempt < OPENAI_MAX_RETRIES:
                await asyncio.sleep(OPENAI_RETRY_DELAY * (attempt + 1))
            else:
                break
    log(f"✗ Запрос к OpenAI окончательно провален: {last_error}", "ERROR")
    return None


async def analyze_photo_with_gpt4omini(image_path: str) -> dict | None:
    """
    Анализирует фото: EasyOCR → при неудаче GPT-4o-mini.
    Возвращает инструкцию по ключевым словам или None.
    """
    try:
        ocr_text = await asyncio.to_thread(extract_text_easyocr, image_path)
        if ocr_text:
            instruction_from_ocr = find_by_keywords(ocr_text)
            if instruction_from_ocr:
                log("✅ Инструкция найдена по тексту EasyOCR")
                return instruction_from_ocr

        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
        except Exception as e:
            log(f"✗ Ошибка чтения файла изображения: {e}", "ERROR")
            return None

        if len(image_bytes) > 8 * 1024 * 1024:
            log("⚠️ Изображение слишком большое, обрезаем до 8 МБ", "WARNING")
            image_bytes = image_bytes[: 8 * 1024 * 1024]
        image_data = base64.b64encode(image_bytes).decode("utf-8")

        messages = [
            {
                "role": "system",
                "content": (
                    "Ты OCR-ассистент техподдержки. "
                    "Распознай читаемый текст с экрана/ошибки на изображении. "
                    "Верни ТОЛЬКО распознанный текст одним блоком, без пояснений и перевода."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Распознай текст ошибки и сообщения с этого изображения. Верни только текст."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}", "detail": "low"},
                    },
                ],
            },
        ]

        response = await _openai_chat_with_retry(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=160,
            temperature=0.0,
            stream=False,
        )
        if not response or not response.choices:
            log("✗ Пустой ответ GPT-4o-mini при анализе фото", "ERROR")
            return None

        gpt_text = (response.choices[0].message.content or "").strip()
        log(f"🤖 GPT-4o-mini OCR текст: '{gpt_text[:160]}'")
        if not gpt_text:
            return None

        instruction_from_gpt = find_by_keywords(gpt_text)
        if instruction_from_gpt:
            log("✅ Инструкция найдена по тексту GPT-4o-mini")
            return instruction_from_gpt
        log("ℹ️ GPT-4o-mini вернул текст без ключевых слов, инструкцию не отправляем", "INFO")
        return None
    except Exception as e:
        log(f"✗ Ошибка GPT-4o-mini анализ фото: {e}", "ERROR")
        return None
