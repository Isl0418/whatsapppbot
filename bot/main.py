"""
Главный цикл бота: получение уведомлений Green API и запуск обработчиков.
"""
import asyncio
import aiohttp

from bot.config import ensure_dirs, ALLOWED_CHATS, SUPPORT_CHAT_ID, TECH_SUPPORT_NUMBERS
from bot.state import bot_active
from bot.logger import log
from bot.instructions import INSTRUCTIONS
from bot.green_api import receive_notification
from bot.handlers import handle_notification


async def main() -> None:
    ensure_dirs()
    log("=" * 70)
    log("🤖 Бот запущен (архитектура: bot/)")
    log(f"🎯 Статус: {'ВКЛЮЧЕН ✅' if bot_active else 'ВЫКЛЮЧЕН ⛔'}")
    log(f"📚 Инструкций в базе: {len(INSTRUCTIONS)}")
    log(f"👂 Чатов: {len(ALLOWED_CHATS)}")
    log(f"👨‍💼 Игнорируемых номеров: {len(TECH_SUPPORT_NUMBERS)}")
    log("⚡ Логика: Проблема -> Кнопки (1/2 или Да/Нет) -> Если нет -> Решение")
    log("🔍 ТЕКСТ: Ключи -> DeepSeek")
    log("🖼️ ФОТО: EasyOCR -> GPT-4o-mini")
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
                asyncio.create_task(handle_notification(session, notification))
                await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                log("🛑 Бот остановлен")
                break
            except Exception as e:
                log(f"💥 Критическая ошибка в главном цикле: {e}", "ERROR")
                await asyncio.sleep(3)
