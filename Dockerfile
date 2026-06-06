FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=server:create_app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["sh", "-c", "SKIP_BACKGROUND_WORKER=true python -m flask --app server:create_app db upgrade && exec env SKIP_BACKGROUND_WORKER=false gunicorn --bind 0.0.0.0:8000 --workers 1 --timeout 120 server.wsgi:app"]
