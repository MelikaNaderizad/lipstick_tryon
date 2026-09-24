# راه‌اندازی با داده‌ی خودت

اصل کار: **هیچ نمونه‌ی ساختگی و هیچ تست خودکاری روی دیتابیس نیست.** دیتابیس با جدول‌ها و ۶ Anchor مرجع شروع می‌شه
و تنها رنگ‌ها همون‌هایی هستن که خودت از سواچ‌های واقعی آپلود می‌کنی.

## ۰. پاک‌سازی مسیر سبک/بدون-دیتابیس قبلی (یک‌بار)
اون مسیر (`extract.html`, `/extract`, `/apply`, `store.py`, `lip_apply.py`) فقط برای ارائه‌ی
ماژولار به کارفرما قبل از آماده شدن Postgres/MinIO ساخته شده بود. حالا که دیتابیس آماده‌ست:
```bash
python remove_legacy_files.py            # پیش‌نمایش
python remove_legacy_files.py --apply    # حذف واقعی (قبلش commit بگیر)
```
و این فایل‌ها رو از زیپ همراه جایگزین کن (تغییر کردن، نه فقط حذف):
`src/back/app/main.py`، `src/back/requirements.txt`، `src/back/tests/conftest.py`،
`src/live-demo/index.html`. Idempotent ـه؛ اگه قبلاً اجرا کرده باشی مشکلی نیست.

## ۱. زیرساخت
```bash
docker compose up -d postgres minio
cd src/back
pip install -r requirements-dev.txt
python -m scripts.init_infra         # جدول‌ها + Anchorهای مرجع + bucket — بدون هیچ نمونه‌ای
uvicorn app.main:app --reload
```
اگه قبلاً نمونه‌های ساختگی (seed یا اسکریپت آپلود) توی دیتابیس/MinIO ریختی و می‌خوای تمیز شروع کنی:
```bash
docker compose down -v               # ⚠ کل داده‌ی Postgres و MinIO پاک می‌شه
docker compose up -d postgres minio
python -m scripts.init_infra
```

## ۲. گذاشتن سواچ‌های خودت
1. `http://localhost:8000/review`
2. برند و محصول رو بساز، عکس‌های سواچ رو انتخاب کن، کادر آبی (پوست) و سبز (رژ) رو بکش، «آپلود و استخراج رنگ».
   عکس می‌ره MinIO و رنگ/متادیتا توی Postgres.
3. رنگ استخراج‌شده رو با عکس مقایسه کن؛ لازم بود اصلاحش کن (انتخابگر رنگ) و «تأیید» بزن.

## ۳. دموی لایو
`src/live-demo/index.html` رو مستقیم توی مرورگر باز کن (هیچ سروی لازم نداره، فقط باید بک‌اند
بالا باشه). آدرس بک‌اند بالای صفحه قابل تنظیمه. این صفحه رنگ‌های **تأییدشده** رو مستقیم از
دیتابیس می‌گیره (`GET /demo/shades`). برای دیدن همه‌ی رنگ‌ها، حتی تأییدنشده‌ها:
`/demo/shades?include_all=true`. ماسک لب و ترکیب رنگ کاملاً سمت مرورگره (MediaPipe + Lab)،
دقیقاً هم‌خوان با چیزی که موتور رنگ سرور (`color_engine/blend.py`) محاسبه می‌کنه.

## چی عوض شد نسبت به زیپ قبلی
- **حذف شد (این نوبت):** مسیر سبک/بدون-دیتابیس (`app/static/extract.html`, `app/store.py`,
  `app/lip_apply.py`, `tests/test_api.py`) — دیگه لازم نیست چون دیتابیس آماده‌ست.
  `app/main.py` هم متناسب ساده شد (`/`, `/anchors`, `/extract`, `/apply`, `/extractions*` حذف شدن؛
  `/` حالا به `/review` ریدایرکت می‌شه). `requirements.txt` بدون `mediapipe` (دیگه سمت سرور
  استفاده نمی‌شه — پیش‌نمایش لایو کامل توی مرورگره).
- **بهبود:** `src/live-demo/index.html` حالا لبه‌ی ماسک لب رو هم فدر (feather) می‌کنه، معادل
  `feather_px` که قبلاً فقط توی نسخه‌ی پایتونی/عکس ثابت بود.
- (تغییرات نوبت قبل هم پابرجاست: Anchorها داخل `init_infra.py`، `run_local.py` هم از همون‌جا
  می‌خونه، دموی لایو پیام «هنوز رنگی نیست» می‌ده، ICC→sRGB، تراکنش‌ها، فقط approved توی
  `/demo/shades`.)

## عمداً دست نزدم
- **`make_test_swatches.py`، `run_manifest.py` و `test_extraction.py`، `test_extraction_smear.py`،
  `test_imaging.py`:** ابزار و تست منطق رنگ/عکس، مستقیم تابع‌ها رو صدا می‌زنن (نه از طریق API)،
  پس مستقل از دیتابیس و از مسیر سبک حذف‌شده‌ان.
- **`run_local.py` و `STORAGE_BACKEND=local`:** اجرا بدون Docker (SQLite + پوشه‌ی محلی) هنوز ممکنه؛
  این یه گزینه‌ی dev‌ـه، نه همون مسیر «بدون دیتابیس» که حذف شد (این یکی همچنان یه دیتابیس واقعی
  می‌سازه، فقط SQLite به‌جای Postgres).
