"""Test file."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import InlineKeyboardMarkup
from . import (
    set_user_language,
    get_charts_keyboard,
    get_language_keyboard,
    start_command,
)

class TestHabitBotFunctions(unittest.IsolatedAsyncioTestCase):
    """Test class."""

    @patch("aiosqlite.connect")
    async def test_set_user_language_executes_correct_query(self, mock_connect):
        """Проверяет, что SQL-запрос формируется правильно при установке языка."""
        mock_conn = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn

        await set_user_language(12345, "ru")

        mock_conn.execute.assert_awaited_once_with(
            "INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)",
            (12345, "ru")
        )
        mock_conn.commit.assert_awaited_once()
