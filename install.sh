#!/bin/bash
# Simplified Interactive Installer: Asks only for essential, variable info.
# Static info like channel IDs are pre-configured.

# ========================================================================
#   سكريبت التثبيت المبسط (يطلب التوكن والدومين فقط)
# ========================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

# --- إعدادات أساسية ---
GIT_REPO_URL="https://github.com/Lahcenoum/sshtestnw.git" # <--- رابط المستودع الخاص بك
PROJECT_DIR="/home/ssh_bot"

# --- معلومات ثابتة للمشروع (تعدل هنا إذا لزم الأمر) ---
ADMIN_USER_ID="5344028088"
ADMIN_CONTACT="@YourAdminUsername"
REQ_CHANNEL_LINK="https://t.me/CLOUDVIP"
REQ_CHANNEL_ID="-1001932589296"
REQ_GROUP_LINK="https://t.me/dgtliA"
REQ_GROUP_ID="-1002218671728"

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
echo "      🔧 بدء تثبيت البوت (الإعداد المبسط)"
echo "=================================================="

# --- القسم الأول: جمع المعلومات الأساسية ---

echo -e "\n[+] يرجى إدخال المعلومات الأساسية التالية:\n"

read -p "  - أدخل توكن البوت (Bot Token): " BOT_TOKEN
read -p "  - أدخل عنوان IP أو نطاق السيرفر (Server IP/Domain): " SERVER_IP
read -p "  - أدخل معرف قناة النسخ الاحتياطي (Backup Channel ID): " BACKUP_CHANNEL_ID

# التحقق من أن المدخلات ليست فارغة
if [ -z "$BOT_TOKEN" ] || [ -z "$SERVER_IP" ] || [ -z "$BACKUP_CHANNEL_ID" ]; then
    red "❌ جميع الحقول إلزامية. يرجى إعادة تشغيل السكربت."
    exit 1
fi

echo
green "[✔] تم جمع المعلومات بنجاح. بدء التثبيت..."
sleep 2


# --- القسم الثاني: التثبيت الفعلي ---

# الخطوة 1: حذف أي تثبيت قديم
echo -e "\n[1/7] 🗑️ حذف أي تثبيت قديم..."
systemctl stop ssh_bot.service >/dev/null 2>&1 || true
systemctl disable ssh_bot.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/ssh_bot.service
rm -rf "$PROJECT_DIR"

# الخطوة 2: تحديث وتثبيت المتطلبات
echo -e "\n[2/7] 📦 تحديث النظام وتثبيت المتطلبات..."
apt-get update >/dev/null 2>&1
apt-get install -y git python3-venv python3-pip sudo curl cron >/dev/null 2>&1

# الخطوة 3: استنساخ المشروع وإعداد الملفات
echo -e "\n[3/7] 📥 استنساخ المشروع وإعداد الملفات..."
git clone "$GIT_REPO_URL" "$PROJECT_DIR"
cd "$PROJECT_DIR" || exit 1

# إنشاء ملف config.json باستخدام المعلومات التي تم جمعها والمعلومات الثابتة
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
    "channel_id": ${REQ_CHANNEL_ID},
    "group_id": ${REQ_GROUP_ID},
    "channel_link": "${REQ_CHANNEL_LINK}",
    "group_link": "${REQ_GROUP_LINK}"
  },
  "points_system": { "cost_per_account": 2, "daily_login_bonus": 1, "initial": 2, "join_bonus": 0, "referral_bonus": 2 },
  "expiry_days": { "free": 1, "paid": 30 },
  "default_connection_settings": {
    "hostname": "${SERVER_IP}",
    "ws_ports": "80, 8880, 8888, 2053",
    "ssl_port": "443",
    "udpcustom_port": "7300",
    "admin_contact": "${ADMIN_CONTACT}",
    "payload": "GET / HTTP/1.1[crlf]Host: ${SERVER_IP}[crlf]Upgrade: websocket[crlf][crlf]"
  }
}
EOL
green "  - ✅ تم إنشاء 'config.json' بنجاح."

# نقل سكربتات SSH
if [ -f "create_ssh_user.sh" ]; then
    mv "create_ssh_user.sh" "/usr/local/bin/"
    chmod +x "/usr/local/bin/create_ssh_user.sh"
fi

# الخطوة 4: إعداد النسخ الاحتياطي
echo -e "\n[4/7] 🗄️ إعداد النسخ الاحتياطي التلقائي..."
cat > /usr/local/bin/backup_bot.sh << EOL
#!/bin/bash
DB_PATH="${PROJECT_DIR}/ssh_bot_users.db"
CAPTION="نسخة احتياطية لقاعدة البيانات - \$(date)"
if [ ! -f "\$DB_PATH" ]; then exit 1; fi
BACKUP_FILE="/tmp/db_backup_\$(date +%F_%H-%M-%S).db"
cp "\$DB_PATH" "\$BACKUP_FILE"
curl -s -F "chat_id=${BACKUP_CHANNEL_ID}" -F "document=@\${BACKUP_FILE}" -F "caption=\${CAPTION}" "https://api.telegram.org/bot${BOT_TOKEN}/sendDocument" > /dev/null
rm "\$BACKUP_FILE"
EOL

chmod +x /usr/local/bin/backup_bot.sh
{ crontab -l 2>/dev/null | grep -v -F "/usr/local/bin/backup_bot.sh"; echo "0 */6 * * * /usr/local/bin/backup_bot.sh"; } | crontab -
green "  - ✅ تم إعداد مهمة النسخ الاحتياطي كل 6 ساعات."

# الخطوة 5: إعداد بيئة بايثون
echo -e "\n[5/7] 🐍 إعداد البيئة الافتراضية وتثبيت المكتبات..."
python3 -m venv venv
(
    source venv/bin/activate
    pip install --upgrade pip >/dev/null 2>&1
    if [ -f "requirements.txt" ]; then pip install -r requirements.txt; else pip install python-telegram-bot paypalrestsdk; fi
)
green "  - ✅ تم تثبيت المكتبات بنجاح."

# الخطوة 6: إعداد وتشغيل الخدمة
echo -e "\n[6/7] 🚀 إعداد وتشغيل الخدمة..."
cat > /etc/systemd/system/ssh_bot.service << EOL
[Unit]
Description=Telegram SSH Bot Service
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

systemctl daemon-reload
systemctl enable ssh_bot.service >/dev/null 2>&1
systemctl restart ssh_bot.service

# الخطوة 7: نهاية التثبيت
echo -e "\n[7/7] 🎉 تم التثبيت بنجاح!"
echo "=================================================="
green "🎉 اكتمل التثبيت بنجاح!"
echo "--------------------------------------------------"
echo "  - 🤖 لمراقبة حالة البوت:"
echo "    systemctl status ssh_bot.service"
echo "  - 📜 لعرض سجلات البوت:"
echo "    journalctl -u ssh_bot.service -f"
echo "=================================================="
