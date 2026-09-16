# Virtual Try-On لیپستیک

## ساختار ماژولار

```
src/
├── database/
│   ├── schema.sql              ← اسکیمای کامل (روی دیتابیس تازه اجرا کن)
│   └── migrations/              ← تغییرات روی دیتابیسی که قبلاً schema.sql رو داشته
├── back/                        ← بک‌اند FastAPI
│   ├── app/
│   │   ├── models/               ← مدل‌های SQLAlchemy (۸ جدول)
│   │   ├── color_engine/         ← استخراج رنگ + blend (فاز ۳، زودتر پیاده شد)
│   │   ├── storage/              ← کلاینت MinIO
│   │   └── routers/
│   │       ├── auth.py            ← ثبت‌نام/لاگین (فعلاً داخلی، بعداً با سیستم بزرگ‌تر جایگزین می‌شه)
│   │       ├── seller.py          ← نمونه‌ی مسیر محافظت‌شده
│   │       └── demo.py            ← بدون Auth، برای دموی لایو
│   └── scripts/
│       └── seed_demo_data.py     ← پر کردن دیتابیس با Anchorها + چند Shade نمونه
└── live-demo/
    └── index.html                ← دموی زنده (دوربین واقعی)، مستقل از بقیه‌ی پروژه
```

## راه‌اندازی محلی (قدم به قدم)

### ۱. بالا آوردن Postgres + MinIO
```bash
docker-compose up -d postgres minio
```
- schema.sql به‌صورت خودکار روی Postgres اجرا می‌شه (از `docker-entrypoint-initdb.d`).
- کنسول MinIO: http://localhost:9001 (کاربری/رمز: `minioadmin`/`minioadmin`)

اگه دیتابیسی داری که قبلاً schema.sql رو (بدون sort_order) اجرا کرده، به‌جاش این رو بزن:
```bash
psql $DATABASE_URL -f src/database/migrations/001_add_sort_order.sql
```

### ۲. نصب و اجرای بک‌اند
```bash
cd src/back
pip install -r requirements.txt
cp .env.example .env   # و مقادیرش رو چک کن
uvicorn app.main:app --reload
```

### ۳. پر کردن دیتابیس با داده‌ی نمونه
```bash
cd src/back
python -m scripts.seed_demo_data
```
این اسکریپت Idempotent‌ه (اجرای دوباره‌ش داده‌ی تکراری نمی‌سازه): ۶ تا Anchor پوستی + یه Seller/Brand/Product نمونه + ۴ تا Shade با `render_color` واقعی برای هر Anchor می‌سازه.

### ۴. باز کردن دموی زنده
فایل `src/live-demo/index.html` رو مستقیم توی مرورگر باز کن (نیاز به وب‌سرور نداره، فقط باید بک‌اند روشن باشه). اگه بک‌اند جای دیگه‌ای (نه localhost:8000) بالاست، آدرسش رو توی همون صفحه عوض کن.

## نکات مهم
- بخش Auth (ثبت‌نام/لاگین) فعلاً داخلیه؛ طبق تصمیم اخیر، قراره بعداً با اعتبارسنجی سیستم بزرگ‌تر جایگزین بشه — این تغییر هنوز اعمال نشده.
- `/demo/*` عمداً بدون Auth‌ه چون برای دموی Buyer-facing طراحی شده (که از اول قرار بود Guest-friendly باشه).
- عکس واقعی Swatch هنوز برای هیچ‌کدوم از Shadeهای نمونه آپلود نشده؛ `swatch_image_url` تا وقتی عکس واقعی توی MinIO نریزی، `null` برمی‌گرده — این عمدیه، نه باگ.
