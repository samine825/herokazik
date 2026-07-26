from random import randint
import logging
from datetime import datetime
from database import load_data, save_data, remove_credit
from telegram.ext import CallbackContext, ContextTypes, Application
import asyncio
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError
logger = logging.getLogger(__name__)




class FurriesScheduler:
    def __init__(self, application):
        self.application = application
        self.task = None

    async def process_furries(self):
        now = datetime.now()
        print(f"Вызов в {now.strftime('%H:%M:%S')}")
        
        data = load_data()
        messages_to_send = []
        users_to_update = []
        data_changed = False
        maid_service_messages = []
        
        for user_id, user in data['users'].items():
            maid = next((f for f in user.get('furries', {}).values() if f.get('is_maid', False)), None)
            
            if not maid:
                continue
                
            # Уход за всеми фурри кроме горничной
            for name, furry in user['furries'].items():
                if furry.get('is_maid', False) or furry['health'] <= 0:
                    continue
                
                actions = []
                cost = 0
                
                # Определяем необходимые действия
                if furry['hunger'] < 40:
                    actions.append("покормить")
                    cost += 250
                if furry['cleanliness'] < 25:
                    actions.append("помыть")
                    cost += 400
                if furry['happiness'] < 50:
                    actions.append("поиграть")
                if furry['health'] < 10:
                    actions.append("вылечить")
                    cost += 2000
                
                if not actions:
                    continue
                
                # Проверяем баланс
                if user['balance'] < cost:
                    maid_service_messages.append(
                        f"Горничная не смогла ухаживать за {name}: недостаточно средств"
                    )
                    continue
                
                # Выполняем действия
                if "покормить" in actions:
                    furry['hunger'] = min(100, furry['hunger'] + randint(15, 25))
                if "помыть" in actions:
                    furry['cleanliness'] = min(100, furry['cleanliness'] + randint(30, 40))
                if "поиграть" in actions:
                    furry['happiness'] = min(100, furry['happiness'] + randint(20, 30))
                if "вылечить" in actions:
                    furry['health'] = 100
                
                # Списание средств
                user['balance'] -= cost
                maid_service_messages.append(
                    f"Горничная ухаживала за {name}: {', '.join(actions)}"
                )
        
        # Сохраняем изменения
        if maid_service_messages:
            save_data(data)
        print(maid_service_messages)
        
        for user_id, user in data['users'].items():
            if "furries" not in user or not user["furries"]:
                continue
                
            furries_to_remove = []
            user_updates = []
            
            for name, furry in user["furries"].items():
                # Обновляем параметры
                furry["hunger"] = max(0, furry["hunger"] - randint(2, 6))
                furry["cleanliness"] = max(0, furry["cleanliness"] - randint(1, 2))
                furry["happiness"] = max(0, furry["happiness"] - randint(1, 4))
                furry["energy"] = min(100, furry["energy"] + 20)
                
                # Проверка условий
                if furry["hunger"] < 30:
                    furry["health"] -= randint(1, 3)
                    if furry["health"] <= 0:
                        furries_to_remove.append(name)
                        chats = await get_user_chats(self.application.bot, user_id, data["chats"])
                        for chat in chats:
                            messages_to_send.append((chat, f"@{user['username']} Твой фурри {name} умер..."))
                        continue
                    else:
                        chats = await get_user_chats(self.application.bot, user_id, data["chats"])
                        for chat in chats:
                            messages_to_send.append((chat, f"@{user['username']} Твой фурри {name} очень голоден"))
                
                if furry["cleanliness"] < 20:
                    furry["health"] -= randint(2, 4)
                    if furry["health"] <= 0:
                        furries_to_remove.append(name)
                        chats = await get_user_chats(self.application.bot, user_id, data["chats"])
                        for chat in chats:
                            messages_to_send.append((chat, f"@{user['username']} Твой фурри {name} умер..."))
                        continue
                    else:
                        chats = await get_user_chats(self.application.bot, user_id, data["chats"])
                        for chat in chats:
                            messages_to_send.append((chat, f"@{user['username']} Твой фурри {name} пиздец грязный, помой его"))
                
                if furry["happiness"] < 40:
                    furry["health"] -= randint(1, 2)
                    if furry["health"] <= 0:
                        furries_to_remove.append(name)
                        chats = await get_user_chats(self.application.bot, user_id, data["chats"])
                        for chat in chats:
                            messages_to_send.append((chat, f"@{user['username']} Твой фурри {name} умер..."))
                        continue
                    else:
                        chats = await get_user_chats(self.application.bot, user_id, data["chats"])
                        for chat in chats:
                            messages_to_send.append((chat, f"@{user['username']} Твой фурри {name} расстроен, ты уделяешь ему слишком мало внимания"))
                
                if furry["happiness"] <= 0:
                    furries_to_remove.append(name)
                    chats = await get_user_chats(self.application.bot, user_id, data["chats"])
                    for chat in chats:
                        messages_to_send.append((chat, f"@{user['username']} Твой фурри {name} убежал, потому что был не счастлив с тобой"))
            
            # Помечаем пользователя для обновления
            if furries_to_remove:
                users_to_update.append((user_id, furries_to_remove))

        # Применяем изменения
        for user_id, furries_to_remove in users_to_update:
            for name in furries_to_remove:
                if name in data['users'][user_id]['furries']:
                    del data['users'][user_id]['furries'][name]
        
        save_data(data)
    
        
        fur = {"nameless_furry1": {
            "rarity": 0,
            "path": "///",
            "hunger": 100,        # 0-100 (умирает при 0)
            "happiness": 100,     # 0-100 (убегает при 0)
            "energy": 100,        # 0-100 (не может действовать при 0)
            "cleanliness": 100,   # 0-100 (болеет при <30)
            "health": 100,       # 0-100 (умирает при 0)
            "born": "2025-07-15 14:30:00",  # дата рождения
            "lastrep": "2025-07-15 14:30:00"
        }}
        now = datetime.now()
        credit_messages = []
        
        for user_id, user in data['users'].items():
            if 'credit' in user and user['credit']:
                due_date = datetime.strptime(user['credit']['due_date'], '%Y-%m-%d %H:%M:%S')
                if now >= due_date:
                    amount = user['credit']['amount']
                    user['balance'] -= amount
                    
                    # Удалить кредит
                    del user['credit']
                    data_changed = True
                    
                    text = f"@{user['username']} Погашение кредита\nСписано: {amount} херокоинов\nНовый баланс: {user['balance']}"
                    chats = await get_user_chats(self.application.bot, int(user_id), data["chats"])
                    for chat in chats:
                        credit_messages.append((chat, text))

    # Сохраняем данные если были изменения
        if data_changed or furries_to_remove:
            save_data(data)
        
        # Объединяем сообщения
        all_messages = {}
        for chat_id, text in messages_to_send:
            if chat_id not in all_messages:
                all_messages[chat_id] = []
            all_messages[chat_id].append(text)

        for chat_id, messages in all_messages.items():
            try:
                # Объединяем все сообщения для этого чата
                full_text = "\n".join(messages)
                await self.application.bot.send_message(chat_id=chat_id, text=full_text)
            except TelegramError as e:
                logger.error(f"Ошибка отправки сообщения: {e}")
        
        if credit_messages:
            credit_dict = {}
            for chat_id, text in credit_messages:
                if chat_id not in credit_dict:
                    credit_dict[chat_id] = []
                credit_dict[chat_id].append(text)
            
            for chat_id, messages in credit_dict.items():
                await self.application.bot.send_message(chat_id=chat_id, text="\n".join(messages))
    async def _hourly_loop(self):
        while True:
            try:
                now = datetime.now()
                next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
                delay = (next_hour - now).total_seconds()
                if delay < 0:
                    delay = 0
                logger.info(f"Следующая проверка через {delay:.1f} секунд")
                await asyncio.sleep(delay)
                
                await self.process_furries()
            except asyncio.CancelledError:
                logger.info("Планировщик фурри остановлен по запросу")
                raise
            except Exception as e:
                logger.exception(f"Критическая ошибка в планировщике: {e}")
                # Перезапуск после задержки при критических ошибках
                await asyncio.sleep(60)

    def start(self):
        """Запуск планировщика"""
        if self.task is None:
            self.task = asyncio.create_task(self._hourly_loop())
            logger.info("Планировщик фурри запущен")

    async def stop(self):
        """Остановка планировщика"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
            logger.info("Планировщик фурри остановлен")
            




async def get_user_chats(bot: Bot, user_id: int, chats_list: list[int]) -> list[int]:
    user_chats = []
    user_chats = []
    unique_chats = set()  # Для устранения дубликатов
    
    for chat_id in chats_list:
        # Проверка уникальности
        if chat_id in unique_chats:
            continue
        unique_chats.add(chat_id)
        try:
            # Если chat_id положительный — это личный чат (user_id должен совпадать)
            if chat_id > 0:
                if chat_id == user_id:
                    user_chats.append(chat_id)
            # Если chat_id отрицательный — это группа/канал (проверяем get_chat_member)
            else:
                member = await bot.get_chat_member(chat_id, user_id)
                if member.status not in ["left", "kicked"]:
                    user_chats.append(chat_id)
        except TelegramError as e:
            print(f"Ошибка при проверке чата {chat_id}: {e}")
    
    return user_chats
