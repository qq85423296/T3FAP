# T3FAP

T3MT Film Auto Platform，简称 `T3FAP`，是一个面向影视自动化场景的服务，提供资源发现、网盘接入、任务编排与插件扩展能力。

## 官方插件库

当前仓库同时承载两类内容：

- `T3FAP` Docker 镜像的公开部署入口
- 官方远程插件市场目录，位于 [`plugins/`](./plugins)

仓库地址：

- `https://github.com/qq85423296/T3FAP`

插件中心中可直接填写：

- `https://github.com/qq85423296/T3FAP`
- `https://github.com/qq85423296/T3FAP/tree/main/plugins`

当前已适配的资源探索插件：

- `catalog.cctv`
- `catalog.migu`
- `catalog.bilibili`
- `catalog.bangumi_daily`
- `catalog.mango`
- `catalog.tencent`

## Docker 镜像

- 镜像名称：`ghcr.io/qq85423296/t3fap:latest`
- 默认对外端口：`8521`
- 默认页面地址：`http://127.0.0.1:8521`
- 默认健康检查地址：`http://127.0.0.1:8521/api/health`

## 推荐部署方式

仓库已提供可直接运行的 [`compose.yaml`](./compose.yaml)，默认启动：

- `t3fap` 应用容器
- `mysql:8.0` 数据库容器

本地持久化目录：

- `./mysql-data`：MySQL 数据文件
- `./data`：应用运行数据、日志、包缓存
- `./downloads`：下载文件、STRM 输出和本地目录相关输出

### 1. 准备环境变量

先复制示例环境文件，再按你的实际环境修改：

```bash
cp .env.example .env
```

Windows PowerShell 也可以使用：

```powershell
Copy-Item .env.example .env
```

至少建议检查这些值：

- `T3MT_PUBLIC_BASE_URL`
- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`

如果浏览器、Emby、Jellyfin 或其他播放器通过局域网 IP 或域名访问 T3FAP，请把 `T3MT_PUBLIC_BASE_URL` 改成真实访问地址，不要保留为 `127.0.0.1`。

### 2. 启动服务

先创建目录：

```bash
mkdir -p mysql-data data downloads
```

再启动：

```bash
docker compose up -d
```

应用会先等待 MySQL 就绪，然后执行 `alembic upgrade head`，最后再启动 API 服务。

### 3. 启动验证

```bash
curl http://127.0.0.1:8521/
curl http://127.0.0.1:8521/api/health
```

预期：

- `/` 返回 T3FAP 页面
- `/api/health` 返回 JSON 健康检查结果

## 数据持久化说明

用户数据不会只存在容器层里。

- MySQL 数据保存在 `./mysql-data`
- 应用运行数据保存在 `./data`
- 下载文件和输出文件保存在 `./downloads`

因为这些路径都映射到宿主机目录，所以只要保留这些目录，删除并重建容器也不会丢失用户数据。

不建议在正常升级时使用：

```bash
docker compose down -v
```

当前仓库默认使用的是本地目录挂载，不是 named volume，但养成避免 `-v` 的习惯更稳妥，后续如果你改成 volume 部署时也不容易误删数据。

## 更新镜像

```bash
docker compose pull
docker compose up -d
```

建议在大版本升级前备份：

- `./mysql-data`
- `./data`
- `./downloads`

## SQLite 回退方案

SQLite 仍然支持，但现在只建议用于快速演示、临时测试或轻量单机场景，不再作为默认部署方式。

如果确实想继续使用 SQLite，可以手动执行：

```bash
docker run -d --name t3fap \
  -p 8521:8521 \
  -e T3MT_PUBLIC_BASE_URL=http://127.0.0.1:8521 \
  -e T3MT_DATABASE_URL=sqlite:////app/storage/runtime/t3mt-next.db \
  -v ./data:/app/storage \
  -v ./downloads:/app/backend/downloads \
  ghcr.io/qq85423296/t3fap:latest
```

长期运行仍推荐 MySQL。

## 第三方插件开发文档

这个仓库同时也可以作为第三方插件示例仓库。想要开发新的市场插件、任务插件、网盘插件或其他扩展插件，可以先阅读这些文档：

- [插件开发总览](./docs/plugins/README.md)
- [插件规范与规则](./docs/plugins/rules.md)
- [最小 catalog 插件示例](./docs/plugins/examples/minimal-catalog-plugin.md)
- [最小 task 插件示例](./docs/plugins/examples/minimal-task-plugin.md)
- [最小 drive 插件示例](./docs/plugins/examples/minimal-drive-plugin.md)

当前仓库中的 [`plugins`](./plugins) 目录已经包含多份可直接参考的市场资源插件实现，适合在此基础上继续扩展第三方来源。
