-- این migration رو روی دیتابیسی بزن که schema.sql رو قبلاً (با finish و
-- category='lipstick' پیش‌فرض) اجرا کرده. تغییرات:
--   ۱. category محصول‌ها که هنوز مقدار پیش‌فرض قدیمی 'lipstick' دارن، به
--      یه نوع واقعی تغییر می‌کنن (فرض: 'stick' — بعداً خودت می‌تونی دستی
--      دقیق‌ترش کنی اگه لازم بود).
--   ۲. محدودیت CHECK روی نوع‌های واقعی محصول اضافه می‌شه.
--   ۳. ستون finish از shade کاملاً حذف می‌شه — «نوع» حالا سطح Product‌ه.

UPDATE product SET category = 'stick' WHERE category = 'lipstick';

ALTER TABLE product ALTER COLUMN category DROP DEFAULT;

ALTER TABLE product
    ADD CONSTRAINT product_category_check
    CHECK (category IN ('liquid', 'stick', 'gloss', 'balm', 'oil', 'plumper'));

ALTER TABLE shade DROP COLUMN IF EXISTS finish;
