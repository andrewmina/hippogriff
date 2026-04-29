FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# Datadog APM — use ddtrace-run to auto-instrument at startup
# DD_SERVICE, DD_ENV, DD_VERSION injected via K8s env / Admission Controller
ENV DD_TRACE_ENABLED=true \
    DD_LOGS_INJECTION=true \
    DD_RUNTIME_METRICS_ENABLED=true \
    DD_TRACE_SAMPLE_RATE=1.0 \
    DD_PROFILING_ENABLED=true \
    DD_APPSEC_ENABLED=false \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["ddtrace-run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
