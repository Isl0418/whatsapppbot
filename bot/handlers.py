"""
Обработка входящих уведомлений и сообщений: чат поддержки, кнопки, текст/фото, решение проблемы.
"""
import asyncio
import os
import time
import aiohttp

from bot.config import (
    ALLOWED_CHATS,
    SUPPORT_CHAT_ID,
    TECH_SUPPORT_NUMBERS,
    PROJECT_ROOT,
)
from bot import state as state_module
from bot.state import user_states
from bot.logger import log
from bot.instructions import find_by_keywords
from bot.green_api import (
    send_message,
    send_buttons,
    send_file,
    download_file_to_temp,
    delete_notification,
)
from bot.ai.vision import analyze_photo_with_gpt4omini
from bot.ai.deepseek import analyze_text_with_deepseek


def get_message_text(message_data: dict) -> str:
    """Извлекает текст из messageData (текст или ответ на кнопку)."""
    if not message_data:
        return ""
    if message_data.get("typeMessage") == "textMessage":
        return (message_data.get("textMessageData") or {}).get("textMessage", "")
    if message_data.get("typeMessage") == "buttonsResponseMessage":
        return (message_data.get("buttonsResponseMessageData") or {}).get("selectedButtonText", "")
    return ""


async def send_instruction_only(
    session: aiohttp.ClientSession, chat_id: str, instruction_data: dict
) -> bool:
    """Отправляет только инструкцию и при необходимости фото."""
    if not instruction_data or "инструкция" not in instruction_data:
        return False
    success = await send_message(session, chat_id, instruction_data["инструкция"])
    if success and "фото" in instruction_data:
        photo_rel = instruction_data["фото"]
        photo_path = PROJECT_ROOT / photo_rel if not os.path.isabs(photo_rel) else photo_rel
        if photo_path.exists():
            await send_file(session, chat_id, str(photo_path))
    return success


async def ask_problem_solved(
    session: aiohttp.ClientSession, chat_id: str, sender_number: str
) -> bool:
    """Спрашивает «решено?» с кнопками (и ответами 1/2)."""
    message = (
        f"👤 Пользователь: {sender_number}\n\n"
        "🔍 Проверьте на наличие интернета.\n"
        "Решилась ли проблема?\n\n"
        "Нажмите соответствующую кнопку (или напишите 1 — да, 2 — нет):"
    )
    buttons = [
        {"buttonId": "btn_solved", "buttonText": "✅ Да, решилась"},
        {"buttonId": "btn_not_solved", "buttonText": "❌ Нет, не решилась"},
    ]
    state = user_states.get(chat_id, {})
    state.update({
        "state": "awaiting_problem_check",
        "sender_number": sender_number,
        "timestamp": time.time(),
    })
    user_states[chat_id] = state
    return await send_buttons(session, chat_id, message, buttons)


async def handle_button_response(
    session: aiohttp.ClientSession,
    chat_id: str,
    button_text: str,
    sender_number: str,
) -> bool:
    """Обрабатывает ответ на кнопки (1/да или 2/нет)."""
    if chat_id not in user_states:
        return False
    state_data = user_states[chat_id]
    if state_data.get("state") != "awaiting_problem_check":
        return False

    original_sender = state_data["sender_number"]
    original_problem = state_data.get("original_problem")
    image_path = state_data.get("image_path")

    if button_text.strip() == "1" or "да" in button_text.lower() or "✅" in button_text:
        log(f"✅ Пользователь {sender_number} подтвердил решение проблемы для {original_sender}")
        await send_message(session, chat_id, f"✅ Отлично! Проблема пользователя {original_sender} решена.")
        del user_states[chat_id]
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError:
                pass
        return True

    if button_text.strip() == "2" or "нет" in button_text.lower() or "❌" in button_text:
        log(f"⚠️ Пользователь {sender_number} сообщил, что проблема НЕ решена для {original_sender}")
        if original_problem:
            await send_message(session, chat_id, "🔍 Проблема не решена. Ищу решение...")
            del user_states[chat_id]
            await process_problem(
                session, chat_id, original_problem, original_sender, image_path=image_path
            )
        else:
            await send_message(session, chat_id, "⚠️ Информация о проблеме не найдена.")
            del user_states[chat_id]
        return True
    return False


async def process_problem(
    session: aiohttp.ClientSession,
    chat_id: str,
    problem_text: str,
    sender_number: str,
    image_path: str | None = None,
) -> None:
    """Ищет инструкцию по проблеме (текст или фото) и отправляет в чат или в поддержку."""
    log(f"🔍 Обработка проблемы от {sender_number}: {problem_text[:50]}...")
    instruction_found = None

    if image_path and os.path.exists(image_path):
        instruction_found = await analyze_photo_with_gpt4omini(image_path)
        try:
            os.remove(image_path)
        except OSError:
            pass
    else:
        instruction_found = find_by_keywords(problem_text)
        if not instruction_found:
            instruction_found = await analyze_text_with_deepseek(problem_text)

    if instruction_found:
        log(f"✅ Найдена инструкция для {sender_number}")
        await send_instruction_only(session, chat_id, instruction_found)
    else:
        log(f"❌ Инструкция не найдена для {sender_number}")
        try:
            fallback_text = (
                "⚠️ Инструкция по проблеме не найдена автоматически.\n\n"
                f"Отправитель: {sender_number}\n"
                f"Проблема: {problem_text[:300]}"
            )
            await send_message(session, SUPPORT_CHAT_ID, fallback_text)
        except Exception as e:
            log(f"✗ Ошибка при пересылке в поддержку: {e}", "ERROR")


