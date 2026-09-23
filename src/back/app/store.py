# -*- coding: utf-8 -*-
"""
ذخیره‌ی ساده‌ی نتیجه‌ی استخراج‌ها — بدون دیتابیس.

  data/results.json          : لیست رکوردها (رنگ، کادرها، تنظیمات، هشدارها، ΔE)
  data/uploads/<id>.<ext>    : عکس اصلی آپلودشده

هدف: چند سواچ آپلود کنی، نتیجه‌ها رو کنار هم ببینی و با تغییر منطق مقایسه کنی.
مسیر با متغیر محیطی TRYON_DATA_DIR عوض می‌شه (پیش‌فرض: src/back/data).
"""
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()


def data_dir() -> Path:
    env = os.getenv("TRYON_DATA_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[1] / "data"


class ResultStore:
    def __init__(self, base=None):
        self.base = Path(base) if base else data_dir()
        self.uploads = self.base / "uploads"
        self.file = self.base / "results.json"

    def _read(self):
        if not self.file.exists():
            return []
        return json.loads(self.file.read_text(encoding="utf-8"))

    def _write(self, items):
        self.base.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.file)  # نوشتن اتمی؛ وسط کار قطع بشه فایل خراب نمی‌شه

    def add(self, record: dict, raw: bytes, ext: str) -> dict:
        with _LOCK:
            rid = uuid.uuid4().hex[:12]
            self.uploads.mkdir(parents=True, exist_ok=True)
            image_file = f"{rid}.{ext}"
            (self.uploads / image_file).write_bytes(raw)
            full = {
                "id": rid,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "image_file": image_file,
                **record,
            }
            items = self._read()
            items.append(full)
            self._write(items)
            return full

    def list(self):
        with _LOCK:
            return list(reversed(self._read()))  # تازه‌ترین اول

    def get(self, rid: str):
        with _LOCK:
            return next((r for r in self._read() if r["id"] == rid), None)

    def image_path(self, rid: str):
        rec = self.get(rid)
        if rec is None:
            return None
        path = self.uploads / rec["image_file"]
        return path if path.is_file() else None

    def delete(self, rid: str) -> bool:
        with _LOCK:
            items = self._read()
            rec = next((r for r in items if r["id"] == rid), None)
            if rec is None:
                return False
            self._write([r for r in items if r["id"] != rid])
            (self.uploads / rec["image_file"]).unlink(missing_ok=True)
            return True
