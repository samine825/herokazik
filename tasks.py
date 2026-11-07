import asyncio
import logging
from datetime import datetime, timedelta
from random import randint

from telegram.error import TelegramError

from database import db
from utils import DATE_FMT, form

logger = logging.getLogger(__name__)

# (флаг, поле последнего прокрута, кулдаун, текст уведомления)
BOX_NOTIFICATIONS = (
    ('herobox_notified', 'last_daily', timedelta(hours=1),
     'Херобокс доступен — /herobox'),
    ('ultraherobox_notified', 'last_ultra_daily', timedelta(hours=24),
     'Ультра херобокс доступен — /ultraherobox'),
)

# уход горничной: (параметр, порог, действие, стоимость)
MAID_ACTIONS = (
    ('hunger', 40, 'покормить', 250),
    ('cleanliness', 25, 'помыть', 400),
    ('happiness', 50, 'поиграть', 0),
    ('health', 10, 'вылечить', 2000),
)


class Scheduler:
    """Раз в минуту проверяет уведомления о боксах, раз в 2 часа обслуживает
    фурри (горничные, деградация параметров, смерти) и списывает кредиты,
    раз в час делает бэкап."""

    MAINTENANCE_EVERY = timedelta(hours=2)
    BACKUP_EVERY = timedelta(hours=1)

    def __init__(self, application):
        self.application = application
        self.task = None
        self._next_maintenance = None
        self._last_backup = None

    def start(self):
        if self.task is None:
            now = datetime.now()
            self._next_maintenance = now + self.MAINTENANCE_EVERY
            self._last_backup = now
            self.task = asyncio.create_task(self._loop())
            logger.info("Планировщик запущен")

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
            logger.info("Планировщик остановлен")

    async def _loop(self):
        while True:
            try:
                await asyncio.sleep(60)
                now = datetime.now()

                await self._notify_boxes(now)

                if now >= self._next_maintenance:
                    self._next_maintenance = now + self.MAINTENANCE_EVERY
                    await self._maintenance(now)

                if now - self._last_backup >= self.BACKUP_EVERY:
                    db.backup()
                    self._last_backup = now
            except asyncio.CancelledError:
                logger.info("Планировщик остановлен по запросу")
                raise
            except Exception:
                logger.exception("Ошибка в планировщике, повтор через минуту")

    async def _notify_boxes(self, now):
        """Один раз уведомляет юзера в ЛС, когда истёк кулдаун бокса."""
        changed = False
        for user_id, user in db.data['users'].items():
            for flag, last_field, cooldown, text in BOX_NOTIFICATIONS:
                last = user.get(last_field)
                if not last or user.get(flag):
                    continue
                if now >= datetime.strptime(last, DATE_FMT) + cooldown:
                    user[flag] = True
                    changed = True
                    try:
                        await self.application.bot.send_message(chat_id=int(user_id), text=text)
                    except TelegramError as e:
                        logger.warning(f"Не удалось отправить уведомление {user_id}: {e}")
        if changed:
            db.save()

    async def _maintenance(self, now):
        ls_messages = {}

        # --- горничные ---
        for user_id, user in db.data['users'].items():
            if not any(f.get('is_maid', False) for f in user.get('furries', {}).values()):
                continue

            for name, furry in user['furries'].items():
                if furry.get('is_maid', False) or furry['health'] <= 0:
                    continue
                # как и при ручном уходе — без энергии ничего не делает
                if furry['energy'] < 20:
                    continue

                needed = [
                    (furry[param], param, action, cost)
                    for param, threshold, action, cost in MAID_ACTIONS
                    if furry[param] < threshold
                ]
                if not needed:
                    continue

                # одно действие за раз — по самому просевшему параметру
                _, _, action, cost = min(needed, key=lambda item: item[0])

                if user['balance'] < cost:
                    ls_messages.setdefault(user_id, []).append(
                        f"Горничная не смогла ухаживать за {name}: недостаточно средств"
                    )
                    continue

                if action == 'покормить':
                    furry['hunger'] = min(100, furry['hunger'] + randint(15, 25))
                elif action == 'помыть':
                    furry['cleanliness'] = min(100, furry['cleanliness'] + randint(30, 40))
                elif action == 'поиграть':
                    furry['happiness'] = min(100, furry['happiness'] + randint(20, 30))
                else:  # вылечить
                    furry['health'] = 100
                furry['energy'] = max(0, furry['energy'] - 20)
                user['balance'] -= cost
                ls_messages.setdefault(user_id, []).append(f"Горничная ухаживала за {name}: {action}")

        # --- деградация параметров, болезни, смерти ---
        for user_id, user in db.data['users'].items():
            furries_to_remove = []

            for name, furry in user.get('furries', {}).items():
                furry["hunger"] = max(0, furry["hunger"] - randint(2, 6))
                furry["cleanliness"] = max(0, furry["cleanliness"] - randint(1, 2))
                furry["happiness"] = max(0, furry["happiness"] - randint(1, 4))
                furry["energy"] = min(100, furry["energy"] + 20)

                if furry["hunger"] < 30:
                    furry["health"] -= randint(1, 3)
                    if furry["health"] <= 0:
                        furries_to_remove.append(name)
                        ls_messages.setdefault(user_id, []).append(f"Твой фурри {name} умер...")
                        continue
                    ls_messages.setdefault(user_id, []).append(f"Твой фурри {name} очень голоден")

                if furry["cleanliness"] < 20:
                    furry["health"] -= randint(2, 4)
                    if furry["health"] <= 0:
                        furries_to_remove.append(name)
                        ls_messages.setdefault(user_id, []).append(f"Твой фурри {name} умер...")
                        continue
                    ls_messages.setdefault(user_id, []).append(f"Твой фурри {name} пиздец грязный, помой его")

                if furry["happiness"] < 40:
                    furry["health"] -= randint(1, 2)
                    if furry["health"] <= 0:
                        furries_to_remove.append(name)
                        ls_messages.setdefault(user_id, []).append(f"Твой фурри {name} умер...")
                        continue
                    ls_messages.setdefault(user_id, []).append(f"Твой фурри {name} расстроен, ты уделяешь ему слишком мало внимания")

                if furry["happiness"] <= 0:
                    furries_to_remove.append(name)
                    ls_messages.setdefault(user_id, []).append(f"Твой фурри {name} убежал, потому что был не счастлив с тобой")

            for name in furries_to_remove:
                user['furries'].pop(name, None)

        # --- кредиты ---
        for user_id, user in db.data['users'].items():
            credit = user.get('credit')
            if credit and now >= datetime.strptime(credit['due_date'], DATE_FMT):
                user['balance'] -= credit['amount']
                del user['credit']
                ls_messages.setdefault(user_id, []).append(
                    f"Погашение кредита\n"
                    f"Списано: {form(credit['amount'])} херокоинов\n"
                    f"Новый баланс: {form(user['balance'])}"
                )

        db.save()

        for user_id, messages in ls_messages.items():
            try:
                await self.application.bot.send_message(chat_id=int(user_id), text="\n".join(messages))
            except TelegramError as e:
                logger.warning(f"Не удалось отправить ЛС {user_id}: {e}")
