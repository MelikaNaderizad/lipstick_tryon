# راه‌اندازی با داده‌ی خودت

اصل کار: **هیچ نمونه‌ی ساختگی و هیچ تست خودکاری روی دیتابیس نیست.** دیتابیس با جدول‌ها و ۶ Anchor مرجع شروع می‌شه
و تنها رنگ‌ها همون‌هایی هستن که خودت از سواچ‌های واقعی آپلود می‌کنی.

## ۰. پاک‌سازی مسیر سبک/بدون-دیتابیس قدیمی (اگه هنوز روی چک‌اوتته)

اون مسیر (`extract.html`, `/extract`, `/apply`, `store.py`, `lip_apply.py`, `tests/test_api.py`)
و پوشه‌ی دموی کاملاً سمت مرورگر (`src/live-demo/`) دیگه استفاده نمی‌شن. اگه فایل‌های مسیر سبک هنوز
توی ریپوت هستن:

```bash
python remove_legacy_files.py            # پیش‌نمایش
python remove_legacy_files.py --apply    # حذف واقعی (قبلش commit بگیر)
```

Idempotent ـه؛ اگه قبلاً اجرا کرده باشی یا این فایل‌ها از قبل نباشن، بدون خطا رد می‌شه.
پوشه‌ی `src/live-demo/` جدا از این اسکریپت‌ه؛ اگه هنوز هست، خودت حذفش کن — منطقش کامل رفته
`app/routers/live.py` + `app/color_engine/live_render.py`.

## ۱. زیرساخت

```bash
docker compose up -d postgres minio
cd src/back
pip install -r requirements.txt
python -m scripts.init_infra         # جدول‌ها (create_all) + Anchorهای مرجع + bucket — بدون هیچ نمونه‌ای
uvicorn app.main:app --reload
```

اگه قبلاً نمونه‌های ساختگی (seed یا اسکریپت آپلود) توی دیتابیس/MinIO ریختی و می‌خوای تمیز شروع کنی:

```bash
docker compose down -v               # ⚠ کل داده‌ی Postgres و MinIO پاک می‌شه
docker compose up -d postgres minio
python -m scripts.init_infra
```

> جدول‌ها با `Base.metadata.create_all` ساخته می‌شن، نه با Alembic migration. اسکلت Alembic
> (`alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`) توی ریپو هست ولی هنوز هیچ ریویژنی
> نوشته نشده و در هیچ اسکریپت یا Dockerfile ای `alembic upgrade head` صدا زده نمی‌شه. برای
> production بهتره قبل از رفتن جلو این تصمیم رو نهایی کنی (migration واقعی یا همین create_all).

## ۲. گذاشتن سواچ‌های خودت

1. `http://localhost:8000/review`
2. برند و محصول رو بساز، عکس‌های سواچ رو انتخاب کن، کادر آبی (پوست) و سبز (رژ) رو بکش، «آپلود و استخراج رنگ».
   عکس می‌ره MinIO و رنگ/متادیتا توی Postgres.
3. رنگ استخراج‌شده رو با عکس مقایسه کن؛ لازم بود اصلاحش کن (انتخابگر رنگ) و «تأیید» بزن.

## ۳. دموی لایو

`http://localhost:8000/live` رو باز کن (ریدایرکت می‌شه به `/review#livePanel` — پنل سوم همون
صفحه) — نیازی به فایل جدا یا اجرای جداگونه نیست، همه‌چی از همون بک‌اندی که بالاست سرو می‌شه.
لندمارک لب و ترکیب رنگ کاملاً سمت سرور انجام می‌شه (`/ws/live-tryon` + MediaPipe پایتون)؛ کلاینت
فقط فریم دوربین رو می‌فرسته و فریم رنگ‌شده رو نمایش می‌ده. این پنل رنگ‌های همون محصول رو نشون
می‌ده (و برای دیدن همه‌ی رنگ‌های تأییدشده‌ی سیستم، مستقل از محصول: `GET /demo/shades`).
برای دیدن همه‌ی رنگ‌ها، حتی تأییدنشده‌ها: `/demo/shades?include_all=true` رو مستقیم صدا بزن.

> Anchor (تناژ پوست) در این مرحله هنوز روی رنگ لایو اثری نمی‌ذاره — فقط روی استخراج رنگ سواچ
> (مرحله‌ی ۲ بالا) و روی `shade_render_profile` (پیش‌نمایش استاتیک) اعمال می‌شه. کالیبراسیون
> رنگ پوست دیده‌شده در دوربین کاربر هنوز کار باقی‌مونده‌ست.

## چی عوض شده نسبت به زیپ قبلی

- **حذف شد:** مسیر سبک/بدون-دیتابیس (`app/static/extract.html`, `app/store.py`,
  `app/lip_apply.py`, `tests/test_api.py`) و پوشه‌ی دموی سمت مرورگر (`src/live-demo/`).
  `app/main.py` هم متناسب ساده شد (`/`, `/anchors`, `/extract`, `/apply`, `/extractions*` حذف شدن؛
  `/` حالا به `/review` ریدایرکت می‌شه، و `/live` هم به `/review#livePanel`).
  `app/static/live.html` هم دیگه استفاده نمی‌شه (منطقش رفته پنل سوم `review.html`)؛ اگه هنوز
  توی چک‌اوتته می‌تونی حذفش کنی.
- **بهبود:** دموی لایو کامل سمت بک‌اند پیاده شده: `app/routers/live.py` (WebSocket +
  MediaPipe پایتون) و `app/color_engine/live_render.py` (ماسک لب + انتقال رنگ حفظ‌کننده‌ی
  بافت در Lab، با پوشش/هایلایت جدا برای هر نوع محصول)؛ کلاینتش پنل سوم `app/static/review.html`ـه.
- (تغییرات نوبت‌های قبل هم پابرجاست: Anchorها داخل `init_infra.py`، `run_local.py` هم از همون‌جا
  می‌خونه، ICC→sRGB، تراکنش‌ها، فقط approved توی `/demo/shades`.)

## عمداً دست نزدم

- **`make_test_swatches.py`، `run_manifest.py` و `test_extraction.py`، `test_extraction_smear.py`،
  `test_imaging.py`، `test_live_render.py`:** ابزار و تست منطق رنگ/عکس/رندر لایو، مستقیم تابع‌ها رو
  صدا می‌زنن (نه از طریق API)، پس مستقل از دیتابیس و بک‌اند بالا بودنه.
- **`run_local.py` و `STORAGE_BACKEND=local`:** اجرا بدون Docker (SQLite + پوشه‌ی محلی) هنوز ممکنه؛
  این یه گزینه‌ی dev‌ـه، نه همون مسیر «بدون دیتابیس» که حذف شد (این یکی همچنان یه دیتابیس واقعی
  می‌سازه، فقط SQLite به‌جای Postgres).

## نکات باز (هنوز حل نشده)

- **presigned URL از MinIO داخل Docker**: اگه `MINIO_ENDPOINT` آدرس داخلی شبکه‌ی Docker باشه
  (مثلاً `minio:9000`)، URL ای که برای نمایش عکس سواچ برمی‌گرده از بیرون کانتینر باز نمی‌شه.
- **Alembic بدون migration واقعی**: طبق بخش ۱ بالا.
