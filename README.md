# T3FAP

T3FAP 是 `T3` 项目的公开说明仓库，用于提供项目简介、Docker 安装方法和基础使用说明。

## 仓库分工

- 私有仓库 `T3`：保存项目源码、测试和构建工作流，并负责触发 Docker 构建
- 公开仓库 `T3FAP`：仅保留项目简介、镜像安装方法与使用文档

## Docker 镜像

- 镜像名称：`T3FAP`
- GHCR 地址：`ghcr.io/qq85423296/t3fap:latest`
- 当前镜像仅包含后端 API 服务，默认监听 `8521`

## 安装与启动

### 1. 拉取镜像

```bash
docker pull ghcr.io/qq85423296/t3fap:latest
```

### 2. 默认方式启动

```bash
docker run -d --name t3fap \
  -p 8521:8521 \
  -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 \
  -v t3fap-storage:/app/storage \
  ghcr.io/qq85423296/t3fap:latest
```

### 3. 使用 MySQL 启动

```bash
docker run -d --name t3fap \
  -p 8521:8521 \
  -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 \
  -e T3MT_DATABASE_URL="mysql+pymysql://t3mt:change_me@host.docker.internal:3306/t3mt_next?charset=utf8mb4" \
  -v t3fap-storage:/app/storage \
  ghcr.io/qq85423296/t3fap:latest
```

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
