import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """هر تست یه پوشه‌ی data تمیز و موقت داره؛ به پوشه‌ی واقعی src/back/data دست نمی‌زنه."""
    monkeypatch.setenv("TRYON_DATA_DIR", str(tmp_path))
    from app.main import app
    return TestClient(app)
