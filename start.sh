#!/bin/bash
# راه‌اندازی سامانه پایش خدمات روستایی
# این اسکریپت را در پوشه اصلی پروژه اجرا کنید

set -e
cd "$(dirname "$0")"

echo "================================"
echo "سامانه پایش خدمات روستایی"
echo "نسخه پایتون (Flask + SQLite)"
echo "================================"
echo ""

# بررسی نصب Flask
if ! python3 -c "import flask" 2>/dev/null; then
  echo "[نصب] Flask نصب نیست. در حال نصب..."
  pip install flask
fi

# بررسی نصب Werkzeug
if ! python3 -c "import werkzeug.security" 2>/dev/null; then
  echo "[نصب] Werkzeug..."
  pip install werkzeug
fi

# ساخت دیتابیس اگر وجود ندارد
if [ ! -f rural.db ]; then
  echo "[راه‌اندازی] ساخت پایگاه داده اولیه..."
  python3 -c "import db; db.init_db()"
fi

echo ""
echo "✓ راه‌اندازی کامل شد!"
echo ""
echo "آدرس سامانه: http://localhost:5050"
echo "نام کاربری: admin"
echo "رمز عبور: admin12345"
echo ""
echo "برای توقف: Ctrl+C"
echo "================================"
echo ""

# اجرای سرور
python3 app.py
