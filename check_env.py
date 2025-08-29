#!/usr/bin/env python3
"""
检查环境变量配置
"""

import os
from dotenv import load_dotenv

load_dotenv()

print('=== 环境变量检查 ===')
print(f'DATABASE_MODE: {os.getenv("DATABASE_MODE")}')
print(f'DATABASE_URL: {os.getenv("DATABASE_URL")}')
print(f'ENABLE_DATA_SYNC: {os.getenv("ENABLE_DATA_SYNC")}')
print(f'SYNC_INTERVAL: {os.getenv("SYNC_INTERVAL")}')
print(f'SYNC_DIRECTIONS: {os.getenv("SYNC_DIRECTIONS")}')

# 检查 .env 文件内容
print('\n=== .env 文件内容 ===')
try:
    with open('.env', 'r', encoding='utf-8') as f:
        content = f.read()
        print(content)
except Exception as e:
    print(f'读取 .env 文件失败: {e}')
