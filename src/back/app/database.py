import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/virtual_tryon"
)

if DATABASE_URL.startswith("sqlite"):
    # فقط برای تست/توسعه‌ی محلی: یه اتصال واحد نگه می‌داره تا دیتابیس In-Memory
    # بین درخواست‌های مختلف (thread های متفاوت TestClient) از دست نره.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # pool_pre_ping از خطای "stale connection" بعد از دوره‌ی بی‌کاری جلوگیری می‌کنه
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

