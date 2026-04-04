# T3FAP

T3FAP 是一个面向影视自动化场景的服务，提供资源搜索、网盘接入、任务调度与插件扩展能力。

## Docker 镜像

- 镜像名称：`T3FAP`
- GHCR 地址：`ghcr.io/qq85423296/t3fap:latest`
- 当前镜像仅包含后端 API 服务，默认监听 `8521`

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
  -v t3fap-storage:/app/storage \
  ghcr.io/qq85423296/t3fap:latest
```

说明：

- 默认会使用容器内 SQLite 数据库
- `t3fap-storage` 用于持久化运行数据和日志
- 访问地址默认是 `http://127.0.0.1:8521`

### 3. 使用 `docker run` 连接 MySQL

```bash
docker run -d --name t3fap \
  -p 8521:8521 \
  -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 \
  -e T3MT_DATABASE_URL="mysql+pymysql://t3mt:change_me@host.docker.internal:3306/t3mt_next?charset=utf8mb4" \
  -v t3fap-storage:/app/storage \
  ghcr.io/qq85423296/t3fap:latest
```

## Docker Compose 部署

仓库已提供 `compose.yaml`，可直接使用：

```bash
docker compose up -d
```

停止服务：

```bash
docker compose down
```

如果需要改成 MySQL，只要把 `compose.yaml` 里的 `T3MT_DATABASE_URL` 改为你的 MySQL 连接串即可。

## 启动验证

```bash
curl http://127.0.0.1:8521/
curl http://127.0.0.1:8521/api/health
```

## 更新镜像

```bash
docker pull ghcr.io/qq85423296/t3fap:latest
docker stop t3fap
docker rm t3fap
docker run -d --name t3fap -p 8521:8521 -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 -v t3fap-storage:/app/storage ghcr.io/qq85423296/t3fap:latest
```
