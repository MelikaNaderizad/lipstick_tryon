# Lipstick swatch → رنگ + پیش‌نمایش روی لب

فروشنده عکس سواچ رو آپلود می‌کنه، دو کادر می‌کشه (پوست خالی + رژ)، و رنگ خالص رژ استخراج می‌شه.
عکس توی **MinIO** و رنگ/متادیتا توی **Postgres** ذخیره می‌شه؛ رنگ‌های تأییدشده برای دموی لایو
(`src/live-demo`) استفاده می‌شن. سیستم **هیچ نمونه‌ی خودساخته‌ای** توی دیتابیس نمی‌ذاره:
فقط سواچ‌هایی هست که خودت از `/review` آپلود کردی.

## دو مسیر (عمداً جدا)
| | صفحه | ذخیره‌سازی | کاربرد |
|---|---|---|---|
| اصلی | `/review` ← `/seller/...` | Postgres + MinIO | آپلود، بررسی، تأیید/رد رنگ‌ها |
| سبک | `/` ← `/extract`, `/apply` | فایل JSON (`src/back/data`) | آزمایش سریع استخراج + پیش‌نمایش روی عکس چهره، بدون دیتابیس |

فقط رنگ‌های **approved** توی `/demo/shades` (و در نتیجه دموی لایو) دیده می‌شن؛ `?include_all=true` همه رو می‌ده.

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
هزینه: حدود ۱ تا ۱.۵ ثانیه برای هر استخراج (endpoint ها sync هستن تا سرور قفل نشه).

## اجرا
```bash
docker compose up -d postgres minio        # از ریشه‌ی ریپو
cd src/back
pip install -r requirements-dev.txt
python -m scripts.init_infra               # جدول‌ها + ۶ Anchor مرجع + bucket (هیچ نمونه‌ای نمی‌سازه)
uvicorn app.main:app --reload
```
بعد `http://localhost:8000/review` (یا `/`، `/docs`، `/health`). جزئیات: `SETUP.md`.

بدون Docker (SQLite + پوشه‌ی محلی): `python -m scripts.run_local`.

## تست و ابزار منطق رنگ (بدون دیتابیس)
```bash
cd src/back
pytest                                                   # فقط منطق استخراج/API سبک؛ به دیتابیس چیزی نمی‌نویسه
python -m scripts.make_test_swatches                     # عکس مصنوعی با جواب معلوم (فقط برای کار روی منطق)
python -m scripts.run_manifest --dir test_swatches       # موتور رنگ روی یه پوشه عکس، بدون سرور
```

## ساختار
```
docker-compose.yml                 # postgres + minio (+ backend)
src/back/
  app/
    main.py                        # /extract /apply /extractions /anchors /health / /review + روترها
    routers/seller.py              # برند/محصول/آپلود سواچ/تأیید (Postgres + MinIO)
    routers/demo.py                # /demo/shades (فقط approved) و /demo/skin-tone-anchors
    models/  database.py  alembic/ # SQLAlchemy + migration
    storage/                       # MinIO (یا پوشه‌ی محلی با STORAGE_BACKEND=local)
    api/deps.py                    # هویت: AUTH_MODE=dev|jwt
    uploads.py                     # خوندن/اعتبارسنجی عکس آپلودی (ICC→sRGB، سقف حجم/پیکسل)
    imaging.py  anchors.py  store.py  lip_apply.py
    color_engine/                  # extraction.py (GrabCut)، blend.py، colorspace.py، swatch_template.py
    static/                        # review.html (اصلی)، extract.html (سبک)
  scripts/                         # init_infra (جدول‌ها + Anchor + bucket)، run_local، make_test_swatches، run_manifest
  tests/
src/live-demo/index.html           # دموی زنده (دوربین) — BASE_OPACITY باید با blend.py یکی بمونه
```

## نکته‌ها
- `AUTH_MODE=dev` فقط برای توسعه‌ست (هدر `X-External-User-Id`)؛ برای production: `AUTH_MODE=jwt` + `HOST_JWT_SECRET`.
- ۶ Anchor پوست داده‌ی مرجع سیستمه (نه نمونه) و فقط توی `app/anchors.py` تعریف می‌شه؛ `init_infra` همون‌ها رو با همون idها توی دیتابیس می‌ذاره.
- دموی لایو فقط رنگ‌های **approved** رو نشون می‌ده: بعد از آپلود توی `/review` «تأیید» رو بزن.
