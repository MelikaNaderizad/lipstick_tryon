# -*- coding: utf-8 -*-
"""
شش رنگ مرجع پوست (Anchor): ۳ سطح روشنی × ۲ زیرتون (خنثی / زیتونی).

فعلاً ثابت توی کده (نه دیتابیس). وقتی فاز دیتابیس برگشت، همین لیست seed جدول
skin_tone_anchor می‌شه؛ «id» همون sort_order ـه تا بعداً هم‌خوان بمونه.
"""

SKIN_TONE_ANCHORS = [
    {"id": 1, "name": "روشن-خنثی",         "reference_color": "#F4DBC9", "sort_order": 1},
    {"id": 2, "name": "روشن-زیتونی",       "reference_color": "#E6DCB0", "sort_order": 2},
    {"id": 3, "name": "متوسط-خنثی",        "reference_color": "#D9B48A", "sort_order": 3},
    {"id": 4, "name": "متوسط-زیتونی",      "reference_color": "#C2B47E", "sort_order": 4},
    {"id": 5, "name": "گندمی‌تیره-خنثی",   "reference_color": "#9C7A52", "sort_order": 5},
    {"id": 6, "name": "گندمی‌تیره-زیتونی", "reference_color": "#9C8A5C", "sort_order": 6},
]


def anchor_by_id(anchor_id):
    return next((a for a in SKIN_TONE_ANCHORS if a["id"] == anchor_id), None)
