# T3FAP

T3MT Film Auto Platform，简称 T3FAP，是一个面向影视自动化场景的服务，提供资源发现、网盘接入、任务编排与插件扩展能力。

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

## Docker 镜像

- 镜像名称：`ghcr.io/qq85423296/t3fap:latest`
- 当前发布镜像默认统一监听端口：`8521`
- 默认页面地址：`http://127.0.0.1:8521`
- 默认健康检查地址：`http://127.0.0.1:8521/api/health`

### 端口说明

当前生成镜像的默认端口是 `8521`。这个结论来自主项目 `t3mt-next` 的 Docker 构建配置：

- `Dockerfile` 中声明了 `EXPOSE 8521`
- 容器启动命令使用的是 `uvicorn apps.api.main:app --host 0.0.0.0 --port 8521`

如果你在旧代码、旧脚本或历史文档里看到 `8000`，请把它视为历史本地默认值或旧回退值，不代表当前发布镜像的默认对外端口。

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

- 默认使用容器内 SQLite 数据库
- `./data` 用于持久化数据库、日志和运行数据
- `./downloads` 用于持久化下载目录、STRM 文件和本地目录插件可见内容
- 页面访问地址默认是 `http://127.0.0.1:8521`
- API 健康检查地址是 `http://127.0.0.1:8521/api/health`
- 如果要给飞牛、Emby、Jellyfin 等媒体库读取 STRM，请把 `T3MT_PUBLIC_BASE_URL` 改成播放器实际访问站点时使用的域名或局域网 IP，例如 `http://192.168.1.20:8521`，不要保留为 `127.0.0.1`

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

仓库已提供 [compose.yaml](./compose.yaml)，可直接使用：

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
- `./downloads`：下载文件、STRM 文件、官方/本地目录相关输出

## 启动验证

```bash
curl http://127.0.0.1:8521/
curl http://127.0.0.1:8521/api/health
```

预期：

- `/` 返回 T3FAP 页面
- `/api/health` 返回 JSON 健康检查结果

## 第三方插件开发文档

这个仓库同时作为第三方插件示例仓库。想要开发新的市场插件、任务插件、网盘插件或其他扩展插件，可以直接阅读下面这些文档：

- [插件开发总览](./docs/plugins/README.md)
- [插件规范与规则](./docs/plugins/rules.md)
- [最小 catalog 插件示例](./docs/plugins/examples/minimal-catalog-plugin.md)
- [最小 task 插件示例](./docs/plugins/examples/minimal-task-plugin.md)
- [最小 drive 插件示例](./docs/plugins/examples/minimal-drive-plugin.md)

当前仓库中的 [plugins](./plugins) 目录已经包含多份可直接参考的市场资源插件实现，适合在此基础上继续扩展第三方来源。

## 更新镜像

```bash
docker pull ghcr.io/qq85423296/t3fap:latest
docker stop t3fap
docker rm t3fap
docker run -d --name t3fap -p 8521:8521 -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 -v ./data:/app/storage -v ./downloads:/app/backend/downloads ghcr.io/qq85423296/t3fap:latest
```
