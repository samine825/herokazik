import json
import os
import re
from datetime import datetime
from pathlib import Path

from config import DATA_FILE
from utils import DATE_FMT

BACKUPS_TO_KEEP = 24


class Database:
    """Хранилище в памяти: данные грузятся один раз при старте,
    каждое изменение атомарно пишется на диск.

    Все функции работают с одним живым словарём db.data —
    устаревших снапшотов и гонок «прочитал-изменил-перезаписал» больше нет.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.data = {'users': {}, 'chats': []}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                return
            except (json.JSONDecodeError, OSError):
                # основной файл бит — пробуем восстановиться из последнего бэкапа
                backup = self._latest_backup_path()
                if backup:
                    try:
                        with open(backup, 'r', encoding='utf-8') as f:
                            self.data = json.load(f)
                        return
                    except (json.JSONDecodeError, OSError):
                        pass
        self.data = {'users': {}, 'chats': []}

    def save(self):
        """Атомарная запись: сначала во временный файл, потом замена."""
        tmp = self.path.with_name(self.path.name + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def backup(self):
        """Ежечасная копия в reserved/ с ротацией (хранятся последние BACKUPS_TO_KEEP)."""
        reserved = Path('reserved')
        reserved.mkdir(exist_ok=True)

        nums = []
        for name in os.listdir(reserved):
            match = re.fullmatch(r'casino_data(\d+)\.json', name)
            if match:
                nums.append(int(match.group(1)))

        target = reserved / f'casino_data{max(nums, default=0) + 1}.json'
        tmp = target.with_name(target.name + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, target)

        files = sorted(reserved.glob('casino_data*.json'), key=self._backup_num)
        for old in files[:-BACKUPS_TO_KEEP]:
            old.unlink()

    @staticmethod
    def _backup_num(path):
        match = re.search(r'casino_data(\d+)\.json', path.name)
        return int(match.group(1)) if match else 0

    def _latest_backup_path(self):
        reserved = Path('reserved')
        if not reserved.exists():
            return None
        files = sorted(reserved.glob('casino_data*.json'), key=self._backup_num)
        return files[-1] if files else None


db = Database(DATA_FILE)


def load_data():
    return db.data


def save_data(data=None):
    db.save()


def get_user(user_id: int):
    return db.data['users'].get(str(user_id))


def create_user(user_id: int, username: str):
    user_data = {
        'username': username,
        'balance': 0,
        'furries': {},
        'minetov': 0,
        'last_daily': None,
        'last_ultra_daily': None,
        'registered_at': datetime.now().strftime(DATE_FMT),
        'credit': None,
        'pass': None,
        'herobox_notified': False,
        'ultraherobox_notified': False,
    }
    db.data['users'][str(user_id)] = user_data
    db.save()
    return user_data


def update_balance(user_id: int, amount: int):
    user = db.data['users'].get(str(user_id))
    if user:
        user['balance'] += int(amount)
        db.save()
        return user['balance']
    return None


def add_chat(chat_id: int):
    # сохраняем на диск только когда появился новый чат, а не на каждое сообщение
    if chat_id not in db.data['chats']:
        db.data['chats'].append(chat_id)
        db.save()


def get_user_id_by_username(username: str):
    username = username.lower()
    for user_id, user_data in db.data['users'].items():
        if user_data["username"].lower() == username:
            return int(user_id)
    return None


def set_credit(user_id: int, amount: int, due_date: str):
    user = db.data['users'].get(str(user_id))
    if user:
        user['credit'] = {'amount': amount, 'due_date': due_date}
        db.save()


def remove_credit(user_id: int):
    user = db.data['users'].get(str(user_id))
    if user and 'credit' in user:
        del user['credit']
        db.save()


def get_credit(user_id: int):
    user = db.data['users'].get(str(user_id))
    return user.get('credit') if user else None
