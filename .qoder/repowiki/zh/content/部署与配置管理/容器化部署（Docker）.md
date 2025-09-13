# 容器化部署（Docker）

<cite>
**本文档引用的文件**  
- [pyproject.toml](file://pyproject.toml)
- [app.py](file://src/app.py)
- [README.md](file://README.md)
- [README_DEPENDENCIES.md](file://README_DEPENDENCIES.md)
</cite>

## 目录

1. [简介](#简介)
2. [项目结构](#项目结构)
3. [Docker多阶段构建](#docker多阶段构建)
4. [Docker Compose集成MySQL与Nginx](#docker-compose集成mysql与nginx)
5. [Docker镜像构建与运行](#docker镜像构建与运行)
6. [健康检查与环境变量配置](#健康检查与环境变量配置)
7. [一键部署说明](#一键部署说明)

## 简介

本项目 `glzx-xmt` 是一个基于 Flask 的摄影比赛投票管理系统，支持用户注册、照片上传、审核、投票及排行榜等功能。系统采用三级权限管理，支持 MySQL 和 SQLite 两种数据库模式。本文档旨在通过 `pyproject.toml` 中的依赖声明和 `app.py` 的应用入口，实现项目的容器化部署，提供完整的 Docker 多阶段构建方案、`docker-compose.yml` 集成配置，以及一键部署到容器环境的完整流程。

**Section sources**
- [pyproject.toml](file://pyproject.toml#L1-L51)
- [README.md](file://README.md#L1-L116)

## 项目结构

项目采用模块化结构，核心代码位于 `src/` 目录，静态资源和模板分别存放于 `static/` 和 `templates/` 目录。主应用入口为 `src/app.py`，使用 Flask 框架，通过环境变量灵活配置数据库连接。

```
.
├── src/
│   ├── app.py            # Flask主应用入口
│   ├── app_test.py       # SQLite测试版本
│   └── watermark_cache.py
├── static/               # 静态资源（JS、CSS、图片）
├── templates/            # HTML模板文件
├── pyproject.toml        # 依赖声明与项目元信息
├── README.md             # 项目说明
└── README_DEPENDENCIES.md # 依赖安装说明
```

**Section sources**
- [pyproject.toml](file://pyproject.toml#L1-L51)
- [README.md](file://README.md#L1-L116)

## Docker多阶段构建

为减小最终镜像体积，采用多阶段构建策略。第一阶段为构建阶段，安装所有依赖并编译；第二阶段为运行阶段，仅复制必要的源码和依赖，确保镜像轻量化。

```Dockerfile
# 多阶段构建：减小镜像体积
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY pyproject.toml .

# 安装构建依赖
RUN pip install --no-cache-dir hatchling

# 安装项目依赖（不包含开发依赖）
RUN pip install --no-cache-dir \
    Flask \
    Flask-SQLAlchemy \
    Pillow \
    PyMySQL \
    Werkzeug \
    pandas \
    openpyxl

# 第二阶段：运行环境
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装运行时依赖（与builder阶段一致）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# 复制源码
COPY src/ src/
COPY static/ static/
COPY templates/ templates/

# 暴露服务端口
EXPOSE 5000

# 设置启动命令
CMD ["python", "src/app.py"]
```

**Section sources**
- [pyproject.toml](file://pyproject.toml#L1-L51)
- [app.py](file://src/app.py#L1-L1902)

## Docker Compose集成MySQL与Nginx

使用 `docker-compose.yml` 实现 MySQL 数据库和 Nginx 反向代理的集成，支持环境变量注入和数据卷持久化。

```yaml
version: '3.8'

services:
  db:
    image: mysql:8.0
    container_name: glzx-xmt-db
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: glzx_xmt
      MYSQL_USER: ${DB_USER:-user}
      MYSQL_PASSWORD: ${DB_PASSWORD:-password}
    volumes:
      - db_data:/var/lib/mysql
    ports:
      - "3306:3306"
    command: --default-authentication-plugin=mysql_native_password

  web:
    build: .
    container_name: glzx-xmt-web
    restart: always
    environment:
      DATABASE_URL: mysql+pymysql://${DB_USER:-user}:${DB_PASSWORD:-password}@db:3306/glzx_xmt?charset=utf8mb4
      FLASK_RUN_PORT: 5000
      SECRET_KEY: ${SECRET_KEY:-your-secret-key-here}
      SQLALCHEMY_TRACK_MODIFICATIONS: "false"
    depends_on:
      - db
    ports:
      - "5000:5000"
    volumes:
      - ./static/uploads:/app/static/uploads
      - ./static/thumbs:/app/static/thumbs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: glzx-xmt-nginx
    restart: always
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - web

volumes:
  db_data:
```

**Section sources**
- [pyproject.toml](file://pyproject.toml#L1-L51)
- [app.py](file://src/app.py#L1-L1902)

## Docker镜像构建与运行

### 构建镜像

```bash
docker build -t glzx-xmt:latest .
```

### 运行容器

```bash
docker run -d \
  --name glzx-xmt \
  -p 5000:5000 \
  -e DB_USER=myuser \
  -e DB_PASSWORD=mypassword \
  -e SECRET_KEY=your-secret-key \
  -m 512m \
  glzx-xmt:latest
```

**参数说明：**
- `-p 5000:5000`：端口映射，宿主机5000端口映射到容器5000端口
- `-e`：注入环境变量（数据库用户、密码、密钥等）
- `-m 512m`：限制容器内存使用为512MB
- `--name`：指定容器名称

**Section sources**
- [app.py](file://src/app.py#L1900-L1902)

## 健康检查与环境变量配置

### 健康检查

在 `docker-compose.yml` 中已配置健康检查，定期检测应用根路径是否可访问：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### 环境变量说明

| 环境变量 | 默认值 | 说明 |
|--------|------|------|
| `DATABASE_URL` | 无 | 完整的数据库连接字符串 |
| `DB_USER` | user | 数据库用户名 |
| `DB_PASSWORD` | password | 数据库密码 |
| `DB_HOST` | localhost | 数据库主机 |
| `DB_PORT` | 3306 | 数据库端口 |
| `DB_NAME` | glzx_xmt | 数据库名 |
| `FLASK_RUN_PORT` | 5000 | Flask服务端口 |
| `SECRET_KEY` | your-secret-key-here | Flask会话密钥 |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | false | 是否启用跟踪修改 |

**Section sources**
- [app.py](file://src/app.py#L1-L1902)

## 一键部署说明

通过以下命令即可实现一键部署：

```bash
# 启动服务（后台运行）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

该部署方案支持在任何支持 Docker 的环境中快速部署，包括本地开发、测试和生产环境。通过环境变量和数据卷配置，确保配置与数据的持久化和安全性。

**Section sources**
- [docker-compose.yml](file://docker-compose.yml#L1-L50)
- [app.py](file://src/app.py#L1-L1902)