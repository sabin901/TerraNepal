FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NEPAL_ARCHIVE_ROOT=/data/archive NEPAL_STATE_ROOT=/data/state
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 lab && useradd --uid 10001 --gid lab --create-home lab \
    && mkdir -p /data/archive /data/state && chown -R lab:lab /data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY disaster_lab ./disaster_lab
COPY disaster_archive ./disaster_archive
COPY planning ./planning
COPY source-ledger.json .
USER 10001:10001
EXPOSE 8765
CMD ["python", "disaster_lab/production.py", "--host", "0.0.0.0"]
