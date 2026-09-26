# Lipstick swatch → رنگ + پیش‌نمایش زنده روی لب

فروشنده عکس سواچ رو آپلود می‌کنه، دو کادر می‌کشه (پوست خالی + رژ)، و رنگ خالص رژ استخراج می‌شه.
عکس توی **MinIO** و رنگ/متادیتا توی **Postgres** ذخیره می‌شه؛ رنگ‌های تأییدشده برای دموی لایو
(`/live`) استفاده می‌شن. سیستم **هیچ نمونه‌ی خودساخته‌ای** توی دیتابیس نمی‌ذاره:
فقط سواچ‌هایی هست که خودت از `/review` آپلود کردی.

> مسیر سبک/بدون-دیتابیس قدیمی (`extract.html`، `/extract`، `/apply`، `store.py`) و دموی کاملاً
> سمت مرورگر (`src/live-demo/`) هر دو حذف شدن. لندمارک لب و ترکیب رنگ لایو الان یه‌جا،
> سمت بک‌اند (Python)، نگه‌داری می‌شه.

## صفحه‌ها

|             | صفحه                      | ذخیره‌سازی                                | کاربرد                                                                                             |
| ----------- | ------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------- |
| آپلود/بررسی | `/review` ← `/seller/...` | Postgres + MinIO                          | آپلود سواچ، بررسی، تأیید/رد رنگ‌ها، و پیش‌نمایش لایو (پنل ۳ همین صفحه)                             |
| دموی لایو   | `/live`                   | Postgres + MinIO (از طریق `/demo/shades`) | ریدایرکت به `/review#livePanel` — لندمارک لب و ترکیب رنگ سمت بک‌اند (WebSocket + MediaPipe پایتون) |

## استخراج رنگ — GrabCut

برای جدا کردن پیگمنت از پوست _داخل_ کادر رژ از **GrabCut** (`cv2.grabCut`) استفاده می‌شه؛ کادر پوستی که
فروشنده می‌کشه به‌عنوان «پس‌زمینه‌ی قطعی» بهش داده می‌شه. روی لکه‌های نامنظم و کادر شل مقاومه.

| سناریو                               | ΔE    |
| ------------------------------------ | ----- |
| کادر شل دور لکه‌ی نامنظم (عکس واقعی) | ۰.۰   |
| کادر خیلی شل (فقط ۱۵٪ پیگمنت)        | ≈ ۲.۴ |
| رژ نودی کم‌کروما + آلودگی شدید پوست  | ۰.۰   |
| رژ آبی فانتزی + کادر شل              | ≈ ۰.۶ |
| هایلایت گلاس + کادر شل               | ≈ ۰.۴ |
| کادر کاملاً پر                       | ≈ ۰.۵ |

اگه GrabCut چیزی پیدا نکنه به میانه‌ی کل کادر برمی‌گرده و هشدار `swatch_pigment_not_found` می‌ده.
هزینه: حدود ۱ تا ۱.۵ ثانیه برای هر استخراج (endpoint sync هست تا سرور قفل نشه).

## پیش‌نمایش لایو

سمت بک‌اند اجرا می‌شه (نه مرورگر): کلاینت (پنل ۳ در `app/static/review.html`) هر فریم دوربین رو با
WebSocket (`/ws/live-tryon`) به سرور می‌فرسته؛ سرور با **MediaPipe پایتون** (`face_mesh`)
لندمارک لب رو پیدا می‌کنه، ماسک لب رو می‌سازه (بیرونی پر، داخلی خالی، لبه‌ی نرم/feather) و رنگ رو
توی فضای **CIE Lab** با یه **انتقال رنگ حفظ‌کننده‌ی بافت** اعمال می‌کنه: به‌جای blend خطی به‌سمت یه
مقدار ثابت (که بافت طبیعی لب رو صاف می‌کنه)، فقط میانگین رنگ لب کاربر به‌سمت رنگ هدف جابه‌جا می‌شه و
اختلاف هر پیکسل از میانگین (هایلایت، خط‌ها، سایه) دست‌نخورده می‌مونه — نتیجه بیشتر شبیه پیگمنت واقعیه
تا یه لایه‌ی رنگ یکدست. پوشش و شدت هایلایت به‌ازای هر نوع محصول (`liquid/stick/gloss/balm/oil/plumper`)
جدا تنظیم شده (`app/color_engine/live_render.py`، `FINISHES`). فریم رنگ‌شده به‌صورت JPEG برمی‌گرده و
کلاینت فقط نمایشش می‌ده. رنگ‌ها مستقیم از `GET /demo/shades` (فقط approved) میان.

> نکته: opacity استفاده‌شده در لایو (`FINISHES`, بر اساس نوع محصول) با opacity ثابت
> `BASE_OPACITY=0.85` که در `app/color_engine/blend.py` برای پیش‌نمایش استاتیک (`shade_render_profile`)
> استفاده می‌شه، یکی نیست — یعنی رنگی که در صفحه‌ی محصول ثابت دیده می‌شه با رنگی که لایو روی لب
> می‌شینه دقیقاً یکسان نخواهد بود. اگه قراره این دو همیشه یکی بمونن، باید یکی از دو مسیر اصلاح بشه.

