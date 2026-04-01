# 🏢 docker部署指南

本指南将引导您完成 FlyTest 后端服务的生产环境部署。系统已改为使用API方式调用嵌入模型，无需本地下载模型文件。


### 🐳 使用 Docker 部署 (推荐)

Docker 提供了环境一致性，是生产环境部署的首选方案。

#### 构建 Docker 镜像
```bash
使用 Docker 部署 (推荐)
# 1. 克隆仓库
git clone https://github.com/MGdaasLab/FlyTest.git
cd FlyTest

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置必要的环境变量

# 3. 启动服务（自动拉取预构建镜像）
docker-compose up -d
```

