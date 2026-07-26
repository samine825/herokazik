import asyncio
import logging
import os
import random
import re
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from handlers import (
    register, daily, ultradaily, balance, dep, top, rules,
    send, minet, furry, post,
    terraktis, DayanichL, fox, credit, kpass, top_callback
)
from database import load_data, save_reserv
from tasks import FurriesScheduler
from config import TOKEN

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """Инициализация после запуска и запуск фоновых задач"""
    
    # ИСПРАВЛЕНИЕ 1: Использование bot_data для хранения FurriesScheduler
    # Это исправляет: AttributeError: 'Application' object has no attribute 'furries_scheduler'
    application.bot_data["furries_scheduler"] = FurriesScheduler(application)
    application.bot_data["furries_scheduler"].start()
    
    terraktis(application)
    DayanichL(application)
    fox(application)

    # ИСПРАВЛЕНИЕ 2: Запуск долгосрочных задач через asyncio.create_task() 
    # в post_init, после инициализации application. Это исправляет: RuntimeError
    asyncio.create_task(save_process_long())
    asyncio.create_task(temp_control(application))
    #    print(id)
    #    if int(id) < 0:
    #        try:
    #            chat = await application.bot.get_chat(int(id))
    #            await asyncio.sleep(1)
    #            try:
    #                link = await chat.export_invite_link()
    #            except Exception as e:
    #                link = "нед"
    #            print(
    #                f"id: {chat.id} "
    #                f"name: {chat.title} "
    #                f"des: {chat.description} "
    #                f"link: {link} "
    #            )
    #            
    #        except Exception as e:
    #            print("E")
    #            continue

async def on_shutdown(application: Application):
    """Очистка при завершении"""
    # ИСПРАВЛЕНИЕ 3: Доступ к планировщику через bot_data
    if "furries_scheduler" in application.bot_data:
        await application.bot_data["furries_scheduler"].stop()

async def temp_control(app):
    while True:
        with open("/sys/class/thermal/thermal_zone0/temp","r") as f:
            temp = int(f.read()) / 1000.0
        if temp > 50:
            await app.bot.send_message(chat_id=5034376510, text=f"!!! cur temp: {temp}")
        await asyncio.sleep(30)
async def temp(update, context):
    try:
        with open("/sys/class/thermal/thermal_zone0/temp","r") as f:
            temp = int(f.read()) / 1000.0
        await update.message.reply_text(f"cur temp: {temp}")
            
        
        
    except Exception as e:
        print(e)

async def save_process_long():
    while True:
        files = [
            f for f in os.listdir("reserved/")
            if os.path.isfile("reserved/" + f)
        ]
        save_reserv(load_data(),f"reserved/casino_data{get_max_file(files)}.json")
        await asyncio.sleep(3600)

def get_max_file(dict):
    max_num = 0
    for key in dict:
        match = re.search(r'casino_data(\d+)\.json$', key)
        if match:
            current_num = int(match.group(1))
            if current_num > max_num:
                max_num = current_num
    return max_num + 1

def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    
    
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
        CommandHandler("temp", temp),
        CommandHandler("kpass", kpass),
        CallbackQueryHandler(top_callback, pattern="^top_")
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    
    application.run_polling(
        close_loop=False, 
        stop_signals=None
    )
    
    
if __name__ == "__main__":
    main()
