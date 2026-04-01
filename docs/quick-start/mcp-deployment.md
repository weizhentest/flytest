# MCP 测试工具部署文档

## 项目概述

本项目包含两个 MCP (Model Context Protocol) 工具服务：

- **ms_mcp_api.py** - MS测试用例工具，提供与MS测试平台的API交互功能
- **FlyTest_tools.py** - FlyTest 测试用例工具，提供本地测试用例管理功能


## 注意！！！

- **Docker 部署**：API Key 会在容器启动时自动初始化，默认 Key 为 `flytest-default-mcp-key-2025`
- **源码部署**：需要在数据库迁移完成后，手动执行 `python manage.py init_admin` 初始化，默认 Key 同上

## 安装部署

### 1. 创建虚拟环境并安装依赖

```bash
cd FlyTest_MCP

cp .env.example .env # 复制env副本使其生效

# 创建虚拟环境
uv venv --python 3.11

# 激活虚拟环境
# Linux/macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 安装依赖
uv pip install -r requirements.txt
```

### 2. 启动服务

#### 启动测试用例工具

```bash
uv run python FlyTest_tools.py
```


## 功能说明

### 测试用例工具功能

- 获取项目列表
- 获取模块信息
- 获取用例等级
- 获取用例列表和详情
- 保存操作截图
- 保存功能测试用例
## 配置说明

#### FlyTest 测试用例工具 (FlyTest_tools.py)

- **服务端口**: 8006
- **API地址**: 后端服务ip+端口
- **API密钥**: 已内置在代码中

## 注意事项

1. 确保目标API服务可访问
2. 检查防火墙设置，确保端口8006和8007可用
3. 如需修改配置，请直接编辑源码中的配置参数
4. 建议在生产环境中使用环境变量管理敏感信息

## 故障排除

- 如果服务启动失败，检查端口是否被占用
- 如果API调用失败，检查网络连接和API地址
- 查看控制台输出获取详细错误信息