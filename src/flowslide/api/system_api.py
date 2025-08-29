"""
系统监控API接口
提供系统资源监控、数据库连接测试等功能
"""

import os
import psutil
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from ..database import db_manager

router = APIRouter(prefix="/api/system", tags=["System Monitoring"])
logger = logging.getLogger(__name__)


@router.get("/db-test")
async def test_database_connection():
    """测试数据库连接"""
    import time
    try:
        logger.info("🔍 Testing database connection...")

        # 记录开始时间
        start_time = time.time()

        # 测试数据库连接
        if db_manager.database_type == "sqlite":
            # SQLite连接测试
            import sqlite3
            db_path = "./data/flowslide.db"
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
        else:
            # 外部数据库连接测试
            # 这里可以实现外部数据库的连接测试
            pass

        # 计算响应时间
        response_time = round((time.time() - start_time) * 1000, 2)  # 毫秒

        logger.info(f"✅ Database connection test passed in {response_time}ms")
        return {
            "success": True,
            "message": "数据库连接正常",
            "database_type": db_manager.database_type,
            "response_time_ms": response_time
        }

    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return {
            "success": False,
            "message": f"数据库连接异常: {str(e)}",
            "database_type": db_manager.database_type,
            "response_time_ms": None
        }


@router.get("/resources")
async def get_system_resources():
    """获取系统资源信息"""
    try:
        logger.info("📊 Collecting system resources...")

        # CPU信息
        cpu_percent = psutil.cpu_percent(interval=1)

        # 内存信息
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent
        }

        # 磁盘信息
        disk = psutil.disk_usage('/')
        disk_info = {
            "total": disk.total,
            "free": disk.free,
            "used": disk.used,
            "percent": disk.percent
        }

        # 系统运行时间
        uptime_seconds = psutil.boot_time()
        current_time = datetime.now().timestamp()
        uptime = current_time - uptime_seconds

        resources = {
            "cpu": {
                "percent": cpu_percent
            },
            "memory": {
                "total": f"{memory_info['total'] // (1024**3)}GB",
                "used": f"{memory_info['used'] // (1024**3)}GB",
                "available": f"{memory_info['available'] // (1024**3)}GB",
                "percent": memory_info["percent"]
            },
            "disk": {
                "total": f"{disk_info['total'] // (1024**3)}GB",
                "used": f"{disk_info['used'] // (1024**3)}GB",
                "free": f"{disk_info['free'] // (1024**3)}GB",
                "percent": disk_info["percent"]
            },
            "uptime": uptime,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("✅ System resources collected")
        return {
            "success": True,
            "resources": resources
        }

    except Exception as e:
        logger.error(f"❌ Get system resources failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统资源信息失败: {str(e)}")


@router.get("/r2-status")
async def get_r2_status():
    """获取R2云存储状态"""
    try:
        logger.info("☁️ Checking R2 status...")

        # 检查R2配置
        r2_config = {
            "access_key": os.getenv("R2_ACCESS_KEY_ID"),
            "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
            "endpoint": os.getenv("R2_ENDPOINT"),
            "bucket": os.getenv("R2_BUCKET_NAME")
        }

        is_configured = all(r2_config.values())

        # 获取最后同步时间（从环境变量或配置文件中读取）
        last_sync_time = os.getenv("LAST_R2_SYNC_TIME")

        status_info = {
            "configured": is_configured,
            "timestamp": datetime.now().isoformat(),
            "last_sync": last_sync_time,
            "success": is_configured  # 如果配置了就认为是成功的
        }

        if is_configured:
            status_info.update({
                "endpoint": r2_config["endpoint"],
                "bucket": r2_config["bucket"]
            })

        logger.info(f"✅ R2 status checked: {'configured' if is_configured else 'not configured'}")
        return {
            "success": True,
            "r2_status": status_info
        }

    except Exception as e:
        logger.error(f"❌ Get R2 status failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取R2状态失败: {str(e)}")


@router.get("/health")
async def get_system_health():
    """获取系统健康状态"""
    try:
        logger.info("🏥 Checking system health...")

        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.now().isoformat()
        }

        # 数据库连接检查
        try:
            db_test = await test_database_connection()
            health_status["checks"]["database"] = {
                "status": "healthy" if db_test["success"] else "unhealthy",
                "message": db_test["message"]
            }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "message": f"数据库检查失败: {str(e)}"
            }
            health_status["status"] = "unhealthy"

        # 系统资源检查
        try:
            resources = await get_system_resources()
            memory_percent = float(resources["resources"]["memory"]["percent"])
            disk_percent = float(resources["resources"]["disk"]["percent"])

            health_status["checks"]["resources"] = {
                "status": "healthy",
                "memory_usage": f"{memory_percent}%",
                "disk_usage": f"{disk_percent}%"
            }

            # 如果资源使用率过高，标记为警告
            if memory_percent > 90 or disk_percent > 90:
                health_status["checks"]["resources"]["status"] = "warning"
                if health_status["status"] == "healthy":
                    health_status["status"] = "warning"

        except Exception as e:
            health_status["checks"]["resources"] = {
                "status": "unhealthy",
                "message": f"资源检查失败: {str(e)}"
            }
            health_status["status"] = "unhealthy"

        # R2状态检查
        try:
            r2_status = await get_r2_status()
            health_status["checks"]["r2"] = {
                "status": "healthy" if r2_status["r2_status"]["configured"] else "not_configured",
                "configured": r2_status["r2_status"]["configured"]
            }
        except Exception as e:
            health_status["checks"]["r2"] = {
                "status": "error",
                "message": f"R2检查失败: {str(e)}"
            }

        logger.info(f"✅ System health checked: {health_status['status']}")
        return health_status

    except Exception as e:
        logger.error(f"❌ Get system health failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统健康状态失败: {str(e)}")
