"""
应用入口文件 - SQLite简化版
"""
import os
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app

# 创建应用
app = create_app('development')

if __name__ == '__main__':
    # 确保目录存在
    os.makedirs('../photo/uploads', exist_ok=True)
    os.makedirs('../photo/thumbs', exist_ok=True)
    os.makedirs('../instance', exist_ok=True)
    
    # 运行应用
    app.run(debug=True, host='127.0.0.1', port=5000)
