FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.lock ./
RUN pip install -r requirements.txt -c requirements.lock && useradd --create-home --uid 10001 cemetery
COPY --chown=cemetery:cemetery . .
RUN python scripts/vendor_bootstrap.py
RUN mkdir -p /app/staticfiles /app/.academic-mail && chown cemetery:cemetery /app/staticfiles /app/.academic-mail && chmod 700 /app/.academic-mail
USER cemetery
EXPOSE 10000
CMD ["python", "scripts/start.py"]
