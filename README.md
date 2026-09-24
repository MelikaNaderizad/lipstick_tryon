# Lipstick swatch → رنگ + پیش‌نمایش زنده روی لب

فروشنده عکس سواچ رو آپلود می‌کنه، دو کادر می‌کشه (پوست خالی + رژ)، و رنگ خالص رژ استخراج می‌شه.
عکس توی **MinIO** و رنگ/متادیتا توی **Postgres** ذخیره می‌شه؛ رنگ‌های تأییدشده برای دموی لایو
(`src/live-demo`) استفاده می‌شن. سیستم **هیچ نمونه‌ی خودساخته‌ای** توی دیتابیس نمی‌ذاره:
فقط سواچ‌هایی هست که خودت از `/review` آپلود کردی.

> **به‌روزرسانی:** مسیر سبک/بدون-دیتابیس قبلی (`extract.html`، `/extract`، `/apply`،
> `store.py`) که فقط برای ارائه‌ی ماژولار قبل از آماده شدن دیتابیس بود، حذف شد.
> اگه هنوز توی چک‌اوتت هست: `python remove_legacy_files.py --apply`.

## صفحه‌ها
| | صفحه | ذخیره‌سازی | کاربرد |
|---|---|---|---|
| آپلود/بررسی | `/review` ← `/seller/...` | Postgres + MinIO | آپلود سواچ، بررسی، تأیید/رد رنگ‌ها |
| دموی لایو | `src/live-demo/index.html` (مستقیم توی مرورگر باز شه) | — | پیش‌نمایش زنده‌ی رژ روی لب با دوربین، از رنگ‌های approved (`/demo/shades`) |

## استخراج رنگ — GrabCut
برای جدا کردن پیگمنت از پوست *داخل* کادر رژ از **GrabCut** (`cv2.grabCut`) استفاده می‌شه؛ کادر پوستی که
فروشنده می‌کشه به‌عنوان «پس‌زمینه‌ی قطعی» بهش داده می‌شه. روی لکه‌های نامنظم و کادر شل مقاومه.

| سناریو | ΔE |
|---|---|
| کادر شل دور لکه‌ی نامنظم (عکس واقعی) | ۰.۰ |
| کادر خیلی شل (فقط ۱۵٪ پیگمنت) | ≈ ۲.۴ |
| رژ نودی کم‌کروما + آلودگی شدید پوست | ۰.۰ |
| رژ آبی فانتزی + کادر شل | ≈ ۰.۶ |
| هایلایت گلاس + کادر شل | ≈ ۰.۴ |
| کادر کاملاً پر | ≈ ۰.۵ |

اگه GrabCut چیزی پیدا نکنه به میانه‌ی کل کادر برمی‌گرده و هشدار `swatch_pigment_not_found` می‌ده.
هزینه: حدود ۱ تا ۱.۵ ثانیه برای هر استخراج (endpoint sync هست تا سرور قفل نشه).

## پیش‌نمایش لایو (`src/live-demo`)
کاملاً سمت مرورگر اجرا می‌شه (بدون وابستگی سرور به mediapipe):
- لندمارک لب با MediaPipe FaceLandmarker (`@mediapipe/tasks-vision`, CDN).
- ماسک لب: کانتور بیرونی پر، داخلی با قانون `evenodd` خالی می‌شه (= فقط خودِ لب)، با یه بلور کوچیک
  (feather) روی لبه تا مرز تیز/بریده نباشه.
- ترکیب رنگ در فضای **CIE Lab** — فقط کانال a/b عوض می‌شه، L با ضریب کم‌تر تا بافت/های‌لایت طبیعی
  لب حفظ بشه. همون منطق و همون ثابت‌ها (`BASE_OPACITY`, ...) که `app/color_engine/blend.py` استفاده
  می‌کنه، برای هم‌خوانی رنگ بین پیش‌نمایش‌های استاتیک و لایو.
- رنگ‌ها مستقیم از `GET /demo/shades` (فقط approved) و `GET /demo/skin-tone-anchors` میان.

## اجرا
```bash
docker compose up -d postgres minio        # از ریشه‌ی ریپو
cd src/back
pip install -r requirements-dev.txt
python -m scripts.init_infra               # جدول‌ها + ۶ Anchor مرجع + bucket (هیچ نمونه‌ای نمی‌سازه)
uvicorn app.main:app --reload
```
بعد `http://localhost:8000/review` (یا `/docs`، `/health`). برای دموی لایو، `src/live-demo/index.html`
رو مستقیم توی مرورگر باز کن (آدرس بک‌اند بالای صفحه قابل تنظیمه). جزئیات: `SETUP.md`.

بدون Docker (SQLite + پوشه‌ی محلی): `python -m scripts.run_local`.

## تست و ابزار منطق رنگ (بدون دیتابیس)
اینا مستقیم تابع‌های `color_engine`/`imaging` رو صدا می‌زنن (نه از طریق API)، پس مستقل از
دیتابیس و بک‌اند بالا بودنه:
```bash
cd src/back
pytest                                                   # منطق استخراج/decode عکس؛ به دیتابیس چیزی نمی‌نویسه
python -m scripts.make_test_swatches                     # عکس مصنوعی با جواب معلوم (فقط برای کار روی منطق)
python -m scripts.run_manifest --dir test_swatches       # موتور رنگ روی یه پوشه عکس، بدون سرور
```

## ساختار
```
docker-compose.yml                 # postgres + minio (+ backend)
remove_legacy_files.py             # حذف idempotent مسیر سبک/بدون-دیتابیس قبلی
src/back/
  app/
    main.py                        # /health / (→/review) /review + روترها
    routers/seller.py              # برند/محصول/آپلود سواچ/تأیید (Postgres + MinIO)
    routers/demo.py                # /demo/shades (فقط approved) و /demo/skin-tone-anchors
    models/  database.py  alembic/ # SQLAlchemy + migration
    storage/                       # MinIO (یا پوشه‌ی محلی با STORAGE_BACKEND=local)
    api/deps.py                    # هویت: AUTH_MODE=dev|jwt
    uploads.py                     # خوندن/اعتبارسنجی عکس آپلودی (ICC→sRGB، سقف حجم/پیکسل)
    imaging.py  anchors.py
    color_engine/                  # extraction.py (GrabCut)، blend.py، colorspace.py، swatch_template.py
    static/                        # review.html
  scripts/                         # init_infra (جدول‌ها + Anchor + bucket)، run_local، make_test_swatches، run_manifest
  tests/
src/live-demo/index.html           # دموی زنده (دوربین) — BASE_OPACITY باید با blend.py یکی بمونه
```

## نکته‌ها
- `AUTH_MODE=dev` فقط برای توسعه‌ست (هدر `X-External-User-Id`)؛ برای production: `AUTH_MODE=jwt` + `HOST_JWT_SECRET`.
- ۶ Anchor پوست داده‌ی مرجع سیستمه (نه نمونه) و فقط توی `app/anchors.py` تعریف می‌شه؛ `init_infra` همون‌ها رو با همون idها توی دیتابیس می‌ذاره.
- دموی لایو فقط رنگ‌های **approved** رو نشون می‌ده: بعد از آپلود توی `/review` «تأیید» رو بزن.
