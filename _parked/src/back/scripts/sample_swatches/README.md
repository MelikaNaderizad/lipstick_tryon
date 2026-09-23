# عکس‌های نمونه‌ی Swatch

عکس واقعی هر Shade رو دقیقاً با همین اسم‌ها اینجا بذار (این اسکریپت هیچ
عکسی خودش نمی‌سازه، فقط همینا رو که پیدا کنه آپلود می‌کنه):

- `demo-rose-classic.jpg`   ← برای Shade «رز کلاسیک»
- `demo-coral.jpg`          ← برای Shade «مرجانی»
- `demo-warm-nude.jpg`      ← برای Shade «نودی گرم»
- `demo-burgundy.jpg`       ← برای Shade «بروندی»

اگه اسم/تعداد Shade های `scripts/seed_demo_data.py` رو عوض کردی، اسم فایل
لازم رو هم از روی `swatch_image_path` همون Shade (بخش آخرش، بعد از `/`)
پیدا کن.

بعد از گذاشتن عکس‌ها:
```bash
cd src/back
python -m scripts.seed_demo_data
```
