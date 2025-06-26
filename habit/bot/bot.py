#!/usr/bin/env python3
"""
Advanced Telegram bot for Habit Tracker with charts and language selection.
"""
import asyncio
import os
import sys
import io
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid
import gettext
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from telegram.error import BadRequest, TelegramError
from dotenv import load_dotenv
import aiosqlite

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
DB_PATH: str = os.getenv("DB_PATH", "habits.db")
DEFAULT_LANGUAGE: str = os.getenv("BOT_LANGUAGE", "ru")

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not found")
    print("❌ TELEGRAM_BOT_TOKEN not found in .env")
    sys.exit(1)

logger.info(f"Starting bot with token: {TELEGRAM_BOT_TOKEN[:10]}...")


async def init_db() -> None:
    """Initialize SQLite database."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS habits (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    frequency TEXT NOT NULL,
                    goal TEXT,
                    category TEXT,
                    created_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS completions (
                    id TEXT PRIMARY KEY,
                    habit_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (habit_id) REFERENCES habits(id)
                )
                """
            )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'ru'
            )
            """
        )
        await conn.commit()
    logger.info("SQLite database initialized")
    except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    raise

# Global state for habit creation
user_states: Dict[int, Dict[str, str]] = {}


def get_main_menu_keyboard(lang: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Create main menu keyboard."""
    _ = get_translation(lang)
    keyboard = [
        [
            InlineKeyboardButton(_("My Habits"), callback_data="show_habits"),
            InlineKeyboardButton(_("Create Habit"), callback_data="create_habit"),
        ],
        [
            InlineKeyboardButton(_("Statistics"), callback_data="show_stats"),
            InlineKeyboardButton(_("Charts"), callback_data="show_charts"),
        ],
        [InlineKeyboardButton(_("Help"), callback_data="show_help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Create language selection keyboard."""
    _ = get_translation(DEFAULT_LANGUAGE)
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ]
    logger.info(f"Language keyboard created: {keyboard}")
    return InlineKeyboardMarkup(keyboard)