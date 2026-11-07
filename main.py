import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from handlers import (
    register, daily, ultradaily, balance, dep, top, rules,
    send, minet, furry, post,
    credit, kpass, top_callback
)
from database import db
from tasks import Scheduler
from config import TOKEN

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Запуск фоновых задач после инициализации"""
    application.bot_data["scheduler"] = Scheduler(application)
    application.bot_data["scheduler"].start()


async def on_shutdown(application: Application):
    """Очистка при завершении"""
    scheduler = application.bot_data.get("scheduler")
    if scheduler:
        await scheduler.stop()
    db.save()  # финальный сброс на диск


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN не задан. Экспортируй переменную окружения: export BOT_TOKEN=...")

    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .post_shutdown(on_shutdown)
        .build()
    )

    handlers = [
        CommandHandler("register", register),
        CommandHandler("herobox", daily),
        CommandHandler("ultraherobox", ultradaily),
        CommandHandler("balance", balance),
        CommandHandler("dep", dep),
        CommandHandler("topusers", top),
        CommandHandler("pravila", rules),
        CommandHandler("send", send),
        CommandHandler("minet", minet),
        CommandHandler("fur", furry),
        CommandHandler("post", post),
        CommandHandler("credit", credit),
        CommandHandler("kpass", kpass),
        CallbackQueryHandler(top_callback, pattern="^top_")
    ]

    for handler in handlers:
        application.add_handler(handler)

    application.run_polling()


if __name__ == "__main__":
    main()
