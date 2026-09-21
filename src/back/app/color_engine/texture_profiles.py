# -*- coding: utf-8 -*-
"""
پارامتر رندر هر «نوع محصول» (Product.category).

این مقدارها حدس اولیه‌ان، نه اندازه‌گیری — باید موقع کالیبراسیون لایو (ماژول ۲)
با چشم و روی عکس واقعی هر نوع تنظیم بشن. عمداً توی کد نگه داشته شدن (نه دیتابیس)
تا تغییرشون migration نخواد.

  alpha        : پوشش رژ روی لب (۱ = کاملاً کدر)
  detail_gain  : چقدر ریزبافت طبیعی لب حفظ بشه (۱ = همون بافت اصلی)
  specular     : شدت هایلایت مصنوعی (۰ = بدون درخشش)
"""
TEXTURE_PROFILES = {
    "liquid":  {"alpha": 0.90, "detail_gain": 0.85, "specular": 0.10},
    "stick":   {"alpha": 0.85, "detail_gain": 0.95, "specular": 0.15},
    "gloss":   {"alpha": 0.55, "detail_gain": 0.60, "specular": 0.80},
    "balm":    {"alpha": 0.35, "detail_gain": 1.00, "specular": 0.25},
    "oil":     {"alpha": 0.45, "detail_gain": 0.60, "specular": 0.85},
    "plumper": {"alpha": 0.50, "detail_gain": 0.65, "specular": 0.60},
}

DEFAULT_PROFILE = {"alpha": 0.85, "detail_gain": 0.90, "specular": 0.15}


def profile_for(category: str) -> dict:
    return TEXTURE_PROFILES.get(category, DEFAULT_PROFILE)
