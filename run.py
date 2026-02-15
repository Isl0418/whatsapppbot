#!/usr/bin/env python3
"""
Точка входа: запуск WhatsApp-бота техподдержки.
Использование: python run.py
Либо: python -m bot.main
"""
import asyncio
from bot.main import main

if __name__ == "__main__":
    asyncio.run(main())
