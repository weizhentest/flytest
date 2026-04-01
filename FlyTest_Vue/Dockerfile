# 第一阶段：构建阶段
ARG NODE_BASE_IMAGE=node:20-alpine
ARG NGINX_BASE_IMAGE=nginx:alpine
FROM ${NODE_BASE_IMAGE} AS builder

ARG NPM_REGISTRY=https://registry.npmjs.org

# 设置工作目录
WORKDIR /app

# 复制 package 文件
COPY package*.json ./

# 设置 npm 源，并同步修正 lock 文件中的 resolved 地址
RUN npm config set registry "${NPM_REGISTRY}" && \
    sed -i \
      -e "s#https://registry\\.npmmirror\\.com/#${NPM_REGISTRY%/}/#g" \
      -e "s#https://registry\\.npmjs\\.org/#${NPM_REGISTRY%/}/#g" \
      package-lock.json

# 安装依赖（npm ci更快更可靠，基于lock文件）
RUN npm ci

# 复制TypeScript配置和构建配置
COPY tsconfig*.json ./
COPY vite.config.ts ./
COPY postcss.config.js ./
COPY tailwind.config.js ./

# 复制源代码
COPY src/ ./src/
COPY public/ ./public/
COPY index.html ./

# 复制生产环境配置
COPY .env.production .env.production

# 构建应用（指定生产模式）
RUN npx vite build --mode production

# 第二阶段：运行阶段
FROM ${NGINX_BASE_IMAGE}

# 复制自定义 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制构建产物到 nginx 的静态文件目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]
