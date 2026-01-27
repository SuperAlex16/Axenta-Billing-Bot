"""Общие обработчики команд"""
from telegram import Update
from telegram.ext import ContextTypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.constants import MSG_HELP
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    logger.info(f"Команда /help от пользователя {update.effective_chat.id}")
    await update.message.reply_text(MSG_HELP)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cancel"""
    logger.info(f"Команда /cancel от пользователя {update.effective_chat.id}")
    await update.message.reply_text("Действие отменено.")
