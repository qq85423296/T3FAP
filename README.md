# T3FAP

T3MT Film Auto Platform，简称 T3FAP，是一个面向影视自动化场景的服务，提供资源搜索、网盘接入、任务调度与插件扩展能力。

## 官方插件库

当前仓库同时承载 T3FAP 的部署说明和官方远程插件市场目录，`plugins/` 下的内容可以直接作为 `t3` 插件中心的远程仓库来源使用。

仓库地址：

- `https://github.com/qq85423296/T3FAP`

插件中心中可直接填写：

- `https://github.com/qq85423296/T3FAP`
- `https://github.com/qq85423296/T3FAP/tree/main/plugins`

当前已适配的资源探索插件：

- `catalog.cctv`：CCTV 探索
- `catalog.migu`：咪咕视频探索
- `catalog.bilibili`：哔哩哔哩探索
- `catalog.bangumi_daily`：Bangumi 每日放送探索
- `catalog.mango`：芒果 TV 探索
- `catalog.tencent`：腾讯视频探索

说明：

- 以上插件基于 `DDSRem-Dev/MoviePilot-Plugins` 的探索能力重新适配为 `t3` 的 `catalog` 插件协议。
- 适配后可在资源中心直接浏览各平台榜单/目录数据，并继续转交到现有资源动作体系。

## Docker 镜像

- 镜像名称：`T3FAP`
- GHCR 地址：`ghcr.io/qq85423296/t3fap:latest`
- 当前镜像已内置前端页面和后端 API，统一监听 `8521`

## 快速开始

### 1. 拉取镜像

```bash
docker pull ghcr.io/qq85423296/t3fap:latest
```

### 2. 使用 `docker run` 启动

```bash
docker run -d --name t3fap \
  -p 8521:8521 \
  -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 \
  -v ./data:/app/storage \
  -v ./downloads:/app/backend/downloads \
  ghcr.io/qq85423296/t3fap:latest
```

说明：

- 默认会使用容器内 SQLite 数据库
- `./data` 用于持久化数据库、日志和运行数据
- `./downloads` 用于持久化下载目录、STRM 文件和本地目录插件可见内容
- 页面访问地址默认是 `http://127.0.0.1:8521`
- API 健康检查地址是 `http://127.0.0.1:8521/api/health`

### 3. 使用 `docker run` 连接 MySQL

```bash
docker run -d --name t3fap \
  -p 8521:8521 \
  -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 \
  -e T3MT_DATABASE_URL="mysql+pymysql://t3mt:change_me@host.docker.internal:3306/t3mt_next?charset=utf8mb4" \
  -v ./data:/app/storage \
  -v ./downloads:/app/backend/downloads \
  ghcr.io/qq85423296/t3fap:latest
```

## Docker Compose 部署

仓库已提供 `compose.yaml`，可直接使用：

```bash
mkdir -p data downloads
docker compose up -d
```

停止服务：

```bash
docker compose down
```

如果需要改成 MySQL，只要把 `compose.yaml` 里的 `T3MT_DATABASE_URL` 改为你的 MySQL 连接串即可。

目录说明：

- `./data`：数据库、日志、运行状态
- `./downloads`：下载文件、STRM 文件、官方本地目录内容

## 启动验证

```bash
curl http://127.0.0.1:8521/
curl http://127.0.0.1:8521/api/health
```

预期：

- `/` 返回 T3FAP 页面
- `/api/health` 返回 JSON 健康检查结果

## 更新镜像

```bash
docker pull ghcr.io/qq85423296/t3fap:latest
docker stop t3fap
docker rm t3fap
docker run -d --name t3fap -p 8521:8521 -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 -v ./data:/app/storage -v ./downloads:/app/backend/downloads ghcr.io/qq85423296/t3fap:latest
```
