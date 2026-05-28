FROM python:3.11-slim-bullseye

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
    rm -f /etc/apt/apt.conf.d/docker-clean || true && \
    apt-get -o Acquire::Retries=10 update && \
    apt-get -o Acquire::Retries=10 install -y --fix-missing --no-install-recommends \
    build-essential \
    git \
    curl \
    supervisor \
    antiword \
    catdoc \
    && rm -rf /var/lib/apt/lists/*

COPY FlyTest_Django/requirements.txt /app/requirements.txt

RUN set -eux; \
    install_requirements() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "pip install via $index"; \
        if python -m pip install --retries 5 --timeout 60 -i "$index" -r /app/requirements.txt; then \
          return 0; \
        fi; \
      done; \
      return 1; \
    }; \
    install_requirements

COPY FlyTest_Django/manage.py /app/
COPY FlyTest_Django/accounts/ /app/accounts/
COPY FlyTest_Django/api_automation/ /app/api_automation/
COPY FlyTest_Django/api_keys/ /app/api_keys/
COPY FlyTest_Django/app_automation_permissions/ /app/app_automation_permissions/
COPY FlyTest_Django/data_factory/ /app/data_factory/
COPY FlyTest_Django/flytest_django/ /app/flytest_django/
COPY FlyTest_Django/knowledge/ /app/knowledge/
COPY FlyTest_Django/langgraph_integration/ /app/langgraph_integration/
COPY FlyTest_Django/mcp_tools/ /app/mcp_tools/
COPY FlyTest_Django/orchestrator_integration/ /app/orchestrator_integration/
COPY FlyTest_Django/projects/ /app/projects/
COPY FlyTest_Django/prompts/ /app/prompts/
COPY FlyTest_Django/requirements/ /app/requirements/
COPY FlyTest_Django/site_notifications/ /app/site_notifications/
COPY FlyTest_Django/skills/ /app/skills/
COPY FlyTest_Django/testcase_templates/ /app/testcase_templates/
COPY FlyTest_Django/testcases/ /app/testcases/
COPY FlyTest_Django/ui_automation/ /app/ui_automation/
COPY FlyTest_Django/THIRD_PARTY_NOTICES.md /app/THIRD_PARTY_NOTICES.md
COPY deploy/production/backend.entrypoint.sh /app/entrypoint.sh
COPY deploy/production/backend.supervisord.conf /app/supervisord.conf

RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh && \
    mkdir -p /app/data /var/log

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
