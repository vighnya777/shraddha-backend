FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /srv/shraddha
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir . \
    && useradd --system --no-create-home --uid 10001 shraddha
USER shraddha
EXPOSE 8000
# gthread workers keep long SSE streams alive; the heartbeat is handled by the arbiter thread.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 8 --worker-class gthread --timeout 120 --graceful-timeout 30 --access-logfile - app.main:app"]
