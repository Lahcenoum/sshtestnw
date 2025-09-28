#!/bin/bash
# Final Version: Focuses on the modular bot structure (using config.json)
# and integrates automatic DB backups to Telegram.

# ========================================================================
#   سكريبت التثبيت للبوت بالهيكلية الجديدة (يعتمد على config.json)
# ========================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

# --- إعدادات أساسية ---
GIT_REPO_URL="https://github.com/Lahcenoum/sshtestbot.git" # <--- غيّر هذا الرابط إذا كان المستودع مختلفًا
PROJECT_DIR="/home/ssh_bot"
SSH_CONNECTION_LIMIT=2

# --- نهاية قسم الإعدادات ---

# --- دوال الألوان ---
red() { echo -e "\e[31m$*\e[0m"; }
green() { echo -e "\e[32m$*\e[0m"; }
yellow() { echo -e "\e[33m$*\e[0m"; }

# التحقق من صلاحيات الجذر
if [ "$(id -u)" -ne 0 ]; then
    red "❌ يجب تشغيل السكربت بصلاحيات root."
    exit 1
fi

echo "=================================================="
echo "    🔧 بدء تثبيت البوت بالهيكلية الجديدة"
echo "=================================================="

# --- القسم الأول: تثبيت المتطلبات الأساسية ---

# الخطوة 0: حذف أي تثبيت قديم
echo -e "\n[0/9] 🗑️ حذف أي تثبيت قديم..."
systemctl stop ssh_bot.service >/dev/null 2>&1 || true
systemctl disable ssh_bot.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/ssh_bot.service
rm -rf "$PROJECT_DIR"

# 1. تحديث النظام وتثبيت المتطلبات
echo -e "\n[1/9] 📦 تحديث النظام وتثبيت المتطلبات..."
apt-get update
apt-get install -y git python3-venv python3-pip sudo curl cron jq

# 2. استنساخ المشروع
echo -e "\n[2/9] 📥 استنساخ المشروع من GitHub..."
git clone "$GIT_REPO_URL" "$PROJECT_DIR"
cd "$PROJECT_DIR" || exit 1

# --- القسم الثاني: إعداد ملف config.json ---

echo -e "\n[3/9] 📝 إعداد ملف 'config.json'..."

read -p "  - أدخل توكن البوت (Bot Token): " BOT_TOKEN
read -p "  - أدخل معرف الأدمن الرقمي (Admin User ID): " ADMIN_USER_ID
read -p "  - أدخل عنوان IP أو نطاق السيرفر (Server IP/Domain): " SERVER_IP

# إنشاء ملف config.json باستخدام cat و EOL
cat > "$PROJECT_DIR/config.json" << EOL
{
  "telegram_bot_token": "${BOT_TOKEN}",
  "admin_user_id": ${ADMIN_USER_ID},
  "database_file": "ssh_bot_users.db",
  "ssh_script_path": "/usr/local/bin/create_ssh_user.sh",
  "telegram_stars_price": 1050,
  
  "paypal_settings": {
    "enabled": false,
    "mode": "sandbox",
    "client_id": "YOUR_PAYPAL_CLIENT_ID",
    "client_secret": "YOUR_PAYPAL_CLIENT_SECRET",
    "price": "2.40",
    "currency": "USD"
  },

  "required_channels": {
    "channel_id": -1001932589296,
    "group_id": -1002218671728,
    "channel_link": "https://t.me/CLOUDVIP",
    "group_link": "https://t.me/dgtliA"
  },
  
  "points_system": {
    "cost_per_account": 2,
    "daily_login_bonus": 1,
    "initial": 2,
    "join_bonus": 0,
    "referral_bonus": 2
  },

  "expiry_days": {
    "free": 1,
    "paid": 30
  },

  "default_connection_settings": {
    "hostname": "${SERVER_IP}",
    "ws_ports": "80, 8880, 8888, 2053",
    "ssl_port": "443",
    "udpcustom_port": "7300",
    "admin_contact": "@YourAdminUsername",
    "payload": "GET / HTTP/1.1[crlf]Host: ${SERVER_IP}[crlf]Upgrade: websocket[crlf][crlf]"
  }
}
EOL

