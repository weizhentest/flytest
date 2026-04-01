---
name: agent-browser-skill
description: 基于 agent-browser CLI 的浏览器自动化工具。提供快照获取、元素交互、截图等功能。推荐用于需要页面快照分析、通过 ref 引用交互元素的场景。
---

# Agent Browser 浏览器自动化

基于 Vercel agent-browser CLI 的浏览器自动化工具，专为 AI Agent 设计。

## ⚠️ 核心工作流：Snapshot + Ref

**禁止猜测选择器！必须先获取 Snapshot，再通过 Ref 操作元素！**

```bash
# 1. 打开页面
agent-browser open http://example.com

# 2. 获取交互元素快照
agent-browser snapshot -i
# 输出示例：
# - heading "Example Domain" [ref=e1] [level=1]
# - button "Submit" [ref=e2]
# - textbox "Email" [ref=e3]
# - link "Learn more" [ref=e4]

# 3. 使用 ref 进行操作
agent-browser click @e2
agent-browser fill @e3 "test@example.com"
agent-browser get text @e1

# 4. 页面变化后重新获取快照
agent-browser snapshot -i
```

## 使用方法

通过 shell 直接调用 `agent-browser` 命令。所有命令都是独立的，会自动连接到后台守护进程管理的浏览器实例。

## 安装要求

```bash
# 全局安装
npm install -g agent-browser

# 下载 Chromium
agent-browser install
```

## 核心命令

### 导航

```bash
agent-browser open <url>      # 打开页面
agent-browser back            # 后退
agent-browser forward         # 前进
agent-browser reload          # 刷新
agent-browser close           # 关闭浏览器
```

### 快照（页面分析）

```bash
agent-browser snapshot            # 完整可访问性树
agent-browser snapshot -i         # 仅交互元素（推荐）
agent-browser snapshot -c         # 紧凑输出
agent-browser snapshot -d 3       # 限制深度为3层
agent-browser snapshot -s "#main" # 范围限定到 CSS 选择器
agent-browser snapshot --json     # JSON 输出（适合程序处理）
```

### 交互操作（使用 @ref）

```bash
agent-browser click @e1           # 点击
agent-browser dblclick @e1        # 双击
agent-browser focus @e1           # 聚焦元素
agent-browser fill @e2 "text"     # 清空并输入
agent-browser type @e2 "text"     # 追加输入（不清空）
agent-browser press Enter         # 按键
agent-browser press Control+a     # 组合键
agent-browser hover @e1           # 悬停
agent-browser check @e1           # 勾选复选框
agent-browser uncheck @e1         # 取消勾选
agent-browser select @e1 "value"  # 选择下拉选项
agent-browser scroll down 500     # 向下滚动 500px
agent-browser scrollintoview @e1  # 滚动到元素可见
agent-browser drag @e1 @e2        # 拖拽
agent-browser upload @e1 file.pdf # 上传文件
```

### 获取信息

```bash
agent-browser get text @e1        # 获取元素文本
agent-browser get html @e1        # 获取 innerHTML
agent-browser get value @e1       # 获取输入框值
agent-browser get attr @e1 href   # 获取属性
agent-browser get title           # 获取页面标题
agent-browser get url             # 获取当前 URL
agent-browser get count ".item"   # 统计匹配元素数量
agent-browser get box @e1         # 获取元素边界框
```

### 状态检查

```bash
agent-browser is visible @e1      # 检查是否可见
agent-browser is enabled @e1      # 检查是否可用
agent-browser is checked @e1      # 检查是否勾选
```

### 截图 & PDF

```bash
agent-browser screenshot              # 截图到标准输出（base64）
agent-browser screenshot ./page.png   # 保存到文件
agent-browser screenshot --full       # 全页面截图
agent-browser pdf output.pdf          # 保存为 PDF
```

### 等待

```bash
agent-browser wait @e1            # 等待元素可见
agent-browser wait 2000           # 等待 2000 毫秒
agent-browser wait --text "成功"   # 等待文本出现
agent-browser wait --url "**/dashboard"  # 等待 URL 匹配
agent-browser wait --load networkidle    # 等待网络空闲
```

### CSS 选择器（也支持）

```bash
agent-browser click "#submit"
agent-browser fill "#email" "test@example.com"
agent-browser find role button click --name "Submit"
```

## 会话管理

多个 AI Agent 可使用不同的浏览器实例：

```bash
# 不同会话
agent-browser --session agent1 open site-a.com
agent-browser --session agent2 open site-b.com

# 或通过环境变量
AGENT_BROWSER_SESSION=agent1 agent-browser click @e1

# 列出活跃会话
agent-browser session list
```

## 截图路径约定

建议统一保存到 `SCREENSHOT_DIR` 环境变量指定的目录：

```bash
SCREENSHOT_DIR=$(pwd)/media/screenshots
agent-browser screenshot ${SCREENSHOT_DIR}/case_11_step1.png
```

## 典型使用场景

### 登录测试

```bash
# 打开登录页
agent-browser open http://192.168.150.114:8913/login

# 获取页面元素
agent-browser snapshot -i
# 输出：
# - textbox "请输入用户名" [ref=e1]
# - textbox "请输入密码" [ref=e2]
# - button "登录" [ref=e3]

# 填写表单
agent-browser fill @e1 "admin"
agent-browser fill @e2 "admin123456"

# 截图
agent-browser screenshot ./step1_filled.png

# 点击登录
agent-browser click @e3

# 等待跳转
agent-browser wait --url "**/dashboard"
agent-browser snapshot -i

# 截图结果
agent-browser screenshot ./step2_result.png

# 关闭浏览器
agent-browser close
```

## 与 playwright-skill 对比

| 特性 | agent-browser-skill | playwright-skill |
|------|---------------------|------------------|
| 调用方式 | 独立 CLI 命令 | node run.js "code" |
| 元素定位 | Snapshot + @ref | CSS 选择器 |
| 状态保持 | 自动守护进程 | 每次启动新浏览器 |
| AI 友好度 | 高（专为 AI 设计） | 中 |
| 代码复杂度 | 简单命令 | 需写 JS 代码 |
