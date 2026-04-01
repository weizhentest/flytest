# 项目介绍

**FlyTest** （/wɑːtest/）是由 **山东麦港数据系统有限公司** 旗下**麦港实验室（MGdaas Lab）** 推出的开源项目，隶属于 **WHart** 系列。该系列聚焦于为开源社区贡献优质产品与组件，旨在通过技术共享赋能行业生态，推动相关领域的技术创新与应用发展。

**FlyTest** 是基于 **Django REST Framework** 与现代大模型技术打造的 **AI 驱动测试自动化平台**。平台聚合自然语言理解、知识库检索与嵌入搜索能力，结合 **LangChain** 与 **MCP（Model Context Protocol）** 工具调用，实现从需求到可执行测试用例的自动化生成与管理，帮助测试团队提升效率与覆盖率。





## 核心价值
- 智能用例生成：从需求或对话中自动生成结构化测试用例（测试步骤、前置条件、输入、期望结果、优先级等）。
- 知识感知：支持从文档、API 文档与知识库抽取上下文，使用嵌入增强模型的理解与检索精度。
- 自动评审与建议：基于模型的需求评审与风险提示，辅助测试策略制定与优先级判断。
- 用例管理与执行：集中管理用例、执行记录、自动截屏与执行结果上报，便于审计与回溯。
- 自动化脚本生成：基于测试用例自动生成 Playwright 自动化脚本，支持一键执行与调试，降低自动化测试门槛。
- 可扩展与可定制：支持接入自定义模型、第三方服务与扩展工具链（LangChain、HuggingFace 等）。



## 技术栈
- 后端：Django, Django REST Framework
- AI：大语言模型（LLM）、LangChain、多种嵌入服务（OpenAI、Azure OpenAI、Ollama等）
- 存储：示例使用 SQLite，可切换为 PostgreSQL / MySQL
- 前端：Vue + Vite（详见 `FlyTest_Vue`）

## 快速上手（简要）
1. 克隆仓库并进入项目根目录：
   ```bash
   git clone https://github.com/MGdaasLab/FlyTest.git
   cd FlyTest
   ```
2. 使用 Docker Compose 启动所有服务：
   ```bash
   docker-compose up -d
   ```
3. 等待服务启动完成后，访问以下地址：
   - 前端界面：http://localhost:8913
   - 默认管理员账号：admin / admin123456
4. 如需自定义配置（如数据库密码、管理员账号等），请在项目根目录创建 `.env` 文件进行设置。

> 详细配置与部署说明请参阅根目录 README。

## 界面与功能预览
以下截图展示了平台的典型界面与功能，供快速浏览：

### 登录页面
![登录页面](/img/image-a1.png)

### 知识库提取与管理
![知识库管理](/img/image-a18.png)

### AI 对话与测试用例生成
![AI 对话与测试用例生成](/img/image-a6.png)

### 测试用例管理
![测试用例管理](/img/image-a7.png)

### 生成用例详情
![生成用例详情](/img/image-a8.png)

### 测试执行与自动截屏
![测试执行](/img/image-a19.png)
![自动截屏](/img/image-a20.png)

### UI自动化测试
![执行结果](/img/image-a22.png)
![报告详情](/img/image-a23.png)


### AI 驱动的需求评审与报告
![AI 需求评审](/img/image-a15.png)
![报告打分与建议](/img/image-a5.png)


（更多细节、API 与部署说明请查阅仓库中的 docs 目录及各模块 README）

