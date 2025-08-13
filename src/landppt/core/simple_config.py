"""
简化的配置文件 - 临时修复数据库问题
"""

import os

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/db/landppt.db")

# 简单的配置类
class SimpleConfig:
    def __init__(self):
        self.database_url = DATABASE_URL
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.debug = os.getenv("DEBUG", "True").lower() == "true"

# 全局配置实例
app_config = SimpleConfig()
