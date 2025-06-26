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

def get_frequency_keyboard(lang: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Create frequency selection keyboard."""
    _ = get_translation(lang)
    keyboard = [
        [InlineKeyboardButton(_("Daily"), callback_data="freq_daily")],
        [InlineKeyboardButton(_("Weekly"), callback_data="freq_weekly")],
        [InlineKeyboardButton(_("Monthly"), callback_data="freq_monthly")],
        [InlineKeyboardButton(_("Cancel"), callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_habits_keyboard(lang: str = DEFAULT_LANGUAGE) -> Optional[InlineKeyboardMarkup]:
    """Create keyboard with active habits."""
    _ = get_translation(lang)
    async with aiosqlite.connect(DB_PATH) as connection:
        cursor = await connection.execute("SELECT id, name FROM habits WHERE is_active = 1")
        habits = await cursor.fetchall()

    if not habits:
        return None

    keyboard = [[InlineKeyboardButton(f"✅ {name}", callback_data=f"complete_{id}")] for id, name in habits]
    keyboard.append([InlineKeyboardButton(_("Main Menu"), id="main_menu")])
    return InlineKeyboardMarkup(keyboard)


async def get_charts_keyboard(lang: Optional[str] = DEFAULT_LANGUAGE) -> Optional[InlineKeyboardButton]:
    """Create keyboard for chart selection."""
    _ = get_translation(lang)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM habits WHERE is_active = 1")
        habits = await cursor.fetchall()

    if not habits:
        return None

    keyboard = [[InlineKeyboardButton(f"📈 {name}", callback_data=f"chart_{id}")] for id, name in habits]
    keyboard.append([InlineKeyboardButton(_("Overview Chart"), callback_data="chart_all")])
    keyboard.append([InlineKeyboardButton(_("Main Menu"), callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


async def get_user_language(user_id: int) -> str:
    """Retrieve user's language."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else DEFAULT_LANGUAGE
    except Exception as e:
        logger.error(f"Error retrieving language for user {user_id}: {e}")
        return DEFAULT_LANGUAGE

async def set_user_language(user_id: int, lang: str) -> None:
    """Set user's language."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)",
                (user_id, lang)
            )
            await db.commit()
        logger.info(f"Set language for user {user_id} to {lang}")
    except Exception as e:
        logger.error(f"Error setting language for user {user_id}: {e}")

async def calculate_habit_stats(habit_id: str, habit_name: str, lang: str = DEFAULT_LANGUAGE) -> Dict:
    """Calculate habit statistics."""
    _ = get_translation(lang)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT completed_at FROM completions WHERE habit_id = ?", (habit_id,))
        completions = await cursor.fetchall()

    total_completions = len(completions)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_completions = [c for c in completions if datetime.fromisoformat(c[0]) > thirty_days_ago]
    completion_rate = (len(recent_completions) / 30.0 * 100) if recent_completions else 0

    completion_dates = sorted([datetime.fromisoformat(c[0]).date() for c in completions])
    current_streak = longest_streak = 0

    if completion_dates:
        today = datetime.now().date()
        current_date = today
        for completion_date in reversed(completion_dates):
            if completion_date == current_date or completion_date == current_date - timedelta(days=1):
                current_streak += 1
                current_date = completion_date
            else:
                break

        temp_streak = 1
        prev_date = completion_dates[0]
        for completion_date in completion_dates[1:]:
            if completion_date == prev_date + timedelta(days=1):
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 1
            prev_date = completion_date

    last_completion = datetime.fromisoformat(completions[-1][0]) if completions else None

    return {
        "habit_id": habit_id,
        "habit_name": habit_name,
        "total_completions": total_completions,
        "completion_rate": completion_rate,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "last_completion": last_completion,
    }
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    _ = get_translation(lang)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        user_exists = await cursor.fetchone()

    if not user_exists:
        message = _(
            "🌐 Welcome to Habit Tracker!\n\n"
            "Please select your preferred language:"
        )
        reply_markup = get_language_keyboard()
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info(f"Displayed language selection for new user {user_id}")
    else:
        user_name = update.effective_user.first_name or _("Friend")
        message = _(
            "🎯 Hello, {}! Welcome to Habit Tracker!\n\n"
            "Track your habits with analytics and charts.\n"
            "Choose an action:"
        ).format(user_name)
        reply_markup = get_main_menu_keyboard(lang)
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info(f"Displayed main menu for user {user_id}")



_translations: Dict[str, gettext.GNUTranslations] = {}


def get_translation(lang: str) -> callable:
    """Get translation function for the specified language."""
    # Clear cache for the language to force reload (for debugging)
    if lang in _translations:
        logger.info(f"Clearing translation cache for language: {lang}")
        del _translations[lang]

    try:
        logger.info(f"Attempting to load translation for language: {lang}")
        _translations[lang] = gettext.translation(
            "messages", "locale", languages=[lang]
        )
        logger.info(f"Successfully loaded translation for {lang}")
    except FileNotFoundError as e:
        logger.error(f"Translation file for {lang} not found: {e}")
        logger.warning(f"Falling back to English for language: {lang}")
        _translations[lang] = gettext.translation(
            "messages", "locale", languages=["en"], fallback=True
        )
    except Exception as e:
        logger.error(f"Error loading translation for {lang}: {e}")
        logger.warning(f"Falling back to English for language: {lang}")
        _translations[lang] = gettext.translation(
            "messages", "locale", languages=["en"], fallback=True
        )
    return _translations[lang].gettext


async def handle_language_selection(query: Update.callback_query, user_id: int, lang: str) -> None:
    """Handle language selection."""
    _ = get_translation(lang)
    new_lang = query.data.replace("lang_", "")
    await set_user_language(user_id, new_lang)
    # Force reload translation for new language
    _ = get_translation(new_lang)  # Update translation
    user_name = query.from_user.first_name or _("Friend")
    message = _(
        "🎯 Hello, {}! Language set to {}.\n\n"
        "Track your habits with analytics and charts.\n"
        "Choose an action:"
    ).format(user_name, _("Русский") if new_lang == "ru" else _("English"))
    reply_markup = get_main_menu_keyboard(new_lang)
    await query.edit_message_text(message, reply_markup=reply_markup)
    logger.info(f"User {user_id} selected language: {new_lang}")
    # Debug: Log the translated main menu buttons
    logger.info(f"Main menu buttons for {new_lang}: {[button.text for row in reply_markup.inline_keyboard for button in row]}")