چون هر فریم یه رفت‌وبرگشت شبکه + inference پایتونی داره، این real-time واقعی (۳۰fps) نیست؛
یه تصمیم آگاهانه‌ست، نه محدودیت ناخواسته. برای کاهش لتنسی، اولین جای تنظیم رزولوشن ارسالی
(`CAPTURE_W` توی `review.html`) ـه.

## اجرا

```bash
docker compose up -d postgres minio        # از ریشه‌ی ریپو
cd src/back
pip install -r requirements.txt
python -m scripts.init_infra               # جدول‌ها (create_all) + ۶ Anchor مرجع + bucket — بدون هیچ نمونه‌ای
uvicorn app.main:app --reload
```

بعد `http://localhost:8000/review` (یا `/docs`، `/health`، `/live` برای دموی لایو با دوربین —
نیازی به دسترسی داشتن به بک‌اند از یه فایل جدا نیست، همه‌چی از همون سرور سرو می‌شه). جزئیات: `SETUP.md`.

بدون Docker (SQLite + پوشه‌ی محلی): `python -m scripts.run_local`.

> جدول‌ها فعلاً با `Base.metadata.create_all` ساخته می‌شن، نه با Alembic migration واقعی؛ فایل‌های
> `alembic/` (`env.py`, `script.py.mako`, `alembic.ini`) آماده‌ن ولی هنوز هیچ ریویژنی نوشته نشده و
> هیچ‌جا `alembic upgrade head` صدا زده نمی‌شه.

## تست و ابزار منطق رنگ (بدون دیتابیس)

اینا مستقیم تابع‌های `color_engine`/`imaging` رو صدا می‌زنن (نه از طریق API)، پس مستقل از
دیتابیس و بک‌اند بالا بودنه:

```bash
cd src/back
pytest                                                   # منطق استخراج/decode عکس/رندر لایو؛ به دیتابیس چیزی نمی‌نویسه
python -m scripts.make_test_swatches                     # عکس مصنوعی با جواب معلوم (فقط برای کار روی منطق)
python -m scripts.run_manifest --dir test_swatches       # موتور رنگ روی یه پوشه عکس، بدون سرور
```

## ساختار

```
docker-compose.yml                 # postgres + minio (+ backend)
remove_legacy_files.py             # حذف idempotent مسیر سبک/بدون-دیتابیس قدیمی (اگه هنوز اجرا نشده)
src/back/
  app/
    main.py                        # /health / (→/review) /review /live + روترها
    routers/seller.py              # برند/محصول/آپلود سواچ/تأیید (Postgres + MinIO)
    routers/demo.py                # /demo/shades (فقط approved) و /demo/skin-tone-anchors
    routers/live.py                # /ws/live-tryon — لندمارک لب + ترکیب رنگ سمت بک‌اند
    models/  database.py  alembic/ # SQLAlchemy + اسکلت Alembic (فعلاً بدون migration فعال)
    storage/                       # MinIO (یا پوشه‌ی محلی با STORAGE_BACKEND=local)
    api/deps.py                    # هویت: AUTH_MODE=dev|jwt
    uploads.py                     # خوندن/اعتبارسنجی عکس آپلودی (ICC→sRGB، سقف حجم/پیکسل)
    imaging.py  anchors.py
    color_engine/                  # extraction.py (GrabCut)، blend.py، live_render.py (ماسک+رنگ لایو)، colorspace.py، swatch_template.py
    static/                        # review.html (آپلود + بررسی + پیش‌نمایش لایو، همه توی یک صفحه)
  scripts/                         # init_infra (جدول‌ها + Anchor + bucket)، run_local، make_test_swatches، run_manifest
  tests/
```

## نکته‌ها

- `AUTH_MODE=dev` فقط برای توسعه‌ست (هدر `X-External-User-Id`)؛ برای production: `AUTH_MODE=jwt` + `HOST_JWT_SECRET`.
- ۶ Anchor پوست داده‌ی مرجع سیستمه (نه نمونه) و فقط توی `app/anchors.py` تعریف می‌شه؛ `init_infra` همون‌ها رو با همون idها توی دیتابیس می‌ذاره.
- دموی لایو فقط رنگ‌های **approved** رو نشون می‌ده: بعد از آپلود توی `/review` «تأیید» رو بزن.
- Anchor فعلاً فقط در استخراج رنگ سواچ (تصحیح نور عکس) و در محاسبه‌ی `shade_render_profile` (پیش‌نمایش استاتیک) استفاده می‌شه؛ در مسیر لایو (`/ws/live-tryon`) هنوز کالیبراسیون بر اساس Anchor پیاده نشده — رنگ پوست دیده‌شده در دوربین اصلاح نمی‌شه.
- specular highlight واقعی (سند `app/color_engine/SPECULAR_HIGHLIGHT_SPEC.md`) هنوز به‌صورت شیدر GPU پیاده نشده؛ چیزی که الان در `live_render.py` هست یه تقریب در فضای Lab سمت Python ـه (پارامترهای `spec`/`spec_desat` در `FINISHES`).
- آدرس presigned URL که از MinIO برمی‌گرده بر اساس `MINIO_ENDPOINT` ساخته می‌شه؛ اگه این مقدار آدرس داخلی شبکه‌ی Docker باشه (مثلاً `minio:9000`)، مرورگر کاربر نمی‌تونه بازش کنه — برای production یه `MINIO_PUBLIC_ENDPOINT` جدا یا reverse-proxy لازمه.
