# Lipstick swatch → color + lip preview (فاز اول)

هدف: **فروشنده عکس سواچ رو آپلود می‌کنه، دو کادر می‌کشه (پوست + رژ)، رنگ خالص
رژ رو می‌گیره** — و اختیاری اون رنگ رو روی یه عکس چهره پیش‌نمایش می‌کنه. بدون
ورود/Auth، بدون دیتابیس، بدون MinIO، بدون Docker.

## استخراج رنگ — GrabCut (الگوریتم استاندارد segmentation)
قبلاً برای جدا کردن پیگمنت از پوست *داخل* کادر رژ، از یه آستانه‌ی ساده‌ی Otsu
روی کروما استفاده می‌شد. جست‌وجو کردم دنیا برای این مسئله (یه کادر تقریبی دور
یه شیء، جدا کردن دقیق شیء از پس‌زمینه) چی استفاده می‌کنه: **GrabCut** — الگوریتم
کلاسیک segmentation (Rother/Kolmogorov/Blake، Microsoft Research، ۲۰۰۴)، دقیقاً
برای همین مسئله طراحی شده و توی OpenCV آماده‌ست (`cv2.grabCut`). به‌جای یه
آستانه‌ی ساده، رنگ پیش‌زمینه/پس‌زمینه رو با یه مدل آماری (GMM) یاد می‌گیره و
همبستگی مکانی پیکسل‌ها رو هم در نظر می‌گیره (Graph Cut) — یعنی به لکه‌های
نامنظم و نویز پوست مقاوم‌تره. کادر پوستی که خودت می‌کشی مستقیم به‌عنوان
«پس‌زمینه‌ی قطعی» به GrabCut داده می‌شه.

**تست عددی** (ΔE نسبت به رنگ واقعی، روی چند سناریوی سخت):
| سناریو | نتیجه |
|---|---|
| عکس واقعی‌ای که فرستادی (کادر شل دور لکه‌ی نامنظم) | ΔE = ۰.۰ |
| کادر خیلی شل‌تر (فقط ۱۵٪ کادر پیگمنت) | ΔE ≈ ۲.۴ |
| رژ نودی کم‌کروما + آلودگی شدید پوست | ΔE = ۰.۰ |
| رژ آبی فانتزی + کادر شل | ΔE ≈ ۰.۶ |
| هایلایت گلاس + کادر شل | ΔE ≈ ۰.۴ |
| کادر کاملاً پر (بدون تغییر نسبت به قبل) | ΔE ≈ ۰.۵ |

اگه GrabCut توی کادر رژ چیزی پیدا نکنه (مثلاً کادر اشتباهاً روی پوست خالی
کشیده شده)، به میانه‌ی کل کادر برمی‌گرده و هشدار `swatch_pigment_not_found`
می‌ده — کرش نمی‌کنه.

**هزینه:** هر استخراج حدود ۱ تا ۱.۵ ثانیه طول می‌کشه (قبلاً تقریباً آنی بود).
برای آپلود (نه لایو) این قابل‌قبوله.

روش قبلی خوشه‌بندی بدون کادر (`cluster_extraction.py`) هنوز توی کد هست، ولی نه
این و نه Otsu دیگه استفاده نمی‌شن.

## اپلای رنگ روی لب
`POST /apply`: عکس چهره + رنگ (#RRGGBB) → همون عکس با رژ روی لب (MediaPipe
FaceMesh + ترکیب Lab — همون منطقی که قبلاً توی `src/live-demo/index.html`
برای حالت لایو پورت شده بود؛ این نسخه برای عکس ثابته).

## اجرا
```bash
cd src/back
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```
بعد `http://localhost:8000/` یا `http://localhost:8000/docs`.
نتیجه‌ها توی `src/back/data/results.json` و عکس‌ها توی `src/back/data/uploads/`.

## حلقه‌ی سریع برای کار روی منطق (بدون سرور)
```bash
cd src/back
python -m scripts.make_test_swatches
python -m scripts.run_manifest --dir test_swatches
pytest   # ⚠ حدود ۳۰ ثانیه طول می‌کشه چون GrabCut سنگین‌تر از قبله
```

## ساختار
```
src/back/
  app/
    main.py                       # /extract  /apply  /extractions  /anchors  /health  /
    color_engine/
      extraction.py                # ★ روش فعلی — کادر دستی + GrabCut
      cluster_extraction.py        # روش بدون کادر — نگه‌داشته‌شده، پیش‌فرض نیست
      colorspace.py, swatch_template.py
    lip_apply.py                   # اپلای رنگ روی لب با MediaPipe (عکس ثابت)
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
  خروجی هر رکورد شامل `vivid_pixels_excluded_fraction` هم هست: چند درصد از کادر
  رژ به‌عنوان «پوست» تشخیص داده و کنار گذاشته شد.
- `POST /apply` (multipart): `photo`، `color` (#RRGGBB). خروجی: خود عکس با رژ.
- `GET /extractions`, `GET /extractions/{id}`, `DELETE /extractions/{id}`, `GET /anchors`.
