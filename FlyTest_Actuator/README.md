# UI自动化执行器 (FlyTest Actuator)

独立的UI自动化执行器服务，通过WebSocket连接Django后端，接收并执行自动化测试任务。

## 架构设计


```
┌─────────────┐     WebSocket      ┌──────────────────┐
│   Django    │ ◄────────────────► │   Actuator       │
│   Backend   │                    │   (执行器)        │
│             │                    │                  │
│ - Consumer  │ ◄─ 发送任务 ────── │ - WebSocketClient│
│ - 任务分发   │ ◄─ 返回结果 ────── │ - TaskConsumer   │
└─────────────┘                    │ - Executor       │
                                   └──────────────────┘
                                          │
                                          ▼
                                   ┌──────────────────┐
                                   │  Playwright      │
                                   │  (浏览器自动化)   │
                                   └──────────────────┘
```

## 通信协议

### 消息格式 (SocketDataModel)
```json
{
    "code": 200,
    "msg": "success",
    "user": "username",
    "is_notice": 2,
    "data": {
        "func_name": "u_test_case",
        "func_args": {
            "case_id": 1
        }
    }
}
```

### 支持的任务类型
- `u_page_steps` - 执行页面步骤
- `u_test_case` - 执行测试用例
- `u_test_case_batch` - 批量执行用例
- `u_stop_execution` - 停止执行
- `u_step_result` - 步骤执行结果
- `u_case_result` - 用例执行结果

## 安装

```bash
cd FlyTest_Actuator
pip install -r requirements.txt
```

## 使用

### 基本启动
```bash
python main.py
```

### 指定服务器地址
```bash
python main.py --server ws://192.168.1.100:8000/ws/ui/actuator/
```

### 指定执行器ID
```bash
python main.py --id actuator-01 --server ws://localhost:8000/ws/ui/actuator/
```

### 完整参数
```bash
python main.py \
    --server ws://localhost:8000/ws/ui/actuator/ \
    --api http://localhost:8000 \
    --id my-actuator \
    --log-level DEBUG
```

## 参数说明

| 参数 | 短参数 | 默认值 | 说明 |
|------|--------|--------|------|
| --server | -s | ws://localhost:8000/ws/ui/actuator/ | WebSocket服务器地址 |
| --api | -a | http://localhost:8000 | API服务器地址 |
| --id | -i | actuator-{pid} | 执行器唯一标识 |
| --log-level | -l | INFO | 日志级别 |

## 工作流程

1. **连接服务器**: 执行器启动后通过WebSocket连接Django后端
2. **等待任务**: 监听来自服务器的执行任务
3. **获取详情**: 通过REST API获取用例/步骤详细信息
4. **生成脚本**: 将步骤配置转换为Playwright代码
5. **执行测试**: 调用Playwright执行浏览器自动化
6. **返回结果**: 通过WebSocket将执行结果发送回服务器

## 打包成独立 EXE

执行器支持打包成独立可执行文件，方便分发部署。

### 安装打包依赖

```bash
# 使用 uv
uv pip install pyinstaller

# 或使用 pip
pip install pyinstaller
```

### 执行打包

```bash
cd FlyTest_Actuator
uv run python build_exe.py
```

### 输出目录

```
dist/FlyTest_Actuator/
├── FlyTest_Actuator.exe  # 主程序
├── config.toml             # 配置文件
├── start.bat               # GUI模式启动脚本
├── start_no_gui.bat        # 无GUI模式启动脚本
├── browsers/               # Playwright浏览器（首次运行自动下载）
└── data/                   # 数据目录
    ├── browser/            # 浏览器用户数据
    ├── screenshots/        # 截图
    └── traces/             # Trace文件
```

### 使用说明

1. 将 `dist/FlyTest_Actuator/` 目录复制到目标机器
2. 编辑 `config.toml` 配置服务器地址和账号
3. 双击 `start.bat` 启动（GUI模式）或 `start_no_gui.bat`（无GUI模式）

**首次运行**：
- 首次运行会自动下载 Chromium 浏览器（约 150MB）
- 浏览器会下载到 `browsers/` 目录
- 后续运行无需重复下载

## 分布式部署

执行器支持分布式部署，多个执行器可以同时连接到一个Django后端：

```bash
# 机器A
python main.py --id actuator-machine-a --server ws://server:8000/ws/ui/actuator/

# 机器B  
python main.py --id actuator-machine-b --server ws://server:8000/ws/ui/actuator/

# 机器C
python main.py --id actuator-machine-c --server ws://server:8000/ws/ui/actuator/
```

服务器会自动将任务分发给可用的执行器。

## 文件说明

```
FlyTest_Actuator/
├── main.py              # 主入口，启动执行器
├── models.py            # 消息模型定义
├── websocket_client.py  # WebSocket客户端
├── consumer.py          # 任务消费者
├── executor.py          # Playwright执行引擎
├── browser_installer.py # 浏览器安装检查模块
├── build_exe.py         # 打包脚本
├── actuator.spec        # PyInstaller配置
├── requirements.txt     # 依赖
└── README.md            # 说明文档
```
