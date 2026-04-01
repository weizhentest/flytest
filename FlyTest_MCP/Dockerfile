# 使用 Python 3.11 官方镜像作为基础镜像
ARG PYTHON_BASE_IMAGE=python:3.11-slim
FROM ${PYTHON_BASE_IMAGE}

ARG APT_BASE_URL=http://deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_FALLBACKS=

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_FALLBACKS=${PIP_INDEX_FALLBACKS}

# 安装系统依赖
RUN if [ "$APT_BASE_URL" != "http://deb.debian.org" ]; then \
        sed -i "s|http://deb.debian.org/debian|${APT_BASE_URL}/debian|g; s|http://deb.debian.org/debian-security|${APT_BASE_URL}/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get -o Acquire::Retries=10 update && apt-get -o Acquire::Retries=10 install -y --fix-missing --no-install-recommends \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（主镜像失败时自动切换到后备源）
RUN set -eux; \
    install_uv() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "pip install uv via $index"; \
        if python -m pip install --no-cache-dir --retries 5 --timeout 30 -i "$index" uv; then \
          return 0; \
        fi; \
        echo "pip install uv failed via $index, trying next index..." >&2; \
      done; \
      return 1; \
    }; \
    install_uv

# 复制依赖文件
COPY requirements.txt .

# 使用 uv 安装 Python 依赖（主镜像失败时自动切换到后备源）
RUN set -eux; \
    install_requirements() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "uv pip install via $index"; \
        if uv pip install --system \
          --default-index "$index" \
          -r requirements.txt; then \
          return 0; \
        fi; \
        echo "uv pip install failed via $index, trying next index..." >&2; \
      done; \
      return 1; \
    }; \
    install_requirements

# 复制supervisord配置
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 复制MCP服务代码（仅复制必要文件）
COPY ms_mcp_api.py /app/
COPY FlyTest_tools.py /app/
COPY playwright-mcp-config.json /app/

# 创建日志目录
RUN mkdir -p /var/log/supervisor

# 暴露两个服务的端口
# ms_mcp_api.py 使用端口 8007
# FlyTest_tools.py 使用端口 8006
EXPOSE 8006 8007

# 使用 supervisord 启动两个服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
