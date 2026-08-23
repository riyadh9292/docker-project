FROM python:3.12-slim

WORKDIR /app

COPY app.py .

# Volume mount point for persistent metrics log
RUN mkdir -p /data

EXPOSE 6000

# Basic container-level healthcheck hitting our own /health endpoint
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6000/health')" || exit 1

CMD ["python", "app.py"]
