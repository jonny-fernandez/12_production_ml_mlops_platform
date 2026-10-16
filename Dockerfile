# Project 12 CP7 local container configuration (not a production release).
# Use the same Python minor version as the parity-tested Project 12 venv.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache

WORKDIR /app

# Use a serving-only dependency set. Do not install the entire R&D/AWS stack.
COPY requirements-container.txt /app/requirements-container.txt
RUN python -m pip install --no-cache-dir -r /app/requirements-container.txt \
    && python -m pip check \
    && groupadd --gid 10001 mlapp \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin mlapp

# Never COPY .env, the original dataset, databases or model artifacts into this image.
COPY --chown=10001:10001 src /app/src

USER 10001:10001
EXPOSE 8000

# CP7 liveness only; readiness/model status is addressed at CP8.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "from urllib.request import urlopen; r=urlopen('http://127.0.0.1:8000/health',timeout=3); assert r.status == 200" || exit 1

# Application middleware emits allowlisted JSON metadata logs. Disable Uvicorn
# access logs so request URLs (including sensitive query strings) are not logged.
CMD ["uvicorn", "mlops_platform.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
