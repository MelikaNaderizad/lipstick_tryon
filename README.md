# Lipstick swatch → color + lip preview (فاز اول)

هدف: **فروشنده عکس سواچ رو آپلود می‌کنه، دو کادر می‌کشه، رنگ خالص رژ رو می‌گیره** —
و اختیاری اون رنگ رو روی یه عکس چهره پیش‌نمایش می‌کنه. بدون ورود/Auth، بدون
دیتابیس، بدون MinIO، بدون Docker.

## روش استخراج رنگ (نسخه‌ی فعلی: کادر دستی)
دو کادر روی عکس می‌کشی:
- **آبی — کادر پوست:** یه تکه پوست خالی (فقط برای تصحیح نور اختیاری لازمه).
- **سبز — کادر رژ:** دقیقاً روی رنگ رژ، بدون هیچ پیکسل دیگه‌ای.

رنگ نهایی از میانه‌ی پیکسل‌های *فقط داخل کادر سبز* به‌دست میاد. هرچی بیرون این
دو کادره — آستین، پس‌زمینه، انگشت — روی نتیجه اثر نمی‌ذاره، چون اصلاً خونده
نمی‌شه. این تست شده: یه مستطیل قرمز پررنگ (شبیه آستین) بیرون کادرها گذاشتم و
رنگ استخراجی عوض نشد (`tests/test_api.py::test_distractor_outside_boxes_is_ignored`).

**قبلاً دو روش دیگه امتحان شده بود که هیچ‌کدوم کافی نبودن:**
1. کادر *ثابت* در موقعیت از‌پیش‌تعیین‌شده — اگه سواچ واقعی توی اون موقعیت
   نبود (مثل عکسی که فرستادی)، رنگ پوست رو برمی‌گردوند.
2. خوشه‌بندی *بدون کادر* (پورت‌شده از فایلی که فرستادی) — روی سواچ آزاد خوب
   کار می‌کرد، ولی اگه توی فریم چیز پررنگ‌تری از رژ باشه (آستین، برافروختگی
   پوست)، ممکن بود اون رو به‌جای رژ انتخاب کنه. کدش هنوز توی
   `app/color_engine/cluster_extraction.py` هست ولی دیگه پیش‌فرض نیست.

کادر دستی (نسخه‌ی فعلی) از هر دو قابل‌پیش‌بینی‌تره چون خودت مشخص می‌کنی دقیقاً
کدوم پیکسل‌ها خونده بشن.

تصحیح نور اختیاریه (پیش‌فرض «بدون تصحیح» — همون رنگ خام کادر). اگه نور عکس
مشکل داشت، «فقط روشنایی» یا «کامل» رو با یه Anchor پوست امتحان کن.

## اپلای رنگ روی لب
`POST /apply`: عکس چهره + رنگ (#RRGGBB) → همون عکس با رژ روی لب. از MediaPipe
FaceMesh برای پیدا کردن کانتور لب استفاده می‌کنه (همون منطقی که قبلاً توی
`src/live-demo/index.html` برای حالت لایو پورت شده بود؛ این نسخه برای عکس
ثابته، نه دوربین زنده).

## اجرا
```bash
cd src/back
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```
بعد `http://localhost:8000/` (صفحه‌ی آپلود + پیش‌نمایش لب) یا `http://localhost:8000/docs`.

نتیجه‌ها توی `src/back/data/results.json` و عکس‌ها توی `src/back/data/uploads/` می‌مونن.

## حلقه‌ی سریع برای کار روی منطق (بدون سرور)
```bash
cd src/back
python -m scripts.make_test_swatches
python -m scripts.run_manifest --dir test_swatches
pytest
```

## ساختار
```
src/back/
  app/
    main.py                       # /extract  /apply  /extractions  /anchors  /health  /
    color_engine/
      extraction.py                # ★ روش فعلی — کادر دستی (پوست + رژ)
      cluster_extraction.py        # روش بدون کادر — نگه‌داشته‌شده، پیش‌فرض نیست
      colorspace.py, swatch_template.py
    lip_apply.py                   # ★ اپلای رنگ روی لب با MediaPipe (عکس ثابت)
    anchors.py                     # ۶ Anchor پوست — فقط برای تصحیح نور اختیاری
    imaging.py                     # خوندن عکس + تبدیل ICC (Display P3 و ...) به sRGB
    store.py                       # ذخیره‌ی نتیجه‌ها توی JSON (بدون دیتابیس)
    static/extract.html            # صفحه‌ی آپلود با کشیدن کادر + پیش‌نمایش لب
  scripts/                         # make_test_swatches, run_manifest
  tests/
```

## API
- `POST /extract` (multipart): `swatch`، `skin_box`، `swatch_box` (کسری `x0,y0,x1,y1`، هر دو لازم)،
  `correction_mode` (`none|exposure|full`, پیش‌فرض `none`)، `anchor_id` (اختیاری)،
  `expected_color` (اختیاری؛ ΔE برمی‌گردونه)، `save` (پیش‌فرض true).
- `POST /apply` (multipart): `photo`، `color` (#RRGGBB). خروجی: خود عکس با رژ.
- `GET /extractions`, `GET /extractions/{id}`, `DELETE /extractions/{id}`, `GET /anchors`.
