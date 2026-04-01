# FlyTest 快速启动指南

## 🚀 一键启动（开箱即用）

### 1. 准备配置文件

```bash
# 复制环境变量模板
cp .env.example .env
```

### 2. 启动所有服务

```bash
# 一键启动所有服务
docker-compose up -d
```

### 3. 访问系统

- **前端界面**: http://localhost:8913
  - 默认账号：`admin`
  - 默认密码：`admin123456`

**就这么简单！系统已经可以使用，包括MCP服务。**

## ✨ 系统自动配置了什么？

首次启动时，系统会自动创建：

### 1. 默认API Key
- **Key值**: `flytest-default-mcp-key-2025`
- **用途**: MCP服务访问后端API

### 2. 默认MCP配置
系统自动添加两个MCP工具配置：
- **FlyTest-Tools** (http://mcp:8006) - 测试用例管理
- **Playwright-MCP** (http://playwright-mcp:8931/mcp) - 浏览器自动化

✅ **开发环境**：直接使用，无需任何配置  
⚠️ **生产环境**：建议更换为安全的自定义Key

## 🔒 生产环境：更换API Key（推荐）

### 步骤1：登录后台

访问 http://localhost:8913 并登录

### 步骤2：创建新的API Key

1. 进入：【系统管理】>【API密钥】
2. **删除**默认Key（名称：Default MCP Key）
3. 点击【创建API Key】
4. 填写名称并保存
5. **复制生成的Key**（只显示一次）

### 步骤3：更新配置

编辑 `.env` 文件：

```bash
# 替换为你的新Key
FLYTEST_API_KEY=你复制的新Key
```

### 步骤4：重启MCP服务

```bash
docker-compose restart mcp
```

## 📝 服务访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost:8913 | Vue前端应用 |
| 后端API | http://localhost:8912 | Django REST API |
| Redis | localhost:8911 | 缓存和消息队列 |
| MCP服务 | http://localhost:8914 | FlyTest MCP工具 |
| MS MCP | http://localhost:8915 | MS测试平台集成 |
| Playwright | http://localhost:8916 | 浏览器自动化 |

## ❓ 常见问题

### 1. 服务启动失败？

```bash
# 查看日志
docker-compose logs

# 重新启动
docker-compose down
docker-compose up -d
```

### 2. 如何验证MCP服务是否正常？

```bash
# 测试API Key是否有效
curl -H "X-API-Key: flytest-default-mcp-key-2025" \
  http://localhost:8912/api/projects/

# 应该返回项目列表JSON
```

### 3. 忘记了自定义的API Key？

删除旧Key，创建新Key即可。系统支持多个Key并存。

### 4. 首次启动很慢？

首次启动需要拉取镜像，可能需要几分钟。后续启动会快很多。

## 🛑 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据（谨慎使用）
docker-compose down -v
```

## 📚 更多文档

- [API Key 配置详解](./FlyTest_MCP/API_KEY_SETUP.md)
- [MCP 服务文档](./FlyTest_MCP/README.md)

---

**提示：** 默认API Key的设计让开发环境开箱即用，生产环境请务必更换！
