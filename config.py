import os
from pathlib import Path

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DATA_FILE = Path('casino_data.json')
