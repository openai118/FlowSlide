"""
系统监控API接口
提供系统资源监控、数据库连接测试等功能
"""

import os
import psutil
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..database import db_manager
from ..services.backup_service import backup_service

router = APIRouter(prefix="/api/system", tags=["System Monitoring"])
logger = logging.getLogger(__name__)


@router.get("/db-status")
async def get_database_status():
    """获取数据库配置状态
    注意：这里的 configured 仅表示“是否配置了外部数据库（DATABASE_URL 为 postgresql/mysql）”，
    本地 SQLite 的存在不视为已配置外部数据库。
    """
    try:
        logger.info("🗄️ Checking database status...")

        # 运行时主库类型（sqlite / postgresql ...）仅用于展示
        runtime_db_type = getattr(db_manager, 'database_type', None)

        # 外部数据库配置仅来自环境（或后续你可能写入到 env 的配置中心）
        raw_db_url = (os.getenv("DATABASE_URL") or "").strip()
        is_external_configured = raw_db_url.startswith("postgresql://") or raw_db_url.startswith("mysql://")

        status_info = {
            "configured": is_external_configured,
            "timestamp": datetime.now().isoformat(),
            "database_type": runtime_db_type or 'unknown'
        }

        # 提供 db_url 的类型解析（仅作提示用途）
        if raw_db_url:
            if raw_db_url.startswith("sqlite"):
                status_info["db_type"] = "SQLite"
            elif raw_db_url.startswith("postgresql"):
                status_info["db_type"] = "PostgreSQL"
            elif raw_db_url.startswith("mysql"):
                status_info["db_type"] = "MySQL"
            else:
                status_info["db_type"] = "Unknown"

        logger.info(f"✅ Database status checked: {'configured' if is_external_configured else 'not configured'}")
        return {
            "success": True,
            "db_status": status_info
        }

    except Exception as e:
        logger.error(f"❌ Get database status failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库状态失败: {str(e)}")


@router.get("/r2-status")
async def get_r2_status():
    """获取R2云存储配置状态"""
    try:
        logger.info("☁️ Checking R2 status...")

        # 选择配置来源策略：
        # - 若 runtime 内的 r2_config 已“完整配置”（四项均非空），优先使用 runtime；
        # - 否则优先使用当前环境变量（UI 保存后 .env 和 os.environ 已更新）；
        # - 最后兜底使用 runtime（即使不完整），避免返回空结构。
        r2_runtime = getattr(backup_service, 'r2_config', None)
        runtime_has_all = bool(r2_runtime and all(r2_runtime.get(k) for k in ("access_key", "secret_key", "endpoint", "bucket")))

        env_config = {
            "access_key": os.getenv("R2_ACCESS_KEY_ID"),
            "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
            "endpoint": os.getenv("R2_ENDPOINT"),
            "bucket": os.getenv("R2_BUCKET_NAME")
        }
        env_has_any = any(env_config.values())

        if runtime_has_all:
            r2_config = r2_runtime  # 完整的运行时配置
        elif env_has_any:
            r2_config = env_config   # 使用最新环境变量（来自 UI 保存）
        else:
            r2_config = r2_runtime or env_config  # 兜底

        # 检查配置完整性
        is_configured = all((v for v in (r2_config.get('access_key'), r2_config.get('secret_key'), r2_config.get('endpoint'), r2_config.get('bucket'))))

        status_info = {
            "configured": is_configured,
            "timestamp": datetime.now().isoformat(),
            "provider_info": None
        }

        if is_configured:
            # 解析endpoint类型（不包含敏感信息）
            endpoint = r2_config.get("endpoint")
            if endpoint and "cloudflarestorage.com" in endpoint:
                status_info["provider"] = "Cloudflare R2"
            else:
                status_info["provider"] = "Unknown"
            # include a small, non-sensitive provider hint
            status_info["provider_info"] = {
                "endpoint": endpoint,
                "bucket": r2_config.get('bucket')
            }

        logger.info(f"✅ R2 status checked: {'configured' if is_configured else 'not configured'}")
        return {
            "success": True,
            "r2_status": status_info
        }

    except Exception as e:
        logger.error(f"❌ Get R2 status failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取R2状态失败: {str(e)}")


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


