FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN addgroup --system app \
    && adduser --system --ingroup app app

COPY --chown=app:app app ./app
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app alembic ./alembic

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
