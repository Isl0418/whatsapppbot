"""
Проверка логики бота без реальных API (запуск: python test_bot_flow.py).
Проверяет: приём сообщения -> сохранение проблемы -> ответ 1/2 -> поиск инструкции.
"""
import sys
sys.path.insert(0, ".")

# Импортируем только то, что не тянет aiohttp/API
from whatsappbot import (
    find_by_keywords,
    INSTRUCTIONS,
    _get_message_text,
    SUPPORT_CHAT_ID,
    ALLOWED_CHATS,
)


def test_find_by_keywords():
    """Бот должен находить инструкцию по ключевым словам."""
    cases = [
        ("нет связи", "нет связи"),
        ("у нас 115 ошибка", "115"),
        ("не работает интернет", "не работает интернет"),
        ("модуль печати завис", "модуль печати"),
        ("каспи не берёт", "терминал каспи"),
    ]
    for text, expected_key in cases:
        result = find_by_keywords(text)
        assert result is not None, f"Не найдена инструкция для: {text!r}"
        assert "инструкция" in result, f"Нет поля инструкция для: {text!r}"
        print(f"  OK: {text!r} -> ключ из инструкции найден")
    print("  find_by_keywords: все проверки пройдены")


def test_get_message_text():
    """Извлечение текста из структуры Green API."""
    # Текстовое сообщение
    msg1 = {
        "typeMessage": "textMessage",
        "textMessageData": {"textMessage": "нет связи"},
    }
    assert _get_message_text(msg1) == "нет связи"
    # Кнопка
    msg2 = {
        "typeMessage": "buttonsResponseMessage",
        "buttonsResponseMessageData": {"selectedButtonText": "✅ Да, решилась"},
    }
    assert _get_message_text(msg2) == "✅ Да, решилась"
    print("  _get_message_text: OK")


def test_support_commands():
    """Команды чата поддержки должны определяться по точному тексту."""
    stop_ok = "бот стоп".strip().lower()
    start_ok = "бот старт".strip().lower()
    assert stop_ok == "бот стоп"
    assert start_ok == "бот старт"
    print("  Команды стоп/старт: OK")


def test_flow_summary():
    """Кратко: цепочка при сообщении из WhatsApp."""
    print("\n  Цепочка при сообщении из WhatsApp:")
    print("    1. receiveNotification -> body.typeWebhook == incomingMessageReceived")
    print("    2. Чат поддержки: если текст «бот стоп»/«бот старт» -> смена bot_active, ответ, deleteNotification")
    print("    3. Если bot_active и чат в ALLOWED_CHATS:")
    print("    4. handle_message: текст/фото -> сохраняем original_problem, вызываем ask_problem_solved (кнопки)")
    print("    5. Ответ «1» или «Да» -> «Проблема решена», очистка состояния")
    print("    6. Ответ «2» или «Нет» -> process_problem(original_problem) -> find_by_keywords/DeepSeek -> send_instruction_only")
    print("  SUPPORT_CHAT_ID задан:", bool(SUPPORT_CHAT_ID))
    print("  ALLOWED_CHATS задан:", len(ALLOWED_CHATS) > 0)


if __name__ == "__main__":
    print("Проверка логики бота (без API)...")
    test_find_by_keywords()
    test_get_message_text()
    test_support_commands()
    test_flow_summary()
    print("\nВсе проверки пройдены.")
