# 🖼️ 前端生产环境部署指南

本指南将引导您完成 FlyTest 前端应用的生产环境部署。

## 📦 环境准备

在开始之前，请确保您的开发和部署环境满足以下要求：

- **Node.js**: 版本 18 或更高。
- **包管理器**: `npm` 或 `yarn`。

## 🚀 部署步骤

### 1. 获取项目代码

首先，从代码仓库克隆最新的前端项目代码。

```bash
# 克隆仓库
git clone https://github.com/MGdaasLab/FlyTest.git

# 进入项目目录
cd FlyTest_Vue
```

### 2. 安装依赖

进入项目目录后，使用 `npm` 或 `yarn` 安装项目所需的依赖项。

```bash
npm install
```

### 3. 配置开发环境

在开始本地开发之前，您需要在 `FlyTest_Vue` 根目录下创建一个 `.env` 文件来配置环境变量。这个文件用于指定开发服务器的 API 地址和代理设置。
```bash
cp .env.production .env #创建.env副本使其生效
```
**示例 `.env` 文件:**

```env
# 开发环境配置
# API 基础路径
VITE_API_BASE_URL=/api

# 是否启用代理
VITE_USE_PROXY=true
```

**配置说明:**

- `VITE_API_BASE_URL=/api`: 定义了 API 请求的基础路径。在开发模式下，所有以 `/api` 开头的请求都将被代理到后端服务。
- `VITE_USE_PROXY=true`: 启用 Vite 开发服务器的反向代理功能。这需要配合 `vite.config.js` 中的代理设置，以解决本地开发时的跨域问题。

创建并配置好此文件后，您可以运行 `npm run dev` 来启动本地开发服务器。
