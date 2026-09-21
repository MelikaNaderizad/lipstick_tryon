import os
import sys

# باید قبل از import اپ باشه: دیتابیس درون‌حافظه‌ی SQLite (بدون نیاز به Postgres/MinIO)
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTH_MODE"] = "dev"
os.environ["STORAGE_BACKEND"] = "local"  # بدون MinIO؛ فایل‌ها توی یه پوشه‌ی موقت
import tempfile  # noqa: E402
os.environ["LOCAL_STORAGE_DIR"] = tempfile.mkdtemp(prefix="tryon_test_storage_")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402,F401
from app.main import app  # noqa: E402
from app.models.skin_tone_anchor import SkinToneAnchor  # noqa: E402
from scripts.seed_demo_data import SKIN_TONE_ANCHORS  # noqa: E402


@pytest.fixture()
def storage(monkeypatch):
    """MinIO جعلی: آبجکت‌ها توی یه dict می‌مونن."""
    store = {}

    def fake_upload_bytes(data, object_name, content_type="application/octet-stream", bucket_name=None):
        store[object_name] = (data, content_type)
        return object_name

    monkeypatch.setattr("app.routers.seller.upload_bytes", fake_upload_bytes)
    return store


@pytest.fixture()
def client(storage):
    yield from _client()


@pytest.fixture()
def real_storage_client():
    """بدون MinIO جعلی: فایل واقعاً روی دیسک (backend=local) نوشته می‌شه."""
    yield from _client()


def _client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for a in SKIN_TONE_ANCHORS:
        db.add(SkinToneAnchor(**a))
    db.commit()
    db.close()
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


def as_user(user_id):
    return {"X-External-User-Id": user_id}
