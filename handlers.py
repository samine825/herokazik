import logging
import os
import random
import re
import time
from datetime import datetime, timedelta
from random import randint

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, helpers
from telegram.error import TelegramError
from telegram.ext import CallbackContext

from database import (
    load_data, save_data, get_user, create_user, update_balance,
    add_chat, get_user_id_by_username, set_credit, remove_credit
)
from logger import log_event
from config import ADMIN_ID
from utils import (
    DATE_FMT, RARITY_NAMES, RARITY_FOLDERS, roll_rarity, furry_price,
    spin_roulette, get_color, get_parity, form, format_wait, payout_bonus
)

logger = logging.getLogger(__name__)

HEROBOX_COOLDOWN = timedelta(hours=1)
ULTRAHEROBOX_COOLDOWN = timedelta(hours=24)

user_last_message_time = {}


def get_max_furry_number(furries_dict):
    max_num = 0
    for key in furries_dict.keys():
        match = re.search(r'furry(\d+)$', key.lower())
        if match:
            current_num = int(match.group(1))
            if current_num > max_num:
                max_num = current_num
    return max_num + 1


async def track_chats(update: Update, context: CallbackContext) -> bool:
    """Обрабатывает сообщения и возвращает False если сообщение нужно игнорировать"""
    user_id = update.effective_user.id
    current_time = time.time()

    # подчищаем устаревшие записи, чтобы словарь не рос бесконечно
    if len(user_last_message_time) > 10000:
        cutoff = current_time - 3600
        for uid in [uid for uid, ts in user_last_message_time.items() if ts < cutoff]:
            del user_last_message_time[uid]

    if user_id in user_last_message_time and user_id != ADMIN_ID:
        if current_time - user_last_message_time[user_id] < 1.0:
            try:
                await update.message.delete()
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения: {e}")
            return False

    user_last_message_time[user_id] = current_time
    add_chat(update.effective_chat.id)
    return True


