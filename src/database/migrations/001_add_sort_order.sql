-- اجرا کن فقط اگه schema.sql رو قبلاً یه‌بار روی این دیتابیس اجرا کرده بودی
-- (یعنی جدول skin_tone_anchor از قبل بدون ستون sort_order وجود داره).
-- روی یه دیتابیس تازه، این مهاجرت لازم نیست چون schema.sql به‌روز خودش این ستون رو داره.

ALTER TABLE skin_tone_anchor
    ADD COLUMN IF NOT EXISTS sort_order SMALLINT NOT NULL DEFAULT 0;
