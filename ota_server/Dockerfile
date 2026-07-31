FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ORBIS_OTA_MANIFEST_DIR=/app/manifests \
    ORBIS_OTA_FIRMWARE_DIR=/app/firmware

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./server.py
COPY manifests ./manifests
RUN mkdir -p /app/firmware && useradd --create-home --uid 10001 orbis && chown -R orbis:orbis /app

USER orbis
EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
