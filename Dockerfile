FROM python:3.11-slim
WORKDIR /app

RUN useradd --create-home --shell /bin/bash alcove

COPY pyproject.toml README.md ./
COPY alcove/ alcove/
COPY scripts/ scripts/
COPY data/ data/
RUN pip install --no-cache-dir .

USER alcove
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["alcove", "serve", "--host", "0.0.0.0"]
