FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

ENV DD_TRACE_ENABLED=true \
    DD_LOGS_INJECTION=true \
    DD_RUNTIME_METRICS_ENABLED=true \
    DD_TRACE_SAMPLE_RATE=1.0 \
    DD_PROFILING_ENABLED=true \
    DD_APPSEC_ENABLED=true \
    DD_DBM_PROPAGATION_MODE=full \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["ddtrace-run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
