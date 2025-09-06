# 摄影比赛投票系统依赖安装

## 安装方式

### 方式一：使用 requirements.txt（推荐）
```bash
pip install -r requirements.txt
```

### 方式二：逐个安装
```bash
pip install Flask==2.3.3
pip install Flask-SQLAlchemy==3.0.5
pip install Pillow==10.0.1
pip install PyMySQL==1.1.0
pip install Werkzeug==2.3.7
```

## 依赖说明

- **Flask**: Web框架，用于构建后端API和路由
- **Flask-SQLAlchemy**: Flask的SQLAlchemy扩展，用于数据库ORM操作
- **Pillow**: Python图像处理库，用于生成照片缩略图
- **PyMySQL**: Python MySQL数据库连接器（仅MySQL版本需要）
- **Werkzeug**: Flask的核心工具库，包含文件上传安全处理

## 使用说明

- `app.py`: 使用MySQL数据库版本
- `app_test.py`: 使用SQLite数据库版本（测试用）

SQLite版本无需额外配置，MySQL版本需要修改数据库连接字符串。