@router.get("/db-test")
async def test_database_connection():
    """测试数据库连接"""
    import time
    try:
        logger.info("🧪 Testing database connection...")

        # 记录开始时间
        start_time = time.time()

        # 检查数据库配置
        db_url = os.getenv("DATABASE_URL")
        is_configured = bool(db_url and db_url.strip())

        # 如果没有配置外部数据库，直接返回未配置状态（不报错）
        if not is_configured:
            return {
                "success": True,  # 改为True，因为本地数据库总是可用的
                "configured": False,
                "message": "使用本地SQLite数据库，未配置外部数据库",
                "database_type": "sqlite",
                "response_time_ms": round((time.time() - start_time) * 1000, 2)
            }

        # 尝试连接数据库
        try:
            # 使用数据库管理器进行连接测试
            from ..database import db_manager
            from sqlalchemy import text

            # 检查数据库管理器是否已初始化
            if not hasattr(db_manager, 'engine') or db_manager.engine is None:
                return {
                    "success": False,
                    "message": "数据库引擎未初始化",
                    "response_time_ms": round((time.time() - start_time) * 1000, 2)
                }

            if not hasattr(db_manager, 'primary_async_engine') or db_manager.primary_async_engine is None:
                return {
                    "success": False,
                    "message": "异步数据库引擎未初始化",
                    "response_time_ms": round((time.time() - start_time) * 1000, 2)
                }

            # 执行一个简单的查询来测试连接
            async with db_manager.primary_async_engine.connect() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()

                # 计算响应时间
                response_time = round((time.time() - start_time) * 1000, 2)

                if row and row[0] == 1:
                    logger.info(f"✅ Database connection test passed in {response_time}ms")
                    return {
                        "success": True,
                        "configured": True,
                        "message": f"数据库连接正常 ({db_manager.database_type})",
                        "database_type": db_manager.database_type,
                        "response_time_ms": response_time
                    }
                else:
                    return {
                        "success": False,
                        "configured": True,
                        "message": "数据库连接异常：查询返回异常结果",
                        "response_time_ms": response_time
                    }

        except Exception as e:
            response_time = round((time.time() - start_time) * 1000, 2)
            logger.error(f"❌ Database connection test failed: {e}")
            return {
                "success": False,
                "configured": True,
                "message": f"数据库连接异常: {str(e)}",
                "response_time_ms": response_time
            }

    except Exception as e:
        logger.error(f"❌ Database test setup failed: {e}")
        return {
            "success": False,
            "message": f"数据库测试设置失败: {str(e)}",
            "response_time_ms": None
        }


@router.get("/r2-test")
async def test_r2_connection():
    """测试R2云存储连接
    优先使用运行时 backup_service.r2_config（若完整），否则回退到环境变量。
    """
    import time

    try:
        # 延迟导入以更好地处理缺失依赖
        try:
            import boto3  # type: ignore
            from botocore.exceptions import NoCredentialsError, ClientError  # type: ignore
        except Exception as import_err:
            logger.error(f"❌ boto3 未安装或导入失败: {import_err}")
            return {
                "success": False,
                "configured": False,
                "message": "缺少boto3依赖，无法测试R2连接",
                "response_time_ms": None
            }

        logger.info("☁️ Testing R2 connection...")

        # 记录开始时间
        start_time = time.time()

        # 选择配置来源（与 /r2-status 保持一致）
        r2_runtime = getattr(backup_service, 'r2_config', None) or {}
        runtime_has_all = all(r2_runtime.get(k) for k in ("access_key", "secret_key", "endpoint", "bucket"))
        env_config = {
            "access_key": os.getenv("R2_ACCESS_KEY_ID"),
            "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
            "endpoint": os.getenv("R2_ENDPOINT"),
            "bucket": os.getenv("R2_BUCKET_NAME")
        }
        env_has_all = all(env_config.get(k) for k in ("access_key", "secret_key", "endpoint", "bucket"))

        r2_config = r2_runtime if runtime_has_all else env_config
        is_configured = all(r2_config.get(k) for k in ("access_key", "secret_key", "endpoint", "bucket"))

        if not is_configured:
            return {
                "success": False,
                "configured": False,
                "message": "R2配置不完整，请在设置中填写并保存 Access Key/Secret/Endpoint/Bucket",
                "response_time_ms": round((time.time() - start_time) * 1000, 2)
            }

        # 创建S3客户端连接R2
        s3_client = boto3.client(
            's3',
            aws_access_key_id=r2_config["access_key"],
            aws_secret_access_key=r2_config["secret_key"],
            endpoint_url=r2_config["endpoint"],
            region_name='auto'  # Cloudflare R2使用auto region
        )

        # 测试连接：尝试列出bucket中的对象（最多1个）
        try:
            _ = s3_client.list_objects_v2(
                Bucket=r2_config["bucket"],
                MaxKeys=1
            )

            # 计算响应时间
            response_time = round((time.time() - start_time) * 1000, 2)

            logger.info(f"✅ R2 connection test passed in {response_time}ms")
            return {
                "success": True,
                "configured": True,
                "message": "R2连接正常",
                "bucket": r2_config["bucket"],
                "endpoint": r2_config["endpoint"],
                "response_time_ms": response_time
            }

        except NoCredentialsError:
            response_time = round((time.time() - start_time) * 1000, 2)
            logger.error("❌ R2 credentials invalid")
            return {
                "success": False,
                "configured": True,
                "message": "R2凭据无效，请检查Access Key和Secret Key",
                "response_time_ms": response_time
            }
        except ClientError as e:
            response_time = round((time.time() - start_time) * 1000, 2)
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchBucket':
                logger.error("❌ R2 bucket does not exist")
                return {
                    "success": False,
                    "configured": True,
                    "message": f"R2存储桶 '{r2_config['bucket']}' 不存在",
                    "response_time_ms": response_time
                }
            elif error_code == 'AccessDenied':
                logger.error("❌ R2 access denied")
                return {
                    "success": False,
                    "configured": True,
                    "message": "R2访问被拒绝，请检查权限设置",
                    "response_time_ms": response_time
                }
            else:
                logger.error(f"❌ R2 connection failed: {error_code}")
                return {
                    "success": False,
                    "configured": True,
                    "message": f"R2连接失败: {error_code}",
                    "response_time_ms": response_time
                }
        except Exception as e:
            response_time = round((time.time() - start_time) * 1000, 2)
            logger.error(f"❌ R2 connection test failed: {e}")
            return {
                "success": False,
                "configured": True,
                "message": f"R2连接异常: {str(e)}",
                "response_time_ms": response_time
            }

    except Exception as e:
        logger.error(f"❌ R2 test setup failed: {e}")
        return {
            "success": False,
            "message": f"R2测试设置失败: {str(e)}",
            "response_time_ms": None
        }


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