green "  - ✅ تم إنشاء وتعبئة ملف 'config.json' بنجاح."

# --- القسم الثالث: إعداد السكربتات والخدمات ---

# 4. إعداد سكربتات SSH
echo -e "\n[4/9] 👤 إعداد سكربتات SSH..."
if [ -f "create_ssh_user.sh" ]; then
    mv "create_ssh_user.sh" "/usr/local/bin/"
    chmod +x "/usr/local/bin/create_ssh_user.sh"
    green "  - ✅ تم إعداد سكربت إنشاء المستخدمين."
else
    yellow "  - ⚠️ تحذير: لم يتم العثور على 'create_ssh_user.sh'."
fi

# ... (يمكن إضافة سكربتات الحذف والمراقبة هنا بنفس الطريقة إذا كانت موجودة في المستودع) ...

# 5. إعداد النسخ الاحتياطي التلقائي
echo -e "\n[5/9] 🗄️ إعداد النسخ الاحتياطي التلقائي..."
read -p "  - أدخل معرف القناة (Channel ID) لإرسال النسخ الاحتياطية إليها (يبدأ بـ -100): " CHANNEL_ID
if [[ ! "$CHANNEL_ID" =~ ^-100[0-9]+$ ]]; then red "❌ المعرف غير صالح." exit 1; fi

cat > /usr/local/bin/backup_bot.sh << EOL
#!/bin/bash
BOT_TOKEN="${BOT_TOKEN}"
CHANNEL_ID="${CHANNEL_ID}"
DB_PATH="${PROJECT_DIR}/ssh_bot_users.db"
CAPTION="نسخة احتياطية جديدة لقاعدة البيانات - \$(date)"

if [ ! -f "\$DB_PATH" ]; then exit 1; fi

BACKUP_FILE="/tmp/db_backup_\$(date +%F_%H-%M-%S).db"
cp "\$DB_PATH" "\$BACKUP_FILE"

curl -s -F "chat_id=\${CHANNEL_ID}" -F "document=@\${BACKUP_FILE}" -F "caption=\${CAPTION}" "https://api.telegram.org/bot\${BOT_TOKEN}/sendDocument" > /dev/null

rm "\$BACKUP_FILE"
EOL

chmod +x /usr/local/bin/backup_bot.sh
# إضافة مهمة cron للعمل كل 6 ساعات
{ crontab -l 2>/dev/null | grep -v -F "/usr/local/bin/backup_bot.sh"; echo "0 */6 * * * /usr/local/bin/backup_bot.sh"; } | crontab -
green "  - ✅ تم إعداد مهمة النسخ الاحتياطي كل 6 ساعات."

# 6. إعداد بيئة بايثون
echo -e "\n[6/9] 🐍 إعداد البيئة الافتراضية وتثبيت المكتبات..."
python3 -m venv venv
(
    source venv/bin/activate
    pip install --upgrade pip
    # تحقق من وجود ملف requirements.txt
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        # تثبيت المكتبات الأساسية إذا لم يوجد الملف
        pip install python-telegram-bot paypalrestsdk
    fi
    green "  - ✅ تم تثبيت المكتبات بنجاح."
)

# 7. إعداد وتشغيل الخدمة
echo -e "\n[7/9] 🚀 إعداد وتشغيل الخدمة..."
cat > /etc/systemd/system/ssh_bot.service << EOL
[Unit]
Description=Telegram SSH Bot Service (Modular)
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/main_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL
green "  - ✅ تم إنشاء ملف الخدمة."

# 8. تشغيل الخدمات
echo -e "\n[8/9] ⚙️ تفعيل وإعادة تشغيل الخدمات..."
systemctl daemon-reload
systemctl enable ssh_bot.service >/dev/null 2>&1
systemctl restart ssh_bot.service

# 9. نهاية التثبيت
echo -e "\n[9/9] 🎉 تم التثبيت بنجاح!"
echo "=================================================="
green "🎉 اكتمل التثبيت بنجاح!"
echo "--------------------------------------------------"
echo "  - 🤖 لمراقبة حالة البوت:"
echo "    systemctl status ssh_bot.service"
echo "  - 📜 لعرض سجلات البوت:"
echo "    journalctl -u ssh_bot.service -f"
echo "=================================================="
