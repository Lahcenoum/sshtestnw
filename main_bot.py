# -*- coding: utf-8 -*-
import sqlite3
import re
from datetime import date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler, PreCheckoutQueryHandler
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

# نستورد الأدوات المشتركة من utils.py
from utils import (
    TOKEN, ADMIN_USER_ID, DB_FILE, REQUIRED_CHANNELS, POINTS_CONFIG, EXPIRY_CONFIG,
    get_text, get_user_lang, log_activity, create_and_send_ssh_account
)

# نستورد معالجات الدفع من payments.py
from payments import (
    show_payment_options, stars_payment_callback, precheckout_callback, successful_payment_callback
)

# =================================================================================
# 1. إعداد قاعدة البيانات والمستخدمين
# =================================================================================
def init_db():
    # ... (الكود الخاص بإنشاء الجداول كما هو في النسخة السابقة) ...
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS users (telegram_user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, last_daily_claim DATE, join_bonus_claimed INTEGER DEFAULT 0, language_code TEXT DEFAULT "ar", created_date DATE, referrer_id INTEGER)')
        cursor.execute('CREATE TABLE IF NOT EXISTS ssh_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_user_id INTEGER NOT NULL, ssh_username TEXT NOT NULL UNIQUE, ssh_password TEXT NOT NULL, created_at TIMESTAMP NOT NULL, expiry_date DATE)')
        cursor.execute('CREATE TABLE IF NOT EXISTS reward_channels (channel_id INTEGER PRIMARY KEY, channel_link TEXT NOT NULL, reward_points INTEGER NOT NULL, channel_name TEXT NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS user_channel_rewards (telegram_user_id INTEGER, channel_id INTEGER, PRIMARY KEY (telegram_user_id, channel_id))')
        cursor.execute('CREATE TABLE IF NOT EXISTS redeem_codes (code TEXT PRIMARY KEY, points INTEGER, max_uses INTEGER, current_uses INTEGER DEFAULT 0)')
        cursor.execute('CREATE TABLE IF NOT EXISTS redeemed_users (code TEXT, telegram_user_id INTEGER, PRIMARY KEY (code, telegram_user_id))')
        cursor.execute('CREATE TABLE IF NOT EXISTS daily_activity (user_id INTEGER PRIMARY KEY, last_seen_date DATE NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS connection_settings (key TEXT PRIMARY KEY, value TEXT)')
        default_settings = CONFIG.get("default_connection_settings", {})
        for key, value in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO connection_settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()


async def get_or_create_user(user_id, lang_code='ar', referrer_id=None, context: ContextTypes.DEFAULT_TYPE = None):
    # ... (الكود الخاص بإنشاء المستخدم كما هو في النسخة السابقة) ...
     with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE telegram_user_id = ?", (user_id,))
        is_new_user = cursor.fetchone() is None
        if is_new_user:
            today = date.today().isoformat()
            cursor.execute("INSERT INTO users (telegram_user_id, points, language_code, created_date, referrer_id) VALUES (?, ?, ?, ?, ?)", (user_id, POINTS_CONFIG.get('initial', 2), lang_code, today, referrer_id))
            conn.commit()
            if referrer_id and context:
                try:
                    cursor.execute("UPDATE users SET points = points + ? WHERE telegram_user_id = ?", (POINTS_CONFIG.get('referral_bonus', 2), referrer_id))
                    conn.commit()
                    referrer_lang = get_user_lang(referrer_id)
                    await context.bot.send_message(chat_id=referrer_id, text=get_text('referral_bonus_notification', referrer_lang, bonus=POINTS_CONFIG.get('referral_bonus', 2)), parse_mode=ParseMode.HTML)
                except Exception as e:
                    print(f"خطأ في منح مكافأة الإحالة: {e}")

async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # ... (الكود الخاص بالتحقق من الانضمام كما هو في النسخة السابقة) ...
    channel_id = REQUIRED_CHANNELS.get('channel_id')
    group_id = REQUIRED_CHANNELS.get('group_id')
    if not channel_id or not group_id: return True
    try:
        channel_member = await context.bot.get_chat_member(channel_id, user_id)
        group_member = await context.bot.get_chat_member(group_id, user_id)
        valid_statuses = ['member', 'administrator', 'creator']
        if channel_member.status not in valid_statuses: return False
        if group_member.status not in valid_statuses: return False
        return True
    except BadRequest as e:
        if "user not found" in e.message: return False
        print(f"خطأ في التحقق من الانضمام: {e}")
        return False
    except Exception as e:
        print(f"خطأ غير متوقع في التحقق: {e}")
        return False