@router.get("/auto-detection")
async def get_auto_detection_status():
    """获取自动检测状态"""
    try:
        logger.info("🔍 获取自动检测状态...")

        from ..core.auto_detection_service import auto_detection_service

        # 获取服务状态
        service_status = await auto_detection_service.get_service_status()

        # 检测当前部署模式
        current_mode = await auto_detection_service.detect_deployment_mode()

        return {
            "success": True,
            "current_mode": current_mode.value,
            "services": service_status,
            "message": "自动检测状态获取成功"
        }

    except Exception as e:
        logger.error(f"❌ 获取自动检测状态失败: {e}")
        return {
            "success": False,
            "message": f"获取自动检测状态失败: {str(e)}",
            "current_mode": "unknown",
            "services": {}
        }


@router.post("/auto-detection/clear-cache")
async def clear_auto_detection_cache():
    """清除自动检测缓存"""
    try:
        logger.info("🧹 清除自动检测缓存...")

        from ..core.auto_detection_service import auto_detection_service
        auto_detection_service.clear_cache()

        return {
            "success": True,
            "message": "自动检测缓存已清除"
        }

    except Exception as e:
        logger.error(f"❌ 清除自动检测缓存失败: {e}")
        return {
            "success": False,
            "message": f"清除自动检测缓存失败: {str(e)}"
        }


@router.post("/restart")
async def restart_application(background_tasks: BackgroundTasks):
    """重启应用程序服务"""
    try:
        logger.info("🔄 正在重启应用程序服务...")

        # 记录重启请求
        import time
        restart_time = datetime.now().isoformat()

        # 在后台执行重启操作，避免阻塞响应
        async def perform_restart():
            try:
                # 等待一小段时间，让API响应返回给客户端
                await asyncio.sleep(2)

                # 重新加载服务实例
                from ..services.service_instances import reload_services
                reload_services()

                # 重新加载环境变量
                from dotenv import load_dotenv
                load_dotenv(override=True)

                logger.info("✅ 应用程序服务重启完成")

            except Exception as e:
                logger.error(f"❌ 应用程序重启失败: {e}")

        # 添加后台任务
        background_tasks.add_task(perform_restart)

        return {
            "success": True,
            "message": "应用程序重启已启动，请等待几秒钟后刷新页面确认重启结果",
            "restart_time": restart_time,
            "status": "restarting"
        }

    except Exception as e:
        logger.error(f"❌ 重启请求处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"重启请求处理失败: {str(e)}")


@router.get("/restart-status")
async def get_restart_status():
    """获取重启状态"""
    try:
        # 这里可以添加更复杂的重启状态检查逻辑
        # 目前简单返回成功状态
        return {
            "success": True,
            "status": "completed",
            "message": "服务运行正常",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ 获取重启状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取重启状态失败: {str(e)}")
