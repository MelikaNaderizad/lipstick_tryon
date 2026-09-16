from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (import registers all models on Base.metadata)
from app.database import get_db
from app.routers import auth, seller

app = FastAPI(title="Virtual Try-On API")

app.include_router(auth.router)
app.include_router(seller.router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Simple liveness + DB connectivity check."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # pragma: no cover
        db_status = f"error: {exc}"
    return {"status": "ok", "database": db_status}
