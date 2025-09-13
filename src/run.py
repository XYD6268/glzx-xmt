#!/usr/bin/env python3
"""
高性能启动脚本
"""
import os
import sys
from app_new import create_app
from tasks.celery_app import make_celery

# 设置环境
os.environ.setdefault('FLASK_ENV', 'production')

# 创建应用
app = create_app()
celery = make_celery(app)

if __name__ == '__main__':
    # 开发环境直接运行
    if os.environ.get('FLASK_ENV') == 'development':
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        print("生产环境请使用 Gunicorn 启动:")
        print("gunicorn -w 4 -k gevent -b 0.0.0.0:5000 run:app")
        print("\nCelery 启动命令:")
        print("celery -A run.celery worker --loglevel=info")