async def register(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    user = update.message.from_user
    user_id = user.id
    username = user.username or user.first_name

    if get_user(user_id):
        await update.message.reply_text("Ты уже зарегистрирован еблан")
        return

    create_user(user_id, username)
    log_event(f"{username} зарегистрировался в системе")
    await update.message.reply_text(
        f"Добро пожаловать {username} в казик херобрина\n"
        f"Для просмотра правил используй /pravila"
    )


async def daily(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    user_id = update.message.from_user.id
    user_data = get_user(user_id)

    if not user_data:
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return
    now = datetime.now()
    last_daily = user_data.get('last_daily')
    if last_daily:
        last_date = datetime.strptime(last_daily, DATE_FMT)
        if (now - last_date) < HEROBOX_COOLDOWN:
            wait_time = last_date + HEROBOX_COOLDOWN - now
            await update.message.reply_text(
                f"Ты ахуел\nСледующий херобокс через: {format_wait(wait_time)}"
            )
            return
    user_data['last_daily'] = now.strftime(DATE_FMT)
    user_data['herobox_notified'] = False
    save_data()

    item = random.randint(1, 1000000)
    if user_data.get('pass'):
        item = random.randint(1, 500000)

    rar = roll_rarity(item)
    if rar is not None:
        await gettingfurry(update, rar, user_id, True, "Следующий херобокс через 1 час")
    else:
        reward = random.randint(100, 10000)
        if user_data.get('pass'):
            reward = random.randint(500, 50000)
        update_balance(user_id, reward)
        log_event(f"{user_data['username']} выбил из херобокса {reward} херокоинов")
        await update.message.reply_text(
            f"Тебе выпало... {form(reward)} херокоинов!\nСледующий херобокс через 1 час"
        )


async def ultradaily(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    user_id = update.message.from_user.id
    user_data = get_user(user_id)

    if not user_data:
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return
    now = datetime.now()
    last_daily = user_data.get('last_ultra_daily')
    if last_daily:
        last_date = datetime.strptime(last_daily, DATE_FMT)
        if (now - last_date) < ULTRAHEROBOX_COOLDOWN:
            wait_time = last_date + ULTRAHEROBOX_COOLDOWN - now
            await update.message.reply_text(
                f"Ты ахуел\nСледующий ультра херобокс через: {format_wait(wait_time)}"
            )
            return
    user_data['last_ultra_daily'] = now.strftime(DATE_FMT)
    user_data['ultraherobox_notified'] = False
    save_data()

    item = random.randint(1, 200000)
    if user_data.get('pass'):
        item = random.randint(1, 150000)

    rar = roll_rarity(item)
    if rar is not None:
        await gettingfurry(update, rar, user_id, True, "Следующий ультра херобокс через 24 часа")
    else:
        reward = random.randint(100000, 10000000)
        if user_data.get('pass'):
            reward = random.randint(500000, 50000000)
        update_balance(user_id, reward)
        log_event(f"{user_data['username']} выбил из ультра херобокса {reward} херокоинов")
        await update.message.reply_text(
            f"Тебе выпало... {form(reward)} херокоинов!\nСледующий ультра херобокс через 24 часа"
        )


async def send_furry_media(update: Update, path, rar, caption):
    """Отправляет фурри: редкость 9 — гифкой, остальные — фото, без файла — текст."""
    if rar == 9 and path:
        await update.message.reply_animation(caption=caption, animation=path)
    elif path:
        await update.message.reply_photo(caption=caption, photo=path)
    else:
        await update.message.reply_text(caption)


async def gettingfurry(update: Update, rar, user_id, message: bool, after_text: str = None) -> bool:
    """Добавляет фурри указанной редкости.

    Возвращает True, если фурри добавлен, False — если инвентарь полон
    и выплачена компенсация.
    """
    folder = RARITY_FOLDERS[rar]
    name = RARITY_NAMES[rar]

    files = []
    if os.path.isdir(folder):
        files = [f for f in os.listdir(folder) if os.path.isfile(folder + f)]
    if rar == 9:
        files = [f for f in files if f.lower().endswith('.gif')]
    photo_path = folder + random.choice(files) if files else None

    user = get_user(user_id)
    now = datetime.now()

    g = 25 if user.get('pass') else 15
    if len(user['furries']) >= g:
        compensation = furry_price(rar, 0)
        update_balance(user_id, compensation)
        log_event(f"{user['username']} выбил из херобокса {name} фурри. с компенсацией")
        caption = (
            f"{name} ФУРРИ\nНо у тебя и так уже есть {g} фурри, "
            f"поэтому компенсация: {form(compensation)} херокоинов"
        )
        await send_furry_media(update, photo_path, rar, caption)
        return False

    max_number = get_max_furry_number(user['furries'])
    user['furries'][f'furry{max_number}'] = {
        "rarity": rar,
        "path": photo_path or "",
        "hunger": 100,
        "happiness": 100,
        "energy": 100,
        "cleanliness": 100,
        "health": 100,
        "born": now.strftime(DATE_FMT),
        "lastrep": now.strftime(DATE_FMT),
        "is_maid": False
    }
    save_data()

    if message:
        log_event(f"{user['username']} выбил из херобокса {name} фурри")
        caption = f"Тебе выпал... {name} ФУРРИ!\n{after_text}"
    else:
        log_event(f"{user['username']} родил {name} фурри")
        caption = f"У вас родился... {name} ФУРРИ!\nСледующее спаривание будет доступно через 1 день"
    await send_furry_media(update, photo_path, rar, caption)
    return True


async def balance(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    user_id = update.message.from_user.id
    user_data = get_user(user_id)

    if not user_data:
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return

    await update.message.reply_text(
        f"Твой баланс:\n"
        f"{form(user_data['balance'])} херокоинов\n"
    )


async def dep(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    try:
        user_id = update.message.from_user.id
        user_data = get_user(user_id)

        if not user_data:
            await update.message.reply_text("Ты не зарегистрирован, используй /register")
            return

        if len(context.args) < 2:
            await update.message.reply_text("еблан, посмотри как командой пользоваться в /pravila")
            return

        is_furry_bet = context.args[0].lower() == "фурри"

        if is_furry_bet:
            furry_name = context.args[1].lower()
            if furry_name not in user_data["furries"]:
                await update.message.reply_text("ты нищеброд")
                return
            furry = user_data["furries"][furry_name]
            born = datetime.strptime(furry["born"], DATE_FMT)
            amount = furry_price(furry["rarity"], (datetime.now() - born).days)
            bet_value = " ".join(context.args[2:]).lower()
        else:
            try:
                amount = int(context.args[0])
                bet_value = " ".join(context.args[1:]).lower()

                if amount < 10:
                    await update.message.reply_text("Минимальная ставка: 10 херокоинов")
                    return
                if amount > user_data['balance']:
                    await update.message.reply_text("ты нищеброд")
                    return
            except ValueError:
                await update.message.reply_text("Неверная сумма ставки")
                return

        result = spin_roulette()
        result_color = get_color(result)
        result_parity = get_parity(result)

        win = False
        multiplier = 0
        valid = False
        if bet_value in ['красный', 'красное']:
            valid = True
            bet_value = 'красный'
            if bet_value == result_color:
                win = True
                multiplier = 2

        elif bet_value in ['черный', 'черное', 'чëрный', 'чëрное', 'чёрный', 'чёрное']:
            valid = True
            bet_value = 'черный'
            if bet_value == result_color:
                win = True
                multiplier = 2

        elif bet_value in ['зеленый', 'зеленое', 'зелëный', 'зелëное', 'зелёный', 'зелёное']:
            valid = True
            bet_value = 'зеленый'
            if bet_value == result_color:
                win = True
                multiplier = 40

        elif bet_value in ['чет', 'четное', 'чëт', 'чëтное', 'чёт', 'чётное']:
            valid = True
            bet_value = 'чет'
            if bet_value == result_parity:
                win = True
                multiplier = 2

        elif bet_value in ['нечет', 'нечетное', 'нечëт', 'нечëтное', 'нечёт', 'нечётное']:
            valid = True
            bet_value = 'нечет'
            if bet_value == result_parity:
                win = True
                multiplier = 2

        else:
            try:
                number_bet = int(bet_value)

                if 0 <= number_bet <= 36:
                    valid = True
                    if number_bet == result:
                        win = True
                        multiplier = 40
            except ValueError:
                pass

        # база x2, бонусы за фурри и пасс сверху
        rarity_bonuses = {
            0: 0.0005,   # Редкий
            1: 0.001,    # Сверхредкий
            2: 0.0025,   # Эпический
            3: 0.005,    # Мифический
            4: 0.01,     # Легендарный
            5: 0.025,    # Невозможный
            6: 0.05,     # Лудоманский
            7: 0.1,      # ебланский
            8: 0.25,     # херобринский
            9: 0.5       # ∞
        }
        total_bonus = 2.0
        if user_data.get('pass'):
            total_bonus += 0.2
        for furry in user_data.get('furries', {}).values():
            total_bonus += rarity_bonuses.get(furry['rarity'], 0)

        if valid:
            if win:
                # равные шансы — x2 + бонусы, число/зелёное — x40 + бонусы (x20 от базы)
                multiplier = total_bonus if multiplier == 2 else total_bonus * 20
                win_amount = int(amount * multiplier)
                if is_furry_bet:
                    del user_data["furries"][furry_name]
                    save_data()
                else:
                    update_balance(user_id, -amount)

                update_balance(user_id, win_amount)
                log_event(f"{user_data['username']} выиграл {win_amount} херокоинов (ставка: {amount} на {bet_value}, furry: {is_furry_bet})")
                response = (
                    f"Ебать, выпало: {result} ({result_color}, {result_parity})\n"
                    f"Коэффициент: x{multiplier:g}\n"
                    f"Твой выигрыш: {form(win_amount)} херокоинов!\n"
                )
            else:
                if is_furry_bet:
                    del user_data["furries"][furry_name]
                    save_data()
                    log_event(f"{user_data['username']} проиграл {furry_name} фурри (ставка: {amount} на {bet_value})")
                    response = (
                        f"Лох ебанный, выпало: {result} ({result_color}, {result_parity})\n"
                        f"Ты потерял {furry_name}...\n"
                    )
                else:
                    update_balance(user_id, -amount)
                    log_event(f"{user_data['username']} проиграл {amount} херокоинов (ставка: {amount} на {bet_value})")
                    response = (
                        f"Лох ебанный, выпало: {result} ({result_color}, {result_parity})\n"
                        f"Ты потерял: {form(amount)} херокоинов\n"
                    )
        else:
            response = "еблан, посмотри как командой пользоваться в /pravila"
        await update.message.reply_text(response)

    except Exception:
        logger.exception("Error in dep")
        await update.message.reply_text("еблан, посмотри как командой пользоваться в /pravila")


def _paginated(title, items, page, format_item, callback_prefix):
    if not items:
        return "список пуст", None

    total_pages = (len(items) + 9) // 10
    start_idx = page * 10
    page_items = items[start_idx:start_idx + 10]

    response = f"{title} (страница {page + 1}/{total_pages}):\n\n"
    for i, item in enumerate(page_items, start_idx + 1):
        response += format_item(i, item)

    keyboard = []
    if page > 0:
        keyboard.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{callback_prefix}_{page}"))
    if page < total_pages - 1:
        keyboard.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"{callback_prefix}_{page + 2}"))

    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    return response, reply_markup


async def top(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    user_id = update.effective_user.id
    if not get_user(user_id):
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return

    data = load_data()
    args = context.args

    # Определяем страницу
    page = 0
    if args and args[-1].isdigit():
        page = int(args[-1]) - 1
        args = args[:-1]

    if not args:
        await update.message.reply_text(
            "Укажи тип топа: лудоманы / нищеброды / сосуны / фурриманы / возрастфурри / редкостьфурри"
        )
        return

    top_type = args[0].lower()

    if top_type == "фурриманы":
        items = sorted(data['users'].values(), key=lambda x: len(x["furries"]), reverse=True)
        response, reply_markup = _paginated(
            "ТОП ФУРРИМАНОВ", items, page,
            lambda i, u: f"{i}. {u['username']}: {len(u['furries'])} фурри\n",
            "top_furrimany"
        )

    elif top_type == "редкостьфурри":
        all_furries = []
        for uid, u in data['users'].items():
            for furry_name, furry_data in u.get("furries", {}).items():
                all_furries.append((furry_data["rarity"], furry_name, u["username"]))
        all_furries.sort(key=lambda x: x[0], reverse=True)
        response, reply_markup = _paginated(
            "ТОП ФУРРИ ПО РЕДКОСТИ", all_furries, page,
            lambda i, f: f"{i}. {f[1]}: {RARITY_NAMES.get(f[0], 'Неизвестно')} ({f[2]})\n",
            "top_rarity"
        )

    elif top_type == "возрастфурри":
        now = datetime.now()
        all_furries = []
        for uid, u in data['users'].items():
            for furry_name, furry_data in u.get("furries", {}).items():
                born_date = datetime.strptime(furry_data["born"], DATE_FMT)
                all_furries.append(((now - born_date).days, furry_name, u["username"]))
        all_furries.sort(key=lambda x: x[0], reverse=True)
        response, reply_markup = _paginated(
            "ТОП САМЫХ ВЗРОСЛЫХ ФУРРИ", all_furries, page,
            lambda i, f: f"{i}. {f[1]}: {f[0]} дней ({f[2]})\n",
            "top_age"
        )

    elif top_type == "лудоманы":
        items = sorted(data['users'].values(), key=lambda x: sort_without_credit(x), reverse=True)
        response, reply_markup = _paginated(
            "ТОП ЛУДОМАНОВ МИРА", items, page,
            lambda i, u: f"{i}. {u['username']}: {form(sort_without_credit(u))} херокоинов\n",
            "top_ludomany"
        )

    elif top_type == "нищеброды":
        items = sorted(data['users'].values(), key=lambda x: x['balance'])
        response, reply_markup = _paginated(
            "ТОП НИЩЕБРОДОВ МИРА", items, page,
            lambda i, u: f"{i}. {u['username']}: {form(u['balance'])} херокоинов\n",
            "top_poor"
        )

    elif top_type == "сосуны":
        items = sorted(data['users'].values(), key=lambda x: x['minetov'], reverse=True)
        response, reply_markup = _paginated(
            "ТОП СОСУНОВ МИРА", items, page,
            lambda i, u: f"{i}. {u['username']}: {form(u['minetov'])} хуев отсосано\n",
            "top_sosuny"
        )

    else:
        await update.message.reply_text("Не знаю такой тип. Смотри /pravila")
        return

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(response, reply_markup=reply_markup)
        except TelegramError:
            pass  # например, "message is not modified" при повторном клике
    else:
        await update.message.reply_text(response, reply_markup=reply_markup)


async def top_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("top_"):
        parts = data.split("_")
        if len(parts) >= 3:
            type_map = {
                "furrimany": "фурриманы",
                "rarity": "редкостьфурри",
                "age": "возрастфурри",
                "ludomany": "лудоманы",
                "poor": "нищеброды",
                "sosuny": "сосуны"
            }
            top_key = parts[1]
            arg_type = type_map.get(top_key)
            page = int(parts[2])
            if arg_type:
                context.args = [arg_type, str(page)]
                await top(update, context)


def sort_without_credit(dat):
    balance = dat['balance']
    if 'credit' in dat and dat['credit'] is not None:
        balance -= dat['credit']['amount']
    return balance


async def rules(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    rules_text = """
*ПРАВИЛА* 
>/register — Регистрация в казике
>
>/herobox — Херобокс \\(раз в час\\)
>
>/ultraherobox — Ультра херобокс \\(раз в 24 часа\\)
>
>/balance — Проверить баланс
>
>/minet <ответ, ID или @\\> — Отсосать хуй
>
>/send <тип\\> <значение\\> <ответ, ID или @\\>
>   — Тип: фурри или херокоины
>   — Значение: количество коинов, или имя фурри
>   
>/topusers <тип\\> — Посмотреть топ игроков
>   — Тип: Лудоманы / Нищеброды / Сосуны / Фурриманы / Возрастфурри / Редкостьфурри
>   
>/dep <ставка\\> <тип\\> — Депнуть херокоины
>   — Тип: Красный \\(x2\\) / Черный \\(x2\\) / Зеленый \\(x40\\) / 0\\-36 \\(x40\\) / Чет \\(x2\\) / Нечет \\(x2\\)
>   — Ставка от 10 херокоинов
>/dep фурри <имя\\> <тип\\> — Депнуть фурри
>   — Тип: Красный \\(x2\\) / Черный \\(x2\\) / Зеленый \\(x40\\) / 0\\-36 \\(x40\\) / Чет \\(x2\\) / Нечет \\(x2\\)
>   — Цена фурри считается так: \\(дни\\+1\\) × 5^\\(редкость\\+1\\) × 10000
>
>/credit — Посмотреть активный кредит
>/credit списать — Погасить кредит досрочно 
>/credit \\<сумма\\> \\<срок\\> — Оформить кредит
>   — Максимальная сумма х100 от баланса
>   — Срок от 1 до 10 дней
>
>/fur — Список имен твоих фурри
>/fur <имя\\> — Открытие профиля фурри
>/fur <имя\\> Поиграть
>   — \\+20\\-30 к счастью, \\-20 энергии 
>/fur <имя\\> Покормить
>   — \\+15\\-25 к сытости, \\-20 энергии
>   — Стоимость: 250 Херокоинов
>/fur <имя\\> Помыть
>   — \\+30\\-40 к чистоте, \\-20 энергии
>   — Стоимость: 400 Херокоинов
>/fur <имя\\> Вылечить
>   — Восполнение здоровья до максимума
>   — Стоимость: 2000 Херокоинов
>/fur <имя\\> переименовать <новое имя\\> 
>   — переименование твоего фурри
>/fur <имя\\> спарить <имя2\\> 
>   — доступно только если обоим фурри есть минимум 5 дней
>   — рожденный фурри получает среднюю редкость родителей
>   — спаривать фурри можно не чаще 1 раза в 24 часа
    """
    await update.message.reply_text(rules_text, parse_mode="MarkdownV2")


async def send(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    sender_id = update.effective_user.id
    message = update.effective_message
    args = context.args

    sender_data = get_user(sender_id)
    if not sender_data:
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return

    if not args:
        await update.message.reply_text(
            "еблан, /pravila читай"
        )
        return

    data = load_data()

    transfer_type = args[0].lower()

    if transfer_type not in ["херокоины", "фурри"]:
        await update.message.reply_text("Укажи тип передачи: 'херокоины' или 'фурри'")
        return

    recipient_identifier = None
    recipient_id = None

    if len(args) > 2:
        recipient_identifier = args[2]
    elif message.reply_to_message:
        recipient_id = message.reply_to_message.from_user.id
    else:
        await update.message.reply_text("Укажи получателя: @username, ID или ответь на сообщение")
        return

    if recipient_identifier:
        if recipient_identifier.startswith('@'):
            username = recipient_identifier[1:]
            recipient_id = get_user_id_by_username(username)
            if not recipient_id:
                await update.message.reply_text("Пользователь не зарегистрирован")
                return
        elif recipient_identifier.isdigit():
            recipient_id = int(recipient_identifier)
            if str(recipient_id) not in data["users"]:
                await update.message.reply_text("Пользователь не зарегистрирован")
                return
        else:
            await update.message.reply_text("Укажите ID или @username получателя")
            return

    if sender_id == recipient_id:
        await update.message.reply_text("Нельзя отправлять самому себе")
        return

    if transfer_type == "херокоины":
        try:
            amount = int(args[1])
            if amount <= 0:
                await update.message.reply_text("Укажи положительную сумму")
                return
            if sort_without_credit(data['users'][str(sender_id)]) < amount:
                await update.message.reply_text("Нельзя отправлять деньги, взятые в кредит")
                return

            if data['users'][str(sender_id)]['balance'] >= amount:
                update_balance(sender_id, -amount)
                update_balance(recipient_id, amount)
                log_event(
                    f"{data['users'][str(sender_id)]['username']} перевел {amount} херокоинов "
                    f"{data['users'][str(recipient_id)]['username']}"
                )
                await update.message.reply_text(
                    f"Херокоины переведены\n"
                    f"Отправитель: {data['users'][str(sender_id)]['username']}\n"
                    f"Получатель: {data['users'][str(recipient_id)]['username']}\n"
                    f"Сумма: {form(amount)}"
                )
            else:
                await update.message.reply_text("Недостаточно херокоинов")
        except ValueError:
            await update.message.reply_text("Укажи корректную сумму")

    elif transfer_type == "фурри":
        furry_name = args[1].lower()

        if furry_name not in data['users'][str(sender_id)]['furries']:
            await update.message.reply_text("У тебя нет такого фурри")
            return

        recipient = data['users'][str(recipient_id)]
        g = 25 if recipient.get('pass') else 15
        if len(recipient['furries']) >= g:
            await update.message.reply_text(f"у {recipient['username']} и без того дохуя фурри")
            return

        furry_data = data['users'][str(sender_id)]['furries'][furry_name]

        new_name = furry_name
        if new_name in recipient['furries']:
            new_name = f"furry{get_max_furry_number(recipient['furries'])}"
        furry_data['is_maid'] = False
        recipient['furries'][new_name] = furry_data
        del data['users'][str(sender_id)]['furries'][furry_name]
        save_data()

        log_event(
            f"{data['users'][str(sender_id)]['username']} передал фурри {furry_name} "
            f"{recipient['username']} (новое имя: {new_name})"
        )

        await update.message.reply_text(
            f"{furry_name} передан\n"
            f"Отправитель: {data['users'][str(sender_id)]['username']}\n"
            f"Получатель: {recipient['username']}\n"
        )


async def minet(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    sender_id = update.effective_user.id
    message = update.effective_message
    args = context.args

    sender_data = get_user(sender_id)
    if not sender_data:
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return

    data = load_data()

    if len(args) > 0:
        recipient_identifier = args[0]

        if recipient_identifier.startswith('@'):
            username = recipient_identifier[1:]
            recipient_id = get_user_id_by_username(username)
            if not recipient_id:
                await update.message.reply_text("Пользователь не зарегестрирован")
                return

        elif recipient_identifier.isdigit():
            recipient_id = int(recipient_identifier)
            if str(recipient_id) not in data["users"]:
                await update.message.reply_text("Пользователь не зарегестрирован")
                return
        else:
            await update.message.reply_text("Укажите ID или @username получателя")
            return

    elif message.reply_to_message:
        recipient_id = message.reply_to_message.from_user.id
        if str(recipient_id) not in data["users"]:
            await update.message.reply_text("Пользователь не зарегестрирован")
            return

    else:
        await update.message.reply_text("Укажи получателя: @username, ID или ответь на сообщение")
        return

    sender_data['minetov'] += 1
    save_data()

    log_event(f"{sender_data['username']} отсосал у {data['users'][str(recipient_id)]['username']}")
    if str(sender_id) == str(recipient_id):
        await update.message.reply_text(
            f"{sender_data['username']} как ты дотянулся??\n"
            f"хуев отсосано: {form(sender_data['minetov'])}"
        )
    else:
        await update.message.reply_text(
            f"{sender_data['username']} отсосал у {data['users'][str(recipient_id)]['username']}\n"
            f"хуев отсосано: {form(sender_data['minetov'])}"
        )


async def furry(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    args = context.args
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if not user_data:
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return
    data = load_data()
    if len(args) > 3:
        await update.message.reply_text("еблан, посмотри как командой пользоваться в /pravila")
        return
    if len(args) == 3:
        if args[0].lower() in data["users"][str(user_id)]["furries"]:
            subcommand = args[1].lower()
            if subcommand == "переименовать" and args[0].lower() != args[2].lower():
                if args[2].lower() not in data["users"][str(user_id)]["furries"]:

                    data["users"][str(user_id)]["furries"][args[2].lower()] = data["users"][str(user_id)]["furries"][args[0].lower()]
                    del data["users"][str(user_id)]["furries"][args[0].lower()]
                    save_data()
                    log_event(f"{user_data['username']} переименовал фурри {args[0]} в {args[2]}")
                    await update.message.reply_text(f"{args[0]} успешно переименован в {args[2]}")
                else:
                    await update.message.reply_text("У тебя уже есть такой фурри")
            elif subcommand == "спарить" and args[0].lower() != args[2].lower():
                if args[2].lower() in data["users"][str(user_id)]["furries"]:
                    now = datetime.now()
                    fur1 = data["users"][str(user_id)]["furries"][args[0].lower()]
                    fur2 = data["users"][str(user_id)]["furries"][args[2].lower()]
                    age1 = now - datetime.strptime(fur1["born"], DATE_FMT)
                    age2 = now - datetime.strptime(fur2["born"], DATE_FMT)
                    if age1.days >= 5 and age2.days >= 5:
                        rep1 = now - datetime.strptime(fur1["lastrep"], DATE_FMT)
                        rep2 = now - datetime.strptime(fur2["lastrep"], DATE_FMT)
                        if rep1 >= timedelta(hours=24) and rep2 >= timedelta(hours=24):
                            rar = int((fur1["rarity"] + fur2["rarity"] + 1) / 2.0)
                            # если инвентарь полон, выплачивается компенсация и кулдаун не тратится
                            born_ok = await gettingfurry(update, rar, user_id, False)
                            if born_ok:
                                fur1["lastrep"] = now.strftime(DATE_FMT)
                                fur2["lastrep"] = now.strftime(DATE_FMT)
                                save_data()
                        else:
                            response = "Еще не прошло 24 часа...\nСледующее спаривание через:\n"

                            wait1 = datetime.strptime(fur1["lastrep"], DATE_FMT) + timedelta(hours=24) - now
                            wait2 = datetime.strptime(fur2["lastrep"], DATE_FMT) + timedelta(hours=24) - now

                            if wait1.total_seconds() > 0:
                                response += f"{args[0].lower()}: {format_wait(wait1)}\n"
                            if wait2.total_seconds() > 0:
                                response += f"{args[2].lower()}: {format_wait(wait2)}\n"

                            await update.message.reply_text(response)
                    else:
                        await update.message.reply_text(f"Они слишком молоды для этого")
            else:
                await update.message.reply_text("Еблан, /pravila почитай")
        else:
            await update.message.reply_text("У тебя нету такого фурри")
    elif len(args) == 2:
        if args[0].lower() in data["users"][str(user_id)]["furries"]:
            fur = data["users"][str(user_id)]["furries"][args[0].lower()]
            action = args[1].lower()
            if action == "покормить":
                if data['users'][str(user_id)]['balance'] >= 250:
                    if fur["energy"] >= 20:
                        if fur["hunger"] == 100:
                            await update.message.reply_text(f"{args[0]} уже сыт")
                        else:
                            ran = randint(15, 25)
                            fur["hunger"] = min(100, fur["hunger"] + ran)
                            fur["energy"] = max(0, fur["energy"] - 20)
                            save_data()
                            update_balance(user_id, -250)
                            log_event(f"{user_data['username']} покормил фурри {args[0]}")
                            await update.message.reply_text(f"Ты потратил 250 херокоинов\n{args[0]}:\n+{ran} к сытости, -20 энергии")
                    else:
                        await update.message.reply_text(f"{args[0]} нуждается в отдыхе")
                else:
                    await update.message.reply_text("ты нищеброд")
            elif action == "помыть":
                if data['users'][str(user_id)]['balance'] >= 400:
                    if fur["energy"] >= 20:
                        if fur["cleanliness"] == 100:
                            await update.message.reply_text(f"{args[0]} уже чист")
                        else:
                            ran = randint(30, 40)
                            fur["cleanliness"] = min(100, fur["cleanliness"] + ran)
                            fur["energy"] = max(0, fur["energy"] - 20)
                            save_data()
                            update_balance(user_id, -400)
                            log_event(f"{user_data['username']} помыл фурри {args[0]}")
                            await update.message.reply_text(f"Ты потратил 400 херокоинов\n{args[0]}:\n+{ran} к чистоте, -20 энергии")
                    else:
                        await update.message.reply_text(f"{args[0]} нуждается в отдыхе")
                else:
                    await update.message.reply_text("ты нищеброд")
            elif action == "поиграть":
                if fur["energy"] >= 20:
                    if fur["happiness"] == 100:
                        await update.message.reply_text(f"{args[0]} уже счастлив :D")
                    else:
                        ran = randint(20, 30)
                        fur["happiness"] = min(100, fur["happiness"] + ran)
                        fur["energy"] = max(0, fur["energy"] - 20)
                        save_data()
                        log_event(f"{user_data['username']} поиграл с фурри {args[0]}")
                        await update.message.reply_text(f"Ты поиграл со своим {args[0]}\n+{ran} к счастью, -20 энергии")
                else:
                    await update.message.reply_text(f"{args[0]} нуждается в отдыхе")
            elif action == "вылечить":
                if data['users'][str(user_id)]['balance'] >= 2000:
                    if fur["health"] == 100:
                        await update.message.reply_text(f"{args[0]} здоров")
                    else:
                        fur["health"] = 100
                        save_data()
                        update_balance(user_id, -2000)
                        log_event(f"{user_data['username']} вылечил фурри {args[0]}")
                        await update.message.reply_text(f"Ты вылечил своего {args[0]} за 2 000 херокоинов\nЗдоровье:100\nЭнергия:0")
                else:
                    await update.message.reply_text("Ты нищеброд")
            elif action == "горничная":
                # снять горничную и проверка «уже есть горничная» — бесплатные
                if fur.get('is_maid', False):
                    fur['is_maid'] = False
                    save_data()
                    await update.message.reply_text(f"{args[0]} больше не горничная")
                elif any(f.get('is_maid', False) for f in user_data['furries'].values()):
                    await update.message.reply_text("У тебя уже есть горничная")
                elif user_data['balance'] < 1000000000:
                    await update.message.reply_text("Ты нищеброд")
                else:
                    fur['is_maid'] = True
                    save_data()
                    update_balance(user_id, -1000000000)
                    await update.message.reply_text(
                        f"Ты потратил 1 000 000 000 херокоинов\n"
                        f"{args[0]} теперь горничная"
                    )
        else:
            await update.message.reply_text("У тебя нету такого фурри")
    elif len(args) == 1:
        if args[0].lower() in data["users"][str(user_id)]["furries"]:
            fur = data["users"][str(user_id)]["furries"][args[0].lower()]
            now = datetime.now()
            age = now - datetime.strptime(fur["born"], DATE_FMT)

            lastrep = datetime.strptime(fur["lastrep"], DATE_FMT)
            wait_time1 = lastrep + timedelta(hours=24) - now
            available1 = wait_time1.total_seconds() <= 0

            if age.days < 5:
                available1 = False
                wait_time1 = lastrep + timedelta(days=5) - now

            time_str = format_wait(wait_time1)
            status = " *[ГОРНИЧНАЯ]*" if fur.get('is_maid', False) else ""

            caption = (
                f"{helpers.escape_markdown(args[0].lower(), version=1)}{status}\n\n"
                f"Редкость: {RARITY_NAMES[fur['rarity']]}\n\n"
                f"Сытость: {fur['hunger']}/100\n"
                f"Счастье: {fur['happiness']}/100\n"
                f"Чистота: {fur['cleanliness']}/100\n"
                f"Энергия: {fur['energy']}/100\n"
                f"Жизни: {fur['health']}/100\n\n"
                f"Возраст: {int(age.days)} дней\n"
                f"{'Спаривание доступно' if available1 else f'Спаривание доступно через: {time_str}'}"
            )
            # редкость 9 — гифка, остальные — фото, без файла — текст
            if fur['rarity'] == 9 and fur.get('path'):
                await update.message.reply_animation(animation=fur["path"], parse_mode="Markdown", caption=caption)
            elif fur.get('path'):
                await update.message.reply_photo(photo=fur["path"], parse_mode="Markdown", caption=caption)
            else:
                await update.message.reply_text(text=caption, parse_mode="Markdown")
        else:
            await update.message.reply_text("У тебя нету такого фурри")
    else:
        text = "Твои фурри:\n"
        now = datetime.now()
        for name, fur in data["users"][str(user_id)]["furries"].items():
            age = now - datetime.strptime(fur["born"], DATE_FMT)
            lastrep = datetime.strptime(fur["lastrep"], DATE_FMT)
            wait_time1 = lastrep + timedelta(hours=24) - now
            available1 = wait_time1.total_seconds() <= 0
            if age.days < 5:
                available1 = False

            status = " *[ГОРНИЧНАЯ]*" if fur.get('is_maid', False) else ""

            text += helpers.escape_markdown(name, version=1) + status + f"\n├─{RARITY_NAMES[fur['rarity']]}, {str(int(age.days))} дней, {'🔥' if available1 else ''}\n└─{fur['hunger']}🍖, {fur['happiness']}😇, {fur['cleanliness']}🧽, {fur['energy']}⚡️, {fur['health']}❤️\n"
        if text == "Твои фурри:\n":
            text = "У тебя нету фурри"
        else:
            text += f"всего фурри: {len(data['users'][str(user_id)]['furries'])}"
        await update.message.reply_text(text=text, parse_mode="Markdown")


async def post(update: Update, context: CallbackContext):
    args = context.args
    user_id = update.effective_user.id
    if args:
        if user_id == ADMIN_ID:
            await context.bot.send_message(chat_id=args[0], text=' '.join(args[1:]))


async def credit(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if not user_data:
        await update.message.reply_text("Ты не зарегистрирован, используй /register")
        return

    if len(context.args) == 0:
        credit = user_data.get('credit')
        if credit:
            await update.message.reply_text(
                f"Твой активный кредит:\n"
                f"Сумма: {form(credit['amount'])} херокоинов\n"
                f"Срок погашения: {credit['due_date']}"
            )
        else:
            await update.message.reply_text("У тебя нет активного кредита")
        return
    elif len(context.args) == 1:
        if context.args[0].lower() == "списать":
            credit = user_data.get('credit')
            if not credit:
                await update.message.reply_text("У тебя нет активного кредита")
                return

            amount = credit['amount']
            if user_data['balance'] < amount:
                await update.message.reply_text("Недостаточно средств для погашения")
                return

            new_balance = update_balance(user_id, -amount)
            remove_credit(user_id)

            await update.message.reply_text(
                f"Кредит погашен досрочно\n"
                f"Списано: {form(amount)} херокоинов\n"
                f"Новый баланс: {form(new_balance)}"
            )

    elif len(context.args) > 1:
        credit = user_data.get('credit')
        if credit:
            await update.message.reply_text("У тебя уже есть активный кредит")
            return
        try:
            amount = int(context.args[0])
            days = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Сумма и срок должны быть числами")
            return

        if user_data['balance'] < 0:
            await update.message.reply_text("Нельзя брать кредит с отрицательным балансом")
            return

        if days < 1 or days > 10:
            await update.message.reply_text("Срок кредита должен быть от 1 до 10 дней")
            return

        max_amount = user_data['balance'] * 100
        if amount < 1 or amount > max_amount:
            await update.message.reply_text(
                f"Сумма кредита должна быть от 1 до {form(max_amount)} херокоинов"
            )
            return

        due_date = (datetime.now() + timedelta(days=days)).strftime(DATE_FMT)

        update_balance(user_id, amount)
        set_credit(user_id, amount, due_date)

        await update.message.reply_text(
            f"Кредит на {form(amount)} херокоинов выдан\n"
            f"Срок погашения: {due_date}\n"
            f"Новый баланс: {form(user_data['balance'] + amount)}"
        )


async def kpass(update: Update, context: CallbackContext):
    if not await track_chats(update, context): return
    sender_id = update.effective_user.id
    message = update.effective_message
    args = context.args
    if sender_id != ADMIN_ID:
        await update.message.reply_text(
            "съебал атсюда"
        )
        return
    if not args:
        await update.message.reply_text(
            "еблан, /pravila читай"
        )
        return

    data = load_data()

    recipient_identifier = None
    recipient_id = None

    if len(args) > 1:
        recipient_identifier = args[1]
    elif message.reply_to_message:
        recipient_id = message.reply_to_message.from_user.id
    else:
        await update.message.reply_text("Укажи получателя: @username, ID или ответь на сообщение")
        return

    if recipient_identifier:
        if recipient_identifier.startswith('@'):
            username = recipient_identifier[1:]
            recipient_id = get_user_id_by_username(username)
            if not recipient_id:
                await update.message.reply_text("Пользователь не зарегистрирован")
                return
        elif recipient_identifier.isdigit():
            recipient_id = int(recipient_identifier)
        else:
            await update.message.reply_text("Укажите ID или @username получателя")
            return

    if str(recipient_id) not in data['users']:
        await update.message.reply_text("Пользователь не зарегистрирован")
        return

    if args[0] == "выдать":
        data['users'][str(recipient_id)]['pass'] = True
        save_data()
        await update.message.reply_text(
            f"казикпасс выдан\n"
        )
    elif args[0] == "отнять":
        data['users'][str(recipient_id)]['pass'] = False
        save_data()
        await update.message.reply_text(
            f"казикпасс отнят\n"
        )
