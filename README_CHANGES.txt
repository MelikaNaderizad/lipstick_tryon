از ریشه‌ی ریپو extract کن (روی فایل‌های قبلی می‌شینن):

  src/back/app/color_engine/live_render.py   ← ماسک بزرگ‌تر/نرم‌تر، guided filter خاموش، پوشش بیشتر
  src/back/app/routers/live.py               ← دیگه frame رو به ماسک نمی‌ده
  src/back/app/static/review.html            ← انتخاب فینیش
  src/back/app/main.py
  src/back/tests/test_live_render.py

تنظیم دستی (بالای live_render.py): MASK_GROW ، FEATHER_FRAC ، و opacity هر فینیش توی FINISHES.
