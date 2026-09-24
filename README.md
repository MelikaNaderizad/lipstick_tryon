# Lipstick swatch → رنگ + پیش‌نمایش زنده روی لب

فروشنده عکس سواچ رو آپلود می‌کنه، دو کادر می‌کشه (پوست خالی + رژ)، و رنگ خالص رژ استخراج می‌شه.
عکس توی **MinIO** و رنگ/متادیتا توی **Postgres** ذخیره می‌شه؛ رنگ‌های تأییدشده برای دموی لایو
(`/live`) استفاده می‌شن. سیستم **هیچ نمونه‌ی خودساخته‌ای** توی دیتابیس نمی‌ذاره:
فقط سواچ‌هایی هست که خودت از `/review` آپلود کردی.

> **به‌روزرسانی:** مسیر سبک/بدون-دیتابیس قبلی (`extract.html`، `/extract`، `/apply`،
> `store.py`) که فقط برای ارائه‌ی ماژولار قبل از آماده شدن دیتابیس بود، حذف شد.
> اگه هنوز توی چک‌اوتت هست: `python remove_legacy_files.py --apply`.

> **به‌روزرسانی دوم:** دموی لایو قبلاً کاملاً سمت مرورگر بود (`src/live-demo/index.html`،
> با MediaPipe JS + blend رنگ توی JS). با تصمیم صریح، این منطق (لندمارک لب + ترکیب رنگ)
> رفت بک‌اند (`app/routers/live.py` + `app/color_engine/live_render.py`)؛ کلاینت هر فریم
> رو با WebSocket می‌فرسته و رنگ‌شده پس می‌گیره. `src/live-demo` دیگه لازم نیست و خالی/حذف‌شده
> می‌مونه. مسیر جدید: `/live`.

## صفحه‌ها
| | صفحه | ذخیره‌سازی | کاربرد |
|---|---|---|---|
| آپلود/بررسی | `/review` ← `/seller/...` | Postgres + MinIO | آپلود سواچ، بررسی، تأیید/رد رنگ‌ها |
| دموی لایو | `/live` | Postgres + MinIO (از طریق `/demo/shades`) | پیش‌نمایش زنده‌ی رژ روی لب با دوربین؛ لندمارک لب و ترکیب رنگ سمت بک‌اند (WebSocket + MediaPipe پایتون) |

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

## پیش‌نمایش لایو (`/live`)
سمت بک‌اند اجرا می‌شه (نه مرورگر): کلاینت (`app/static/live.html`) هر فریم دوربین رو با
WebSocket (`/ws/live-tryon`) به سرور می‌فرسته؛ سرور با **MediaPipe پایتون** (`face_mesh`)
لندمارک لب رو پیدا می‌کنه، ماسک لب رو می‌سازه (بیرونی پر، داخلی با قانون evenodd خالی، لبه
فدرشده) و رنگ رو توی فضای **CIE Lab** با یه **انتقال رنگ حفظ‌کننده‌ی بافت** اعمال می‌کنه: به‌جای
blend خطی به‌سمت یه مقدار ثابت (که بافت طبیعی لب رو صاف می‌کنه)، فقط میانگین رنگ لب کاربر
به‌سمت رنگ هدف جابه‌جا می‌شه و اختلاف هر پیکسل از میانگین (های‌لایت، خط‌ها، سایه) دست‌نخورده
می‌مونه — نتیجه بیشتر شبیه پیگمنت واقعیه تا یه لایه‌ی رنگ یکدست. فریم رنگ‌شده به‌صورت JPEG
برمی‌گرده و کلاینت فقط نمایشش می‌ده (به‌علاوه‌ی آینه‌کردن نمایش با CSS، چون فریم ارسالی به
سرور آینه نیست). منطق و ثابت‌ها (`BASE_OPACITY`, ...) با `app/color_engine/blend.py` هم‌خوانن.
رنگ‌ها مستقیم از `GET /demo/shades` (فقط approved) میان.

چون هر فریم یه رفت‌وبرگشت شبکه + inference پایتونی داره، این real-time واقعی (۳۰fps) نیست؛
یه تصمیم آگاهانه‌ست، نه محدودیت ناخواسته. برای کاهش لتنسی، اولین جای تنظیم رزولوشن ارسالی
(`CAPTURE_W` توی `live.html`) ـه.

## اجرا
```bash
docker compose up -d postgres minio        # از ریشه‌ی ریپو
cd src/back
pip install -r requirements-dev.txt
python -m scripts.init_infra               # جدول‌ها + ۶ Anchor مرجع + bucket (هیچ نمونه‌ای نمی‌سازه)
uvicorn app.main:app --reload
```
بعد `http://localhost:8000/review` (یا `/docs`، `/health`، `/live` برای دموی لایو با دوربین —
نیازی به دسترسی داشتن به بک‌اند از یه فایل جدا نیست، همه‌چی از همون سرور سرو می‌شه). جزئیات: `SETUP.md`.

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
    main.py                        # /health / (→/review) /review /live + روترها
    routers/seller.py              # برند/محصول/آپلود سواچ/تأیید (Postgres + MinIO)
    routers/demo.py                # /demo/shades (فقط approved) و /demo/skin-tone-anchors
    routers/live.py                # /ws/live-tryon — لندمارک لب + ترکیب رنگ سمت بک‌اند
    models/  database.py  alembic/ # SQLAlchemy + migration
    storage/                       # MinIO (یا پوشه‌ی محلی با STORAGE_BACKEND=local)
    api/deps.py                    # هویت: AUTH_MODE=dev|jwt
    uploads.py                     # خوندن/اعتبارسنجی عکس آپلودی (ICC→sRGB، سقف حجم/پیکسل)
    imaging.py  anchors.py
    color_engine/                  # extraction.py (GrabCut)، blend.py، live_render.py (ماسک+رنگ لایو)، colorspace.py، swatch_template.py
    static/                        # review.html، live.html
  scripts/                         # init_infra (جدول‌ها + Anchor + bucket)، run_local، make_test_swatches، run_manifest
  tests/
src/live-demo/                     # قدیمی و منسوخ — منطق لایو رفته بک‌اند (/live)؛ خالی/حذف‌شده می‌مونه
```

## نکته‌ها
- `AUTH_MODE=dev` فقط برای توسعه‌ست (هدر `X-External-User-Id`)؛ برای production: `AUTH_MODE=jwt` + `HOST_JWT_SECRET`.
- ۶ Anchor پوست داده‌ی مرجع سیستمه (نه نمونه) و فقط توی `app/anchors.py` تعریف می‌شه؛ `init_infra` همون‌ها رو با همون idها توی دیتابیس می‌ذاره.
- دموی لایو فقط رنگ‌های **approved** رو نشون می‌ده: بعد از آپلود توی `/review` «تأیید» رو بزن.
