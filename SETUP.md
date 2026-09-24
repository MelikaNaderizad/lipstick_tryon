# راه‌اندازی با داده‌ی خودت

اصل کار: **هیچ نمونه‌ی ساختگی و هیچ تست خودکاری روی دیتابیس نیست.** دیتابیس با جدول‌ها و ۶ Anchor مرجع شروع می‌شه
و تنها رنگ‌ها همون‌هایی هستن که خودت از سواچ‌های واقعی آپلود می‌کنی.

## ۱. Extract و پاک‌سازی
زیپ رو توی ریشه‌ی ریپو extract کن (overwrite بزن). `restore_parked.py` باید قبلاً اجرا شده باشه. بعد:
```bash
python cleanup_and_fix.py            # پیش‌نمایش
python cleanup_and_fix.py --apply    # اعمال (قبلش commit بگیر)
```
اگه نسخه‌ی قبلی زیپ رو اجرا کرده بودی مشکلی نیست؛ همه‌چیز idempotent ـه.

## ۲. زیرساخت
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

## ۳. گذاشتن سواچ‌های خودت
1. `http://localhost:8000/review`
2. برند و محصول رو بساز، عکس‌های سواچ رو انتخاب کن، کادر آبی (پوست) و سبز (رژ) رو بکش، «آپلود و استخراج رنگ».
   عکس می‌ره MinIO و رنگ/متادیتا توی Postgres.
3. رنگ استخراج‌شده رو با عکس مقایسه کن؛ لازم بود اصلاحش کن (انتخابگر رنگ) و «تأیید» بزن.
4. `src/live-demo/index.html` رنگ‌های **تأییدشده** رو مستقیم از دیتابیس می‌گیره (`GET /demo/shades`).
   برای دیدن همه‌ی رنگ‌ها، حتی تأییدنشده‌ها: `/demo/shades?include_all=true`.

## چی عوض شد نسبت به زیپ قبلی
- **حذف شد:** `seed_demo_data.py` (برند/محصول/رنگ نمونه)، `scripts/sample_swatches/`، `upload_swatches.py` (سواچ ساختگی می‌ساخت و برند «Test» می‌ریخت) و `tests/test_upload_api.py`.
  `tests/conftest.py` هم به نسخه‌ی اصلی خودت برگشت (بدون SQLite جعلی و MinIO جعلی).
- **Anchorها** حالا داخل `init_infra.py` ساخته می‌شن؛ `run_local.py` هم از همون‌جا می‌خونه.
- **دموی لایو:** متن «Seed شده» عوض شد و اگه هنوز رنگ تأییدشده‌ای نباشه پیام می‌ده.
- بقیه‌ی اصلاحات زیپ قبلی (ICC، تراکنش، `def` به‌جای `async def`، فقط approved توی `/demo/shades`، حذف کد مرده و تکراری) همون‌طوری‌ه.

## عمداً دست نزدم
- **`make_test_swatches.py`، `run_manifest.py` و `test_extraction.py`، `test_api.py`، `test_imaging.py`:** ابزار و تست منطق رنگ از فاز اول خودتن و به دیتابیس چیزی نمی‌نویسن
  (`test_extraction.py` به `make_test_swatches.py` وابسته‌ست). اگه اینا رو هم نمی‌خوای بگو پاک کنم.
- **مسیر سبک `/extract` + `extract.html` + `store.py`:** پیش‌نمایش روی لب (`/apply`) فقط اونجاست.
- **`run_local.py` و `STORAGE_BACKEND=local`:** اجرا بدون Docker (SQLite + پوشه‌ی محلی) هنوز ممکنه.