async def handle_message(
    session: aiohttp.ClientSession,
    chat_id: str,
    message_type: str,
    message_data: dict,
    sender_number: str,
) -> bool:
    """Обрабатывает одно входящее сообщение (текст или фото)."""
    if sender_number in TECH_SUPPORT_NUMBERS:
        log(f"👨‍💼 Игнорируем техподдержку: {sender_number}")
        return True
    if not state_module.bot_active:
        log(f"📭 Бот выключен, игнорируем: {sender_number}")
        return True

    if chat_id in user_states and message_type == "textMessage":
        text = get_message_text(message_data)
        if await handle_button_response(session, chat_id, text, sender_number):
            return True

    if chat_id in user_states:
        state_time = user_states[chat_id].get("timestamp", 0)
        if time.time() - state_time > 300:
            log(f"🕐 Таймаут состояния для {chat_id}")
            del user_states[chat_id]

    if message_type == "textMessage":
        text = get_message_text(message_data)
        log(f"📝 Текст от {sender_number}: {text[:100]}...")
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
        download_url = file_data.get("downloadUrl")
        caption = file_data.get("caption", "")
        log(f"📷 Фото от {sender_number}, описание: '{caption}'")

        if download_url and str(download_url).startswith("http"):
            image_path = await download_file_to_temp(
                session, download_url, f"image_{int(time.time())}.jpg"
            )
            if image_path:
                combined_text = f"{caption} [фото]" if caption else "[фото]"
                user_states[chat_id] = {
                    "state": "awaiting_problem_check",
                    "sender_number": sender_number,
                    "timestamp": time.time(),
                    "original_problem": combined_text,
                    "image_path": image_path,
                }
                await ask_problem_solved(session, chat_id, sender_number)
            elif caption:
                user_states[chat_id] = {
                    "state": "awaiting_problem_check",
                    "sender_number": sender_number,
                    "timestamp": time.time(),
                    "original_problem": caption,
                }
                await ask_problem_solved(session, chat_id, sender_number)
        elif caption:
            user_states[chat_id] = {
                "state": "awaiting_problem_check",
                "sender_number": sender_number,
                "timestamp": time.time(),
                "original_problem": caption,
            }
            await ask_problem_solved(session, chat_id, sender_number)
    return True


async def handle_notification(
    session: aiohttp.ClientSession, notification: dict
) -> None:
    """Обрабатывает одно уведомление Green API: команды поддержки, фильтр по времени, обработка сообщения."""
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
    msg_text = get_message_text(message_data).strip().lower()

    # Чат поддержки: команды «бот стоп» / «бот старт»
    if chat_id == SUPPORT_CHAT_ID:
        if msg_text == "бот стоп":
            state_module.bot_active = False
            log("⛔ Бот остановлен по команде из чата поддержки")
            await send_message(session, SUPPORT_CHAT_ID, "⛔ Бот остановлен. Вебхуки не обрабатываются.")
            if receipt_id:
                await delete_notification(session, receipt_id)
            return
        if msg_text == "бот старт":
            state_module.bot_active = True
            state_module.bot_started_at = time.time()
            log("✅ Бот запущен по команде из чата поддержки. Старые сообщения будут пропущены.")
            await send_message(
                session, SUPPORT_CHAT_ID,
                "✅ Бот запущен. Сообщения, пришедшие пока бот был выключен, пропущены."
            )
            if receipt_id:
                await delete_notification(session, receipt_id)
            return

    if not state_module.bot_active:
        if receipt_id:
            await delete_notification(session, receipt_id)
        return

    if state_module.bot_started_at is not None:
        notif_time = body.get("timestamp") or 0
        if notif_time < state_module.bot_started_at:
            log(f"⏭️ Пропуск старого сообщения (timestamp {notif_time} < {state_module.bot_started_at})")
            if receipt_id:
                await delete_notification(session, receipt_id)
            return
        if time.time() - state_module.bot_started_at > 60:
            state_module.bot_started_at = None

    if chat_id not in ALLOWED_CHATS:
        if receipt_id:
            await delete_notification(session, receipt_id)
        return

    log(f"📨 Получено уведомление от {sender_number}, тип: {message_type}")
    await handle_message(session, chat_id, message_type, message_data, sender_number)
    if receipt_id:
        await delete_notification(session, receipt_id)
    await asyncio.sleep(0.3)
