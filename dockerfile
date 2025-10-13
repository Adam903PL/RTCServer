# Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Kod aplikacji
#   - main.py na poziomie /app
#   - cały pakiet src/
#   - statyki (masz już u siebie — więc kopiujemy je do obrazu)
COPY main.py .
COPY src ./src
COPY static ./static

# 3) Logi
RUN mkdir -p /app/logs

EXPOSE 8080

# 4) Healthcheck pod nowe endpointy (pozostaje /health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# 5) Start
CMD ["python", "main.py"]
