
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs/")

def ensure_log_dir_exists():
    if not LOG_DIR.exists():
        os.makedirs(LOG_DIR)

def get_current_log_file():
    ensure_log_dir_exists()
    today = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"{today}.log"

def log_event(event: str):
    log_file = get_current_log_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {event}\n"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)