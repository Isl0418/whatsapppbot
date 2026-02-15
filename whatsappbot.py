import os
import time
import base64
import json
import re
from datetime import datetime

import asyncio
import aiohttp
from openai import AsyncOpenAI


# === НАСТРОЙКИ API ===
DEEPSEEK_API_KEY = "sk-87063cd0ce1b40ae6e15436e32089"  # Для текста
OPENAI_API_KEY = "sk-proj---Cx7lhMyoad-7udPTNHClC_cdkdFb-O45W6BKLE8ucNPgyfGVRMA"  # Для фото (GPT-4o-mini)

# Таймауты и ретраи для внешних API
OPENAI_REQUEST_TIMEOUT = 20  # секунд
OPENAI_MAX_RETRIES = 2
OPENAI_RETRY_DELAY = 2  # секунд между попытками

DEEPSEEK_REQUEST_TIMEOUT = 20  # секунд
DEEPSEEK_MAX_RETRIES = 2
DEEPSEEK_RETRY_DELAY = 2

# Настройки Green API
GREEN_INSTANCE = "7103509463"
GREEN_TOKEN = "c1de9c1eb3164d7cb1fe6adc380d835c56b53fe0564d08bc"

# Чаты (бот будет отвечать только в эти чаты)
ALLOWED_CHATS = [
    "120363420695442782@g.us",  # MAIN_CHAT_ID
]
# Чат поддержки: команды "бот стоп" / "бот старт" и сюда уходят сообщения "инструкция не найдена"
SUPPORT_CHAT_ID = "120363420695442782@g.us"  # можно тот же чат или отдельный
# Номера техподдержки (бот им не отвечает)
TECH_SUPPORT_NUMBERS = [
    "77071958118@c.us",
    "77017055408@c.us",
    "77053201050@c.us",
]

# Статус бота (меняется командами из чата поддержки)
bot_active = True
# Время последнего "бот старт" — сообщения старше этого пропускаем (пока бот был выключен)
bot_started_at = None

# === КЛИЕНТЫ ===
# DeepSeek только для текста
deepseek_client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

# OpenAI для фото (GPT-4o-mini - дешевая и с vision)
openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.openai.com/v1",
)

# === GREEN API НАСТРОЙКИ ===
GREEN_BASE = f"https://api.green-api.com/waInstance{GREEN_INSTANCE}"
HEADERS = {"Content-Type": "application/json"}

# Создаем папки
os.makedirs("logs", exist_ok=True)
os.makedirs("temp_files", exist_ok=True)
os.makedirs("photos", exist_ok=True)

# === СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ===
# Хранит состояние пользователей: chat_id -> {state, problem_text, sender_number, timestamp}
user_states = {}

