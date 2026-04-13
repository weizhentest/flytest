ARG PYTHON_BASE_IMAGE=python:3.11-slim

FROM ${PYTHON_BASE_IMAGE}

ARG APT_BASE_URL=http://deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_FALLBACKS=

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app

RUN if [ "$APT_BASE_URL" != "http://deb.debian.org" ]; then \
        sed -i "s|http://deb.debian.org/debian|${APT_BASE_URL}/debian|g; s|http://deb.debian.org/debian-security|${APT_BASE_URL}/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get -o Acquire::Retries=10 update && \
    apt-get -o Acquire::Retries=10 install -y --fix-missing --no-install-recommends \
    adb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN set -eux; \
    install_requirements() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "pip install via $index"; \
        if python -m pip install --retries 5 --timeout 30 -i "$index" -r /app/requirements.txt; then \
          return 0; \
        fi; \
        echo "pip install failed via $index, trying next index..." >&2; \
      done; \
      return 1; \
    }; \
    install_requirements

COPY app /app/app

RUN mkdir -p /app/data

EXPOSE 8010

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
