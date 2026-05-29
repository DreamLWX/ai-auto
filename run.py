"""
Flask 应用启动入口（开发环境）
"""
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    # host=0.0.0.0 让局域网其他设备也能访问
    # debug=True 开启热重载
    app.run(host='0.0.0.0', port=5000, debug=True)