# === ПОЛНЫЙ СПИСОК ИНСТРУКЦИЙ ===
INSTRUCTIONS = {
    "-1": {
        "инструкция": "Проверить интернет, если интернет есть то далее возле значка интернете есть стрелка вверх(крыша), откройте ее и найдете модуль печати(синий мячик), зажмите его и нажмите выйти, далее через экран двойным нажатием перезапустите тот же синий мячик",
        "фото": "photos/модульпечати.jpg"
    },
    "нет связи": {
        "инструкция": "Проверить интернет, если интернет есть то далее возле значка интернете есть стрелка вверх(крыша), откройте ее и найдете модуль печати(синий мячик), зажмите его и нажмите выйти, далее через экран двойным нажатием перезапустите тот же синий мячик",
        "фото": "photos/модульпечати.jpg"
    },
    "весы": {
        "инструкция": "Проверить кабель интернета на весах и есть ли интернет в магазине, Весы Масса К: 'url' Весы Ронгта: 'url'",
        "requires_choice": True
    },
    "115": {
        "инструкция": "Зажмите и выйдите с модуля печати. Далее зайдите в модуль печати через рабочий стол и обновите его. Модуль печати выглядит так",
        "фото": "photos/модульпечати.jpg"
    },
    "команда не поддерживается в данном режиме": {
        "инструкция": "Зажмите и выйдите с модуля печати. Далее зайдите в модуль печати через рабочий стол и обновите его. Модуль печати выглядит так",
        "фото": "photos/модульпечати.jpg"
    },
    "ошибка при печати на фр: смена на фр кончилась! 24 часа с момента первой продажи истекли! необходимо снять отчет с гашением или закрыть смену!": {
        "инструкция": "Закройте смену",
    },
    "69": {
        "инструкция": "Проверьте не повисла ли где то одна тенге и проверьте нет ли акционных товаров",
    },
    "Сумма всех меньше итога": {
        "инструкция": "Проверьте не повисла ли где то одна тенге и проверьте нет ли акционных товаров",
    },
    "не прогружаются весы, прогрузить весы, прогрузка весов": {
        "инструкция": "Весы Масса К: 'url' Весы Ронгта: 'url'",
    },
    "не работает интернет": {
        "инструкция": "Перезагрузите роутер",
    },
    "34": {
        "инструкция": "Неверная дата",
    },
    "неверная дата": {
        "инструкция": "Неверная дата",
    },
    "печать отключена": {
        "инструкция": "Зажать кнопку карандаша, и нажать кнопку над карандашом выбрать весовой товар и нажать снова ту же кнопку над карандашом и выйти из меню",
    },
    "терминал каспи": {
        "инструкция": "Проверьте наличие интернета, подключен ли терминал каспи к вайфаю",
    },
    "терминал джусан": {
        "инструкция": "Проверьте наличие интернета, подключен ли терминал джусан к вайфаю",
    },
    "чек": {
        "инструкция": "Уточните проблему или скиньте фотографияю. Будет лучше если и то и то.",
    },
    "Kaspi": {
        "инструкция": "Проверьте наличие интернета, подключен ли терминал каспи к вайфаю",
    },
    "Halyk": {
        "инструкция": "Проверьте наличие интернета, подключен ли терминал каспи к вайфаю",
    },
    "не удалось выгрузить товары в весы": {
        "инструкция": "Весы Масса К: 'url' Весы Ронгта: 'url'",
    },
    "ошибка печати полного чека: Field 'note' not found": {
        "инструкция": "Обновить модуль печати",
        "фото": "photos/модульпечати.jpg"
    },
    "модуль печати": {
        "инструкция": "Найти синий значок модуля печати на рабочем столе, зажать на нем, выбрать 'Выйти', затем двойным нажатием запустить модуль печати снова",
        "фото": "photos/модульпечати.jpg"
    }
}


# === ЛОГИРОВАНИЕ ===
def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)

    log_file = f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except:
        pass


