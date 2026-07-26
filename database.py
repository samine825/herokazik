import json
import os
from datetime import datetime
from pathlib import Path
from config import DATA_FILE

def load_data():
    if not DATA_FILE.exists():
        return {'users': {}, 'chats': []}
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(user_id: int):
    data = load_data()
    return data['users'].get(str(user_id))


def create_user(user_id: int, username: str):
    data = load_data()
    user_data = {
        'username': username,
        'balance': 0,
        'furries': {},
        'minetov': 0,
        'last_daily': None,
        'last_ultra_daily': None,
        'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'credit': None,
        'pass':None
    }
    data['users'][str(user_id)] = user_data
    save_data(data)
    return user_data




def update_balance(user_id: int, amount: int):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str in data['users']:
        data['users'][user_id_str]['balance'] += int(amount)
        save_data(data)
        return data['users'][user_id_str]['balance']
    return None



def add_chat(chat_id: int):
    data = load_data()
    if chat_id not in data['chats']:
        data['chats'].append(chat_id)
        save_data(data)

def get_user_id_by_username(username: str):
    data = load_data()
    username = username.lower()
    for user_id, user_data in data["users"].items():
        if user_data["username"].lower() == username:
            return int(user_id)
    return None

def save_reserv(data,path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def set_credit(user_id: int, amount: int, due_date: str):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str in data['users']:
        data['users'][user_id_str]['credit'] = {
            'amount': amount,
            'due_date': due_date
        }
        save_data(data)

def remove_credit(user_id: int):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str in data['users'] and 'credit' in data['users'][user_id_str]:
        del data['users'][user_id_str]['credit']
        save_data(data)

def get_credit(user_id: int):
    data = load_data()
    user_id_str = str(user_id)
    return data['users'][user_id_str].get('credit')
