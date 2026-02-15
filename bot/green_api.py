"""
Green API (WhatsApp): отправка и приём сообщений.
"""
import asyncio
import json
import os
import time
import aiohttp

from bot.config import GREEN_INSTANCE, GREEN_TOKEN, DIR_TEMP
from bot.logger import log

GREEN_BASE = f"https://api.green-api.com/waInstance{GREEN_INSTANCE}"
HEADERS = {"Content-Type": "application/json"}


async def send_message(session: aiohttp.ClientSession, chat_id: str, text: str) -> bool:
    """Отправка текстового сообщения в WhatsApp."""
    try:
        url_send = f"{GREEN_BASE}/sendMessage/{GREEN_TOKEN}"
        payload = {"chatId": chat_id, "message": text}
        async with session.post(
            url_send, json=payload, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 200:
                log(f"📤 -> {chat_id[:15]}: {text[:50]}...")
                return True
            body = (await response.text())[:200]
            log(f"✗ Ошибка отправки: {response.status} - {body}", "ERROR")
            return False
    except Exception as e:
        log(f"✗ Ошибка send_message: {e}", "ERROR")
        return False


async def send_buttons(
    session: aiohttp.ClientSession, chat_id: str, text: str, buttons: list
) -> bool:
    """Отправка сообщения с кнопками."""
    try:
        url_send_buttons = f"{GREEN_BASE}/sendButtons/{GREEN_TOKEN}"
        payload = {"chatId": chat_id, "message": text, "buttons": buttons}
        async with session.post(
            url_send_buttons, json=payload, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status == 200:
                log(f"✅ Кнопки отправлены в {chat_id[:15]}")
                return True
            body = (await response.text())[:200]
            log(f"✗ Ошибка отправки кнопок: {response.status} - {body}", "ERROR")
            return False
    except Exception as e:
        log(f"✗ Ошибка send_buttons: {e}", "ERROR")
        return False


async def send_file(
    session: aiohttp.ClientSession, chat_id: str, file_path: str | os.PathLike, caption: str = ""
) -> bool:
    """Отправка файла в чат. file_path — абсолютный или относительный путь."""
    try:
        path = os.path.abspath(file_path)
        if not os.path.exists(path):
            log(f"✗ Файл не найден: {path}", "ERROR")
            return False
        url_upload = f"{GREEN_BASE}/sendFileByUpload/{GREEN_TOKEN}"
        with open(path, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("file", f, filename=os.path.basename(path))
            form.add_field("chatId", chat_id)
            form.add_field("caption", caption)
            async with session.post(
                url_upload, data=form, timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                success = response.status == 200
                if success:
                    log(f"📎 Файл отправлен: {os.path.basename(path)}")
                else:
                    body = (await response.text())[:200]
                    log(f"✗ Ошибка файла: {response.status} - {body}", "ERROR")
                return success
    except Exception as e:
        log(f"✗ Ошибка send_file: {e}", "ERROR")
        return False


async def receive_notification(session: aiohttp.ClientSession) -> dict | None:
    """Получение одного уведомления Green API."""
    try:
        url_receive = f"{GREEN_BASE}/receiveNotification/{GREEN_TOKEN}"
        async with session.get(
            url_receive, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=25),
        ) as response:
            response_text = (await response.text()).strip()
        if not response_text or response_text.lower() == "null":
            return None
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        log(f"✗ Ошибка парсинга JSON: {e}. Ответ: '{response_text[:100]}'", "ERROR")
        return None
    except asyncio.TimeoutError:
        log("⚠️ Таймаут при получении уведомления", "WARNING")
        return None
    except Exception as e:
        log(f"✗ Ошибка получения уведомления: {e}", "ERROR")
        return None


async def delete_notification(session: aiohttp.ClientSession, receipt_id) -> bool:
    """Удаление уведомления в Green API."""
    try:
        url_delete = f"{GREEN_BASE}/deleteNotification/{GREEN_TOKEN}/{receipt_id}"
        async with session.delete(url_delete, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status != 200:
                log(f"⚠️ Ошибка удаления уведомления {receipt_id}: {response.status}", "WARNING")
        return True
    except Exception as e:
        log(f"✗ Ошибка delete_notification: {e}", "ERROR")
        return False


async def download_file_to_temp(
    session: aiohttp.ClientSession, url: str, filename: str | None = None
) -> str | None:
    """Скачивает файл во временную папку. Возвращает путь к файлу или None."""
    try:
        if not url or not isinstance(url, str) or not url.startswith("http"):
            log(f"✗ Неверный URL: '{url}'", "ERROR")
            return None
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                log(f"✗ Ошибка HTTP: {response.status}", "ERROR")
                return None
            filename = filename or f"temp_{int(time.time())}.jpg"
            temp_path = DIR_TEMP / filename
            with open(temp_path, "wb") as f:
                async for chunk in response.content.iter_chunked(1024 * 8):
                    if chunk:
                        f.write(chunk)
        log(f"📥 Файл сохранен: {temp_path}")
        return str(temp_path)
    except Exception as e:
        log(f"✗ Ошибка скачивания: {e}", "ERROR")
        return None
