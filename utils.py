import random

DATE_FMT = '%Y-%m-%d %H:%M:%S'

RARITY_NAMES = {
    0: "РЕДКИЙ",
    1: "СВЕРХРЕДКИЙ",
    2: "ЭПИЧЕСКИЙ",
    3: "МИФИЧЕСКИЙ",
    4: "ЛЕГЕНДАРНЫЙ",
    5: "НЕВОЗМОЖНЫЙ",
    6: "ЛУДОМАНСКИЙ",
    7: "ЕБЛАНСКИЙ",
    8: "ХЕРОБРИНСКИЙ",
    9: "∞"
}

RARITY_FOLDERS = {
    0: "furrybase/редкий/",
    1: "furrybase/сверхредкий/",
    2: "furrybase/эпический/",
    3: "furrybase/мифический/",
    4: "furrybase/легендарный/",
    5: "furrybase/невозможный/",
    6: "furrybase/лудоманский/",
    7: "furrybase/ебланский/",
    8: "furrybase/херобринский/",
    9: "furrybase/∞/"
}

# (максимальный ролл, редкость) — всё, что выше последнего порога, даёт деньги
RARITY_ODDS = (
    (1, 9), (10, 8), (100, 7), (500, 6), (1000, 5),
    (5000, 4), (10000, 3), (25000, 2), (50000, 1), (100000, 0),
)


def roll_rarity(item):
    for threshold, rar in RARITY_ODDS:
        if item <= threshold:
            return rar
    return None


def furry_price(rarity, age_days):
    """Цена фурри: 5^(редкость+1) * 10000 * (дни + 1). age_days=0 — цена без учёта возраста."""
    return (5 ** (rarity + 1)) * 10000 * (age_days + 1)


RARITY_BONUSES = {
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


def payout_bonus(user):
    """База x2 + бонусы за фурри + 0.2 за пасс. Для числа/зелёного умножается на 20 (x40)."""
    total = 2.0
    if user.get('pass'):
        total += 0.2
    for furry in user.get('furries', {}).values():
        total += RARITY_BONUSES.get(furry['rarity'], 0)
    return total


def spin_roulette():
    return random.randint(0, 36)


def get_color(number):
    if number == 0:
        return 'зеленый'
    reds = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    return 'красный' if number in reds else 'черный'


def get_parity(number):
    if number == 0:
        return 'ноль'
    return 'чет' if number % 2 == 0 else 'нечет'


def form(n):
    return f"{n:,}".replace(",", " ")


def format_wait(td):
    """'1д 3ч 5мин' из timedelta."""
    total = max(0, int(td.total_seconds()))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    parts.append(f"{minutes}мин")
    return " ".join(parts)