# =================================================================================
# 2. معالجات الأوامر الرئيسية
# =================================================================================
@log_activity
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
    user = update.effective_user
    message = update.message if not from_callback else update.callback_query.message
    
    user_lang = user.language_code if user.language_code in ['ar', 'en'] else 'ar'
    referrer_id = int(context.args[0].split('_')[1]) if context.args and context.args[0].startswith('ref_') and context.args[0].split('_')[1].isdigit() and int(context.args[0].split('_')[1]) != user.id else None

    await get_or_create_user(user.id, lang_code=user_lang, referrer_id=referrer_id, context=context)
    lang_code = get_user_lang(user.id)

    if not await check_membership(user.id, context):
        keyboard = [[InlineKeyboardButton(get_text('force_join_channel_button', lang_code), url=REQUIRED_CHANNELS.get('channel_link'))], [InlineKeyboardButton(get_text('force_join_group_button', lang_code), url=REQUIRED_CHANNELS.get('group_link'))], [InlineKeyboardButton(get_text('force_join_verify_button', lang_code), callback_data='verify_join')]]
        await message.reply_text(get_text('force_join_prompt', lang_code), reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard_layout = [[KeyboardButton(get_text('get_account_button', lang_code)), KeyboardButton(get_text('paid_servers_button', lang_code))], [KeyboardButton(get_text('balance_button', lang_code)), KeyboardButton(get_text('my_account_button', lang_code))], [KeyboardButton(get_text('daily_button', lang_code)), KeyboardButton(get_text('earn_points_button', lang_code))], [KeyboardButton(get_text('redeem_code_button', lang_code)), KeyboardButton(get_text('contact_admin_button', lang_code))]]
    await message.reply_text(get_text('welcome', lang_code), reply_markup=ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True))

# ... (باقي الأوامر مثل my_accounts, balance_command, daily_command موجودة هنا كما في النسخة السابقة) ...
# For brevity, these functions are omitted but should be copied from the previous version.


# =================================================================================
# 3. معالجات ردود الأفعال (Callbacks)
# =================================================================================
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang_code = get_user_lang(user_id)
    data = query.data

    if data == 'create_ssh':
        await query.edit_message_text(text=get_text('creating_account', lang_code))
        with sqlite3.connect(DB_FILE) as conn:
            cost = POINTS_CONFIG.get('cost_per_account', 2)
            conn.execute("UPDATE users SET points = points - ? WHERE telegram_user_id = ?", (cost, user_id))
            conn.commit()
            
        account_info = await create_and_send_ssh_account(user_id, lang_code, EXPIRY_CONFIG.get('free', 2))
        await query.edit_message_text(account_info, parse_mode=ParseMode.HTML)
    
    elif data == 'verify_join':
        if await check_membership(user_id, context):
            await query.edit_message_text(get_text('force_join_success', lang_code))
            await start(update, context, from_callback=True)
        else:
            await query.answer(get_text('force_join_fail', lang_code), show_alert=True)

# =================================================================================
# 4. نقطة انطلاق البوت
# =================================================================================
def main():
    init_db()
    
    if "YOUR_TELEGRAM_BOT_TOKEN" in TOKEN:
        print("خطأ فادح: لم يتم تعيين توكن البوت في ملف 'config.json'.")
        sys.exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    
    def create_lang_regex(key):
        return f"^({'|'.join([re.escape(get_text(key, lang)) for lang in ['ar', 'en']])})$"

    app.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    
    # أوامر الأزرار الرئيسية
    app.add_handler(MessageHandler(filters.Regex(create_lang_regex('paid_servers_button')) & filters.ChatType.PRIVATE, show_payment_options))
    # ... (Add other message handlers for my_accounts, balance, etc.)
    
    # معالجات ردود الأفعال
    app.add_handler(CallbackQueryHandler(button_callback_handler, pattern='^(create_ssh|verify_join)$'))
    app.add_handler(CallbackQueryHandler(stars_payment_callback, pattern='^pay_stars$'))

    # معالجات الدفع (يتم استيرادها)
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT & filters.ChatType.PRIVATE, successful_payment_callback))
    
    print("...البوت قيد التشغيل")
    app.run_polling()

if __name__ == '__main__':
    main()
