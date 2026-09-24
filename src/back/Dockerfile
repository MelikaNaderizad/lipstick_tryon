FROM python:3.12-slim

WORKDIR /app

# mediapipe (و opencv زیرش) روی ایمیج slim به این کتابخانه‌های سیستمی نیاز دارن؛
# بدونشون موقع import mediapipe با خطای libGL.so.1 یا مشابه کرش می‌کنه.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
