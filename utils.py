# -*- coding: utf-8 -*-
import json
import sys
import sqlite3
import html
import random
import string
import subprocess
import traceback
from datetime import datetime, date, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

# =================================================================================
# 1. تحميل الإعدادات واللغات (Configuration & Localization Loader)
# =================================================================================
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        CONFIG = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("خطأ فادح: تأكد من وجود ملف 'config.json' وأنه مكتوب بشكل صحيح.")
    sys.exit(1)

TOKEN = CONFIG['telegram_bot_token']
ADMIN_USER_ID = CONFIG['admin_user_id']
DB_FILE = CONFIG['database_file']
SSH_SCRIPT_PATH = CONFIG['ssh_script_path']
POINTS_CONFIG = CONFIG.get('points_system', {})
EXPIRY_CONFIG = CONFIG.get('expiry_days', {})

def load_texts():
    texts = {}
    for lang_file in Path('.').glob('*.json'):
        if lang_file.stem in ['ar', 'en']:
            with open(lang_file, 'r', encoding='utf-8') as f:
                texts[lang_file.stem] = json.load(f)
    return texts

TEXTS = load_texts()

def get_text(key, lang_code='ar', **kwargs):
    lang_code = lang_code if lang_code in TEXTS else 'ar'
    text = TEXTS.get(lang_code, {}).get(key, TEXTS.get('ar', {}).get(key, key))
    return text.format(**kwargs) if kwargs else text

# =================================================================================
# 2. دوال مساعدة لقاعدة البيانات (Database Helpers)
# =================================================================================
def get_user_lang(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT language_code FROM users WHERE telegram_user_id = ?", (user_id,)).fetchone()
        return res[0] if res else 'ar'

def get_connection_setting(key):
    with sqlite3.connect(DB_FILE) as conn:
        result = conn.execute("SELECT value FROM connection_settings WHERE key = ?", (key,)).fetchone()
        return result[0] if result else ""

# =================================================================================
# 3. Decorators & Core Logic Helpers
# =================================================================================
def log_activity(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user:
            user_id = update.effective_user.id
            today = date.today().isoformat()
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("INSERT OR REPLACE INTO daily_activity (user_id, last_seen_date) VALUES (?, ?)", (user_id, today))
                conn.commit()
        return await func(update, context, *args, **kwargs)
    return wrapper

async def create_and_send_ssh_account(user_id: int, lang_code: str, expiry_days: int, is_paid: bool = False):
    try:
        prefix = "paid" if is_paid else "free"
        random_part = random.randint(100, 999) if is_paid else user_id
        username = f"{prefix}{random_part}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10 if is_paid else 8))

        command_to_run = ["sudo", SSH_SCRIPT_PATH, username, password, str(expiry_days)]
        subprocess.run(command_to_run, capture_output=True, text=True, timeout=30, check=True)

        expiry_date = (date.today() + timedelta(days=expiry_days)).isoformat()
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "INSERT INTO ssh_accounts (telegram_user_id, ssh_username, ssh_password, created_at, expiry_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, password, datetime.now(), expiry_date)
            )
            conn.commit()

        return get_text(
            'account_details_full', lang_code,
            username=html.escape(username),
            password=html.escape(password),
            expiry=html.escape(expiry_date),
            hostname=html.escape(get_connection_setting("hostname")),
            ws_ports=html.escape(get_connection_setting("ws_ports")),
            ssl_port=html.escape(get_connection_setting("ssl_port")),
            udpcustom_port=html.escape(get_connection_setting("udpcustom_port")),
            payload=html.escape(get_connection_setting("payload"))
        )
    except subprocess.CalledProcessError as e:
        print(f"فشل سكربت SSH: {e.stderr}")
        return get_text('creation_error_user_exists', lang_code)
    except Exception:
        traceback.print_exc()
        return get_text('creation_error_generic', lang_code)