# === GREEN API ФУНКЦИИ (АСИНХРОННЫЕ) ===
async def send_message(session: aiohttp.ClientSession, chat_id, text):
    """Отправка текстового сообщения в WhatsApp."""
    try:
        url_send = f"{GREEN_BASE}/sendMessage/{GREEN_TOKEN}"
        payload = {"chatId": chat_id, "message": text}

        async with session.post(
            url_send,
            json=payload,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 200:
                log(f"📤 -> {chat_id[:15]}: {text[:50]}...")
                return True
            else:
                body = (await response.text())[:200]
                log(f"✗ Ошибка отправки: {response.status} - {body}", "ERROR")
                return False
    except Exception as e:
        log(f"✗ Ошибка send_message: {e}", "ERROR")
        return False


async def send_buttons(session: aiohttp.ClientSession, chat_id, text, buttons):
    """Отправка сообщения с кнопками (исправленный метод, async)."""
    try:
        # В Green API правильный формат для кнопок
        url_send_buttons = f"{GREEN_BASE}/sendButtons/{GREEN_TOKEN}"

        payload = {
            "chatId": chat_id,
            "message": text,
            "buttons": buttons,
        }

        async with session.post(
            url_send_buttons,
            json=payload,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status == 200:
                log(f"✅ Кнопки отправлены в {chat_id[:15]}")
                return True
            else:
                body = (await response.text())[:200]
                log(f"✗ Ошибка отправки кнопок: {response.status} - {body}", "ERROR")
                return False
    except Exception as e:
        log(f"✗ Ошибка send_buttons: {e}", "ERROR")
        return False


async def send_file(session: aiohttp.ClientSession, chat_id, file_path, caption=""):
    """Отправка файла в чат."""
    try:
        if not os.path.exists(file_path):
            log(f"✗ Файл не найден: {file_path}", "ERROR")
            return False

        url_upload = f"{GREEN_BASE}/sendFileByUpload/{GREEN_TOKEN}"

        # Небольшой синхронный диск-I/O допустим
        with open(file_path, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("file", f, filename=os.path.basename(file_path))
            form.add_field("chatId", chat_id)
            form.add_field("caption", caption)

            async with session.post(
                url_upload,
                data=form,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                success = response.status == 200
                if success:
                    log(f"📎 Файл отправлен: {os.path.basename(file_path)}")
                else:
                    body = (await response.text())[:200]
                    log(f"✗ Ошибка файла: {response.status} - {body}", "ERROR")
                return success
    except Exception as e:
        log(f"✗ Ошибка send_file: {e}", "ERROR")
        return False


async def receive_notification(session: aiohttp.ClientSession):
    """Получение одного уведомления Green API."""
    try:
        url_receive = f"{GREEN_BASE}/receiveNotification/{GREEN_TOKEN}"
        async with session.get(
            url_receive,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=25),
        ) as response:
            response_text = (await response.text()).strip()

        # Проверяем, что это не пустой ответ или "null"
        if not response_text or response_text.lower() == "null":
            return None

        try:
            # Пробуем распарсить JSON
            data = json.loads(response_text)
            return data
        except json.JSONDecodeError as e:
            log(f"✗ Ошибка парсинга JSON: {e}. Ответ: '{response_text[:100]}'", "ERROR")
            return None

    except asyncio.TimeoutError:
        log("⚠️ Таймаут при получении уведомления", "WARNING")
        return None
    except Exception as e:
        log(f"✗ Ошибка получения уведомления: {e}", "ERROR")
        return None


async def delete_notification(session: aiohttp.ClientSession, receipt_id):
    """Удаление уведомления в Green API."""
    try:
        url_delete = f"{GREEN_BASE}/deleteNotification/{GREEN_TOKEN}/{receipt_id}"
        async with session.delete(
            url_delete,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response:
            if response.status != 200:
                log(f"⚠️ Ошибка удаления уведомления {receipt_id}: {response.status}", "WARNING")

        return True
    except Exception as e:
        log(f"✗ Ошибка delete_notification: {e}", "ERROR")
        return False


async def download_file_to_temp(session: aiohttp.ClientSession, url, filename=None):
    """Скачивает файл во временную папку (async)."""
    try:
        if not url or not isinstance(url, str) or not url.startswith("http"):
            log(f"✗ Неверный URL: '{url}'", "ERROR")
            return None

        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                log(f"✗ Ошибка HTTP: {response.status}", "ERROR")
                return None

            if not filename:
                filename = f"temp_{int(time.time())}.jpg"

            temp_path = os.path.join("temp_files", filename)

            with open(temp_path, "wb") as f:
                async for chunk in response.content.iter_chunked(1024 * 8):
                    if chunk:
                        f.write(chunk)

        log(f"📥 Файл сохранен: {temp_path}")
        return temp_path
    except Exception as e:
        log(f"✗ Ошибка скачивания: {e}", "ERROR")
        return None


# === ПОИСК ПО КЛЮЧАМ (ПЕРВЫЙ ЭТАП ДЛЯ ТЕКСТА) ===
def find_by_keywords(text):
    """Поиск инструкции по ключевым словам в тексте"""
    if not text:
        return None

    text_lower = text.lower().strip()

    # 1. Прямое совпадение с ключом
    if text_lower in INSTRUCTIONS:
        log(f"🔑 Точное совпадение с ключом: '{text_lower}'")
        return INSTRUCTIONS[text_lower]

    # 2. Проверка по номерам проблем
    if text_lower in ["-1", "115", "69", "34"]:
        log(f"🔑 Найдено по номеру проблемы: '{text_lower}'")
        return INSTRUCTIONS.get(text_lower)

    # 3. Поиск по частичному совпадению в ключах
    for key in INSTRUCTIONS:
        if key.lower() in text_lower and len(key) > 3:  # Исключаем короткие совпадения
            log(f"🔑 Частичное совпадение: '{key}' в тексте")
            return INSTRUCTIONS[key]

    # 4. Поиск по ключевым словам
    keyword_mapping = {
        "нет связи": ["интернет", "сеть", "подключение", "связ"],
        "весы": ["вес", "весов", "масса", "ронгта"],
        "115": ["команда не поддерживается", "модуль", "печати"],
        "смена кончилась": ["смена", "отчет", "гашение", "24 часа"],
        "69": ["сумма", "итог", "расчет", "акци"],
        "не работает интернет": ["интернет", "роутер", "вайфай", "сеть"],
        "печать отключена": ["печать", "принтер", "чек", "печатает"],
        "терминал": ["терминал", "каспи", "джусан", "halyk", "оплата"],
        "чек": ["чек", "чек-принтер", "бумага", "печать"],
        "модуль печати": ["модуль", "синий", "мячик", "иконка"]
    }

    for instruction_key, keywords in keyword_mapping.items():
        if instruction_key in INSTRUCTIONS:
            for keyword in keywords:
                if keyword in text_lower:
                    log(f"🔑 Найдено по ключевому слову '{keyword}': '{instruction_key}'")
                    return INSTRUCTIONS[instruction_key]

    return None


def extract_text_easyocr(image_path: str):
    """
    Локальный OCR через EasyOCR.
    Используется перед GPT-4o-mini, чтобы сэкономить токены.
    """
    try:
        import easyocr
    except Exception as e:
        # EasyOCR не установлен или не работает – просто пропускаем
        log(f"⚠️ EasyOCR недоступен: {e}", "WARNING")
        return None

    try:
        reader = easyocr.Reader(['ru', 'en'])
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
    """
    Вызов OpenAI с ретраями и таймаутами.
    Ожидается, что вызывается только для GPT-4o-mini.
    """
    last_error = None
    for attempt in range(OPENAI_MAX_RETRIES + 1):
        try:
            return await asyncio.wait_for(
                openai_client.chat.completions.create(**kwargs),
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


async def analyze_photo_with_gpt4omini(image_path):
    """
    Анализирует фото с помощью комбинации EasyOCR + GPT-4o-mini.

    Логика:
    1) Пытаемся распознать текст на фото через EasyOCR.
       - Если текст есть и в нем найдены ключевые слова → сразу возвращаем инструкцию.
    2) Если EasyOCR не нашел ключевые слова → отправляем изображение в GPT-4o-mini.
       - GPT-4o-mini возвращает ТОЛЬКО текст с изображения.
       - Проверяем этот текст через find_by_keywords.
       - Если ключевых слов нет → НИЧЕГО не отправляем в группу (возвращаем None).
    """
    try:
        # 1. OCR через EasyOCR (бесплатно)
        ocr_text = await asyncio.to_thread(extract_text_easyocr, image_path)
        if ocr_text:
            instruction_from_ocr = find_by_keywords(ocr_text)
            if instruction_from_ocr:
                log("✅ Инструкция найдена по тексту EasyOCR")
                return instruction_from_ocr

        # 2. Fallback: GPT-4o-mini как vision/OCR
        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
        except Exception as e:
            log(f"✗ Ошибка чтения файла изображения: {e}", "ERROR")
            return None

        # Безопасное кодирование в base64 (ограничиваем размер файла до разумного)
        if len(image_bytes) > 8 * 1024 * 1024:
            log("⚠️ Изображение слишком большое, обрезаем до 8 МБ перед отправкой в OpenAI", "WARNING")
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
                    {
                        "type": "text",
                        "text": "Распознай текст ошибки и сообщения с этого изображения. Верни только текст.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "low",
                        },
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

        # Проверяем текст на наличие ключевых слов
        instruction_from_gpt = find_by_keywords(gpt_text)
        if instruction_from_gpt:
            log("✅ Инструкция найдена по тексту GPT-4o-mini")
            return instruction_from_gpt

        # Ключевых слов нет — ничего не отправляем в группу
        log("ℹ️ GPT-4o-mini вернул текст без ключевых слов, инструкцию не отправляем", "INFO")
        return None

    except Exception as e:
        log(f"✗ Ошибка GPT-4o-mini анализ фото: {e}", "ERROR")
        return None


# === DEEPSEEK АНАЛИЗ ТЕКСТА ===
async def analyze_text_with_deepseek(text):
    """Анализирует текст с помощью DeepSeek (дешевый и хорош для текста)"""
    try:
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
                "content": (
                    "Проблема: "
                    f"{text}\n\n"
                    "Список допустимых ключей:\n"
                    "- 'нет связи'\n"
                    "- 'весы'\n"
                    "- '115'\n"
                    "- 'команда не поддерживается в данном режиме'\n"
                    "- 'ошибка при печати на фр: смена на фр кончилась! 24 часа с момента первой продажи истекли! необходимо снять отчет с гашением или закрыть смену!'\n"
                    "- '69'\n"
                    "- 'Сумма всех меньше итога'\n"
                    "- 'не прогружаются весы, прогрузить весы, прогрузка весов'\n"
                    "- 'не работает интернет'\n"
                    "- '34'\n"
                    "- 'неверная дата'\n"
                    "- 'печать отключена'\n"
                    "- 'терминал каспи'\n"
                    "- 'терминал джусан'\n"
                    "- 'чек'\n"
                    "- 'Kaspi'\n"
                    "- 'Halyk'\n"
                    "- 'не удалось выгрузить товары в весы'\n"
                    "- 'ошибка печати полного чека: Field 'note' not found'\n"
                    "- 'модуль печати'\n"
                ),
            },
        ]

        last_error = None
        response = None

        for attempt in range(DEEPSEEK_MAX_RETRIES + 1):
            try:
                response = await asyncio.wait_for(
                    deepseek_client.chat.completions.create(
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
                log(f"⚠️ Ошибка DeepSeek анализ текста (попытка {attempt + 1}/{DEEPSEEK_MAX_RETRIES + 1}): {e}", "ERROR")
                if attempt < DEEPSEEK_MAX_RETRIES:
                    await asyncio.sleep(DEEPSEEK_RETRY_DELAY * (attempt + 1))

        if not response or not response.choices:
            log(f"✗ Не удалось получить ответ DeepSeek: {last_error}", "ERROR")
            return None

        result = (response.choices[0].message.content or "").strip().lower()
        log(f"🤖 DeepSeek анализ текста: '{result}'")

        if result in INSTRUCTIONS:
            return INSTRUCTIONS[result]
        elif result == "не найдено":
            return None
        else:
            # Пробуем найти похожий ключ
            for key in INSTRUCTIONS:
                if key in result:
                    return INSTRUCTIONS[key]
            return None

    except Exception as e:
        log(f"✗ Ошибка DeepSeek анализ текста: {e}", "ERROR")
        return None


# === ОТПРАВКА ИНСТРУКЦИИ ===
async def send_instruction_only(session: aiohttp.ClientSession, chat_id, instruction_data):
    """Отправляет ТОЛЬКО инструкцию, без дополнительных сообщений"""
    if not instruction_data or "инструкция" not in instruction_data:
        return False

    # Отправляем инструкцию
    success = await send_message(session, chat_id, instruction_data["инструкция"])

    # Отправляем фото если есть
    if success and "фото" in instruction_data:
        photo_path = instruction_data["фото"]
        if os.path.exists(photo_path):
            await send_file(session, chat_id, photo_path)

    return success


async def ask_problem_solved(session: aiohttp.ClientSession, chat_id, sender_number):
    """Спрашивает, решилась ли проблема (с кнопками)"""
    message = (
        f"👤 Пользователь: {sender_number}\n\n"
        f"🔍 Проверьте на наличие интернета.\n"
        f"Решилась ли проблема?\n\n"
        f"Нажмите соответствующую кнопку:"
    )

    # Правильный формат кнопок для Green API
    buttons = [
        {
            "buttonId": "btn_solved",
            "buttonText": "✅ Да, решилась"
        },
        {
            "buttonId": "btn_not_solved",
            "buttonText": "❌ Нет, не решилась"
        }
    ]

    # Сохраняем/обновляем состояние ожидания ответа, не затирая уже сохраненные поля
    state = user_states.get(chat_id, {})
    state.update(
        {
            "state": "awaiting_problem_check",
            "sender_number": sender_number,
            "timestamp": time.time(),
        }
    )
    user_states[chat_id] = state

    # Отправляем кнопки
    return await send_buttons(session, chat_id, message, buttons)


async def handle_button_response(session: aiohttp.ClientSession, chat_id, button_text, sender_number):
    """Обрабатывает ответ на кнопки"""
    if chat_id not in user_states:
        return False

    state_data = user_states[chat_id]

    if state_data["state"] == "awaiting_problem_check":
        original_sender = state_data["sender_number"]
        original_problem = state_data.get("original_problem")
        image_path = state_data.get("image_path")

        # Принимаем: "1", "да", "✅ Да, решилась" и т.п.
        if (button_text.strip() == "1" or "да" in button_text.lower() or "✅" in button_text):
            # Пользователь подтвердил, что проблема решена
            log(f"✅ Пользователь {sender_number} подтвердил решение проблемы для {original_sender}")
            await send_message(session, chat_id, f"✅ Отлично! Проблема пользователя {original_sender} решена.")

            # Удаляем состояние ожидания
            del user_states[chat_id]

            # Удаляем временный файл, если был
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass
            return True

        # Принимаем: "2", "нет", "❌ Нет, не решилась" и т.п.
        elif (button_text.strip() == "2" or "нет" in button_text.lower() or "❌" in button_text):
            # Проблема не решена, нужно обработать
            log(f"⚠️ Пользователь {sender_number} сообщил, что проблема НЕ решена для {original_sender}")

            if original_problem:
                # Если есть сохраненная проблема, обрабатываем ее
                await send_message(session, chat_id, "🔍 Проблема не решена. Ищу решение...")

                # Удаляем состояние ожидания
                del user_states[chat_id]

                # Обрабатываем проблему, передаем image_path если есть
                await process_problem(session, chat_id, original_problem, original_sender, image_path=image_path)
                return True
            else:
                await send_message(session, chat_id, "⚠️ Информация о проблеме не найдена.")
                del user_states[chat_id]
                return True

    return False


# === ОБРАБОТКА ПРОБЛЕМЫ (если не решена) ===
async def process_problem(session: aiohttp.ClientSession, chat_id, problem_text, sender_number, image_path=None):
    """Обрабатывает проблему если она не решена (async)"""
    log(f"🔍 Обработка проблемы от {sender_number}: {problem_text[:50]}...")

    instruction_found = None

    if image_path and os.path.exists(image_path):
        # Для фото: EasyOCR -> GPT-4o-mini
        instruction_found = await analyze_photo_with_gpt4omini(image_path)

        # Удаляем временный файл
        try:
            os.remove(image_path)
        except Exception:
            pass
    else:
        # Для текста: сначала ключи, потом DeepSeek
        instruction_found = find_by_keywords(problem_text)

        if not instruction_found:
            instruction_found = await analyze_text_with_deepseek(problem_text)

    # Отправляем инструкцию если нашли
    if instruction_found:
        log(f"✅ Найдена инструкция для {sender_number}")
        await send_instruction_only(session, chat_id, instruction_found)
    else:
        log(f"❌ Инструкция не найдена для {sender_number}")
        # В рабочий чат ничего не отправляем, только в чат поддержки
        try:
            fallback_text = (
                "⚠️ Инструкция по проблеме не найдена автоматически.\n\n"
                f"Отправитель: {sender_number}\n"
                f"Проблема: {problem_text[:300]}"
            )
            await send_message(session, SUPPORT_CHAT_ID, fallback_text)
        except Exception as e:
            log(f"✗ Ошибка при пересылке в поддержку: {e}", "ERROR")


# === ОБРАБОТКА СООБЩЕНИЙ ===
async def handle_message(session: aiohttp.ClientSession, chat_id, message_type, message_data, sender_number):
    """Обрабатывает входящие сообщения"""
    # Проверяем номер отправителя (техподдержке не отвечаем)
    if sender_number in TECH_SUPPORT_NUMBERS:
        log(f"👨‍💼 Игнорируем техподдержку: {sender_number}")
        return True

    # Проверяем активность бота
    if not bot_active:
        log(f"📭 Бот выключен, игнорируем: {sender_number}")
        return True

    # Проверяем, ожидаем ли мы ответ на кнопки
    if chat_id in user_states and message_type == "textMessage":
        text = message_data.get("textMessageData", {}).get("textMessage", "")
        handled = await handle_button_response(session, chat_id, text, sender_number)
        if handled:
            return True

    # Проверяем, не устарело ли состояние
    if chat_id in user_states:
        state_time = user_states[chat_id].get("timestamp", 0)
        if time.time() - state_time > 300:  # 5 минут таймаут
            log(f"🕐 Таймаут состояния для {chat_id}")
            del user_states[chat_id]

    # Обрабатываем новые сообщения
    if message_type == "textMessage":
        text = message_data.get("textMessageData", {}).get("textMessage", "")
        log(f"📝 Текст от {sender_number}: {text[:100]}...")

        # Всегда сохраняем проблему в состояние, затем спрашиваем «решено?» (1/2 или кнопки)
        state = user_states.get(chat_id, {})
        state.update({
            "state": "awaiting_problem_check",
            "original_problem": text,
            "sender_number": sender_number,
            "timestamp": time.time(),
        })
        user_states[chat_id] = state
        await ask_problem_solved(session, chat_id, sender_number)

    elif message_type == "imageMessage":
        file_data = message_data.get("fileMessageData", {})

        if not file_data:
            log(f"✗ Нет fileMessageData в сообщении от {sender_number}", "ERROR")
            return False

        # Извлекаем данные
        download_url = file_data.get("downloadUrl")
        caption = file_data.get("caption", "")

        log(f"📷 Фото от {sender_number}, описание: '{caption}'")

        if download_url and download_url.startswith('http'):
            log(f"📎 Скачиваем фото с URL: {download_url[:50]}...")
            image_path = await download_file_to_temp(session, download_url, f"image_{int(time.time())}.jpg")

            if image_path:
                # Сначала спрашиваем про решение проблемы
                combined_text = f"{caption} [фото]" if caption else "[фото]"

                # Сохраняем проблему и путь к фото
                user_states[chat_id] = {
                    "state": "awaiting_problem_check",
                    "sender_number": sender_number,
                    "timestamp": time.time(),
                    "original_problem": combined_text,
                    "image_path": image_path
                }

                await ask_problem_solved(session, chat_id, sender_number)
            else:
                log(f"✗ Не удалось скачать фото")
                # Если есть описание - спрашиваем про решение
                if caption:
                    user_states[chat_id] = {
                        "state": "awaiting_problem_check",
                        "sender_number": sender_number,
                        "timestamp": time.time(),
                        "original_problem": caption
                    }
                    await ask_problem_solved(session, chat_id, sender_number)
        else:
            log(f"⚠️ Нет валидного downloadUrl для фото")
            # Если есть описание - спрашиваем про решение
            if caption:
                user_states[chat_id] = {
                    "state": "awaiting_problem_check",
                    "sender_number": sender_number,
                    "timestamp": time.time(),
                    "original_problem": caption
                }
                await ask_problem_solved(session, chat_id, sender_number)

    return True


def _get_message_text(message_data: dict) -> str:
    """Извлекает текст из messageData (текст или кнопка)."""
    if not message_data:
        return ""
    if message_data.get("typeMessage") == "textMessage":
        return (message_data.get("textMessageData") or {}).get("textMessage", "")
    if message_data.get("typeMessage") == "buttonsResponseMessage":
        return (message_data.get("buttonsResponseMessageData") or {}).get("selectedButtonText", "")
    return ""


async def handle_notification(session: aiohttp.ClientSession, notification: dict):
    """Обработка одного уведомления Green API (async)."""
    global bot_active, bot_started_at
    try:
        receipt_id = notification.get("receiptId")
        body = notification.get("body", {})

        if body.get("typeWebhook") != "incomingMessageReceived":
            if receipt_id:
                await delete_notification(session, receipt_id)
            return

        sender_data = body.get("senderData", {})
        chat_id = sender_data.get("chatId", "")
        sender_number = sender_data.get("sender", "")
        message_data = body.get("messageData", {})
        message_type = message_data.get("typeMessage")
        msg_text = _get_message_text(message_data).strip().lower()

        # Чат поддержки: только команды «бот стоп» / «бот старт» (работают всегда)
        if chat_id == SUPPORT_CHAT_ID:
            if msg_text == "бот стоп":
                bot_active = False
                log("⛔ Бот остановлен по команде из чата поддержки")
                await send_message(session, SUPPORT_CHAT_ID, "⛔ Бот остановлен. Вебхуки не обрабатываются.")
                if receipt_id:
                    await delete_notification(session, receipt_id)
                return
            if msg_text == "бот старт":
                bot_active = True
                bot_started_at = time.time()
                log("✅ Бот запущен по команде из чата поддержки. Старые сообщения будут пропущены.")
                await send_message(session, SUPPORT_CHAT_ID, "✅ Бот запущен. Сообщения, пришедшие пока бот был выключен, пропущены.")
                if receipt_id:
                    await delete_notification(session, receipt_id)
                return
            # Если чат поддержки тот же, что и рабочий (в ALLOWED_CHATS), дальше обработаем как обычное сообщение

        # Бот выключен — остальные чаты не обрабатываем, только удаляем уведомление
        if not bot_active:
            if receipt_id:
                await delete_notification(session, receipt_id)
            return

        # Пропускаем сообщения, пришедшие до «бот старт» (пока бот был выключен)
        if bot_started_at is not None:
            notif_time = body.get("timestamp") or 0
            if notif_time < bot_started_at:
                log(f"⏭️ Пропуск старого сообщения (timestamp {notif_time} < {bot_started_at})")
                if receipt_id:
                    await delete_notification(session, receipt_id)
                return
            # Через 60 сек снимаем ограничение, чтобы не проверять бесконечно
            if time.time() - bot_started_at > 60:
                bot_started_at = None

        # Обрабатываем только разрешённые чаты
        if chat_id not in ALLOWED_CHATS:
            if receipt_id:
                await delete_notification(session, receipt_id)
            return

        log(f"📨 Получено уведомление от {sender_number}, тип: {message_type}")

        await handle_message(session, chat_id, message_type, message_data, sender_number)

        if receipt_id:
            await delete_notification(session, receipt_id)
        await asyncio.sleep(0.3)

    except Exception as e:
        log(f"💥 Критическая ошибка при обработке уведомления: {e}", "ERROR")


# === ГЛАВНЫЙ ЦИКЛ (ASYNC) ===
async def main():
    log("=" * 70)
    log("🤖 Бот запущен с СИСТЕМОЙ КНОПОК (новая логика, async)!")
    log(f"🎯 Статус: {'ВКЛЮЧЕН ✅' if bot_active else 'ВЫКЛЮЧЕН ⛔'}")
    log(f"📚 Инструкций в базе: {len(INSTRUCTIONS)}")
    log(f"👂 Чатов: {len(ALLOWED_CHATS)}")
    log(f"👨‍💼 Игнорируемых номеров: {len(TECH_SUPPORT_NUMBERS)}")
    log("⚡ Логика: Проблема -> Кнопки (1/2 или Да/Нет) -> Если нет -> Решение")
    log("🔍 ТЕКСТ: Ключи -> DeepSeek (без истории сообщений)")
    log("🖼️ ФОТО: EasyOCR -> GPT-4o-mini (Vision, только при необходимости)")
    log(f"📋 Чат поддержки (стоп/старт): {SUPPORT_CHAT_ID}")
    log("   Команды: «бот стоп» — остановить, «бот старт» — запустить (старые сообщения пропустятся)")
    log("=" * 70)

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            try:
                notification = await receive_notification(session)
                if not notification:
                    await asyncio.sleep(1)
                    continue

                # Обрабатываем каждое уведомление в отдельной задаче, чтобы не блокировать получение новых
                asyncio.create_task(handle_notification(session, notification))
                await asyncio.sleep(0.1)

            except KeyboardInterrupt:
                log("🛑 Бот остановлен")
                break
            except Exception as e:
                log(f"💥 Критическая ошибка в главном цикле: {e}", "ERROR")
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())