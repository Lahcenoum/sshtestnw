# -*- coding: utf-8 -*-
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.ext import ContextTypes

# نستورد الأدوات المشتركة من ملف utils.py
from utils import (
    get_text, get_user_lang, log_activity, create_and_send_ssh_account,
    CONFIG, EXPIRY_CONFIG
)

# =================================================================================
# معالجات أوامر وميزات الدفع
# =================================================================================

@log_activity
async def show_payment_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض للمستخدم خيارات الدفع المتاحة.
    """
    lang_code = get_user_lang(update.effective_user.id)
    keyboard = [
        [InlineKeyboardButton(get_text('telegram_stars_button', lang_code), callback_data='pay_stars')],
        # [InlineKeyboardButton(get_text('paypal_button', lang_code), callback_data='pay_paypal')],
        # [InlineKeyboardButton(get_text('moroccan_bank_button', lang_code), callback_data='pay_bank_transfer')],
    ]
    await update.message.reply_text(get_text('choose_payment_method', lang_code), reply_markup=InlineKeyboardMarkup(keyboard))

async def stars_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يبدأ عملية الدفع باستخدام نجوم تليجرام.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang_code = get_user_lang(user_id)
    
    payload = f"PAID_SSH_STARS_{user_id}_{uuid.uuid4().hex[:8]}"
    
    try:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=get_text('payment_invoice_title', lang_code),
            description=get_text('payment_invoice_description', lang_code),
            payload=payload,
            provider_token=None,
            currency="XTR",
            prices=[LabeledPrice(label=get_text('payment_invoice_label', lang_code), amount=CONFIG.get('telegram_stars_price', 1050))]
        )
    except Exception as e:
        print(f"خطأ في إرسال فاتورة النجوم: {e}")
        await context.bot.send_message(query.message.chat_id, get_text('payment_not_configured', lang_code))

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يستجيب لطلب تليجرام للتحقق من جاهزية الدفع.
    """
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يتم استدعاؤه بعد إتمام المستخدم لعملية الدفع بنجاح.
    """
    user_id = update.effective_user.id
    lang_code = get_user_lang(user_id)

    # إنشاء حساب مدفوع وإرساله للمستخدم
    account_info = await create_and_send_ssh_account(
        user_id=user_id,
        lang_code=lang_code,
        expiry_days=EXPIRY_CONFIG.get('paid', 30),
        is_paid=True
    )
    
    await update.message.reply_text(
        f"{get_text('payment_successful_creation', lang_code)}\n\n{account_info}",
        parse_mode='HTML'
    )
