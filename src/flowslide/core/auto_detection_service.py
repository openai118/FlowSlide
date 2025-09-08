"""
自动检测服务 - 根据外部数据库和R2的有效配置自动确定运行模式
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from ..core.sync_strategy_config import DeploymentMode

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CONFIG_MISSING = "config_missing"
    CONNECTION_FAILED = "connection_failed"


@dataclass
class ServiceCheckResult:
    """服务检查结果"""
    status: ServiceStatus
    message: str
    response_time_ms: Optional[float] = None
    error_details: Optional[str] = None


class AutoDetectionService:
    """自动检测服务"""

    def __init__(self):
        self.cache_timeout = 300  # 5分钟缓存
        self._cache: Dict[str, Tuple[ServiceCheckResult, float]] = {}

    def _is_cache_valid(self, service_name: str) -> bool:
        """检查缓存是否有效"""
        if service_name not in self._cache:
            return False

        result, timestamp = self._cache[service_name]
        import time
        return (time.time() - timestamp) < self.cache_timeout

    def _cache_result(self, service_name: str, result: ServiceCheckResult):
        """缓存检测结果"""
        import time
        self._cache[service_name] = (result, time.time())

    def _get_cached_result(self, service_name: str) -> Optional[ServiceCheckResult]:
        """获取缓存的检测结果"""
        if self._is_cache_valid(service_name):
            return self._cache[service_name][0]
        return None

    async def check_external_database(self) -> ServiceCheckResult:
        """检查外部数据库连接"""
        # 检查缓存
        cached = self._get_cached_result("external_db")
        if cached:
            return cached

        try:
            # 动态导入配置以避免循环导入
            from .simple_config import DATABASE_URL, LOCAL_DATABASE_URL, DATABASE_MODE
            
            database_url = (DATABASE_URL or "").strip()
            database_mode = DATABASE_MODE
            
            # 如果使用的是本地数据库URL，则认为是本地模式
            if (not database_url) or database_url == LOCAL_DATABASE_URL or database_url.startswith("sqlite:///"):
                result = ServiceCheckResult(
                    status=ServiceStatus.UNAVAILABLE,
                    message="使用的是本地SQLite数据库"
                )
                self._cache_result("external_db", result)
                return result

            # 如果数据库模式显式为 local，则强制认为是本地数据库
            if (database_mode or "").strip().lower() == "local":
                result = ServiceCheckResult(
                    status=ServiceStatus.UNAVAILABLE,
                    message="数据库模式设置为local，使用本地数据库"
                )
                self._cache_result("external_db", result)
                return result

            # 检查是否是有效的外部数据库URL
            if not (database_url.startswith("postgresql://") or database_url.startswith("mysql://")):
                result = ServiceCheckResult(
                    status=ServiceStatus.UNAVAILABLE,
                    message="不是有效的外部数据库URL格式"
                )
                self._cache_result("external_db", result)
                return result

            # 尝试连接数据库（只有连接成功才算 AVAILABLE）
            import time
            start_time = time.time()

            # 创建异步引擎进行测试
            # If asyncpg is used behind pgbouncer, disable asyncpg's statement cache
            # by setting statement_cache_size=0 (or read from PG_STATEMENT_CACHE_SIZE env).
            # 强制所有 asyncpg 场景禁用 prepared statement 缓存，避免 pgbouncer 问题
            async_connect_args = {"statement_cache_size": 0}
            async_engine = create_async_engine(database_url, echo=False, connect_args=async_connect_args)

            try:
                async with async_engine.connect() as conn:
                    # 执行简单查询测试连接
                    result = await conn.execute(text("SELECT 1 as test"))
                    row = result.fetchone()

                    response_time = (time.time() - start_time) * 1000

                    if row and row[0] == 1:
                        check_result = ServiceCheckResult(
                            status=ServiceStatus.AVAILABLE,
                            message="外部数据库连接正常",
                            response_time_ms=round(response_time, 2)
                        )
                    else:
                        check_result = ServiceCheckResult(
                            status=ServiceStatus.CONNECTION_FAILED,
                            message="数据库连接测试失败：查询返回异常结果",
                            response_time_ms=round(response_time, 2)
                        )

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                check_result = ServiceCheckResult(
                    status=ServiceStatus.CONNECTION_FAILED,
                    message=f"外部数据库连接失败: {str(e)}",
                    response_time_ms=round(response_time, 2),
                    error_details=str(e)
                )

            finally:
                await async_engine.dispose()

            self._cache_result("external_db", check_result)
            return check_result

        except Exception as e:
            result = ServiceCheckResult(
                status=ServiceStatus.CONNECTION_FAILED,
                message=f"外部数据库检测过程中发生错误: {str(e)}",
                error_details=str(e)
            )
            self._cache_result("external_db", result)
            return result

    async def check_r2_storage(self) -> ServiceCheckResult:
        """检查R2云存储连接"""
        # 检查缓存
        cached = self._get_cached_result("r2")
        if cached:
            return cached

        try:
            import time
            start_time = time.time()

            # 检查R2配置
            r2_config = {
                "access_key": os.getenv("R2_ACCESS_KEY_ID"),
                "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
                "endpoint": os.getenv("R2_ENDPOINT"),
                "bucket": os.getenv("R2_BUCKET_NAME")
            }

            # 严格完整性：全部四项都非空才继续
            if not all(r2_config.values()):
                missing_configs = [k for k,v in r2_config.items() if not v]
                result = ServiceCheckResult(
                    status=ServiceStatus.CONFIG_MISSING,
                    message=f"R2配置不完整，缺少: {', '.join(missing_configs)}"
                )
                self._cache_result("r2", result)
                return result

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
                response = s3_client.list_objects_v2(
                    Bucket=r2_config["bucket"],
                    MaxKeys=1
                )

                response_time = (time.time() - start_time) * 1000

                check_result = ServiceCheckResult(
                    status=ServiceStatus.AVAILABLE,
                    message="R2云存储连接正常",
                    response_time_ms=round(response_time, 2)
                )

            except NoCredentialsError as e:
                response_time = (time.time() - start_time) * 1000
                check_result = ServiceCheckResult(
                    status=ServiceStatus.CONNECTION_FAILED,
                    message="R2凭据无效，请检查Access Key和Secret Key",
                    response_time_ms=round(response_time, 2),
                    error_details=str(e)
                )

            except ClientError as e:
                response_time = (time.time() - start_time) * 1000
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')

                if error_code == 'NoSuchBucket':
                    check_result = ServiceCheckResult(
                        status=ServiceStatus.CONNECTION_FAILED,
                        message=f"R2存储桶 '{r2_config['bucket']}' 不存在",
                        response_time_ms=round(response_time, 2),
                        error_details=error_code
                    )
                elif error_code == 'AccessDenied':
                    check_result = ServiceCheckResult(
                        status=ServiceStatus.CONNECTION_FAILED,
                        message="R2访问被拒绝，请检查权限设置",
                        response_time_ms=round(response_time, 2),
                        error_details=error_code
                    )
                else:
                    check_result = ServiceCheckResult(
                        status=ServiceStatus.CONNECTION_FAILED,
                        message=f"R2连接失败: {error_code}",
                        response_time_ms=round(response_time, 2),
                        error_details=error_code
                    )

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                check_result = ServiceCheckResult(
                    status=ServiceStatus.CONNECTION_FAILED,
                    message=f"R2连接测试异常: {str(e)}",
                    response_time_ms=round(response_time, 2),
                    error_details=str(e)
                )

            self._cache_result("r2", check_result)
            return check_result

        except Exception as e:
            result = ServiceCheckResult(
                status=ServiceStatus.CONNECTION_FAILED,
                message=f"R2检测过程中发生错误: {str(e)}",
                error_details=str(e)
            )
            self._cache_result("r2", result)
            return result

    async def detect_deployment_mode(self) -> DeploymentMode:
        """自动检测部署模式"""
        logger.info("🔍 开始自动检测部署模式...")

        # 并行检查外部数据库和R2
        db_task = asyncio.create_task(self.check_external_database())
        r2_task = asyncio.create_task(self.check_r2_storage())

        db_result, r2_result = await asyncio.gather(db_task, r2_task)

        # 记录检测结果
        logger.info(f"📊 外部数据库检测结果: {db_result.status.value} - {db_result.message}")
        logger.info(f"📊 R2存储检测结果: {r2_result.status.value} - {r2_result.message}")

        # 根据检测结果确定部署模式
        has_external_db = db_result.status == ServiceStatus.AVAILABLE
        has_r2 = r2_result.status == ServiceStatus.AVAILABLE

        if has_external_db and has_r2:
            detected_mode = DeploymentMode.LOCAL_EXTERNAL_R2
            logger.info("🎯 检测到部署模式: 本地+外部数据库+R2")
        elif has_external_db:
            detected_mode = DeploymentMode.LOCAL_EXTERNAL
            logger.info("🎯 检测到部署模式: 本地+外部数据库")
        elif has_r2:
            detected_mode = DeploymentMode.LOCAL_R2
            logger.info("🎯 检测到部署模式: 本地+R2")
        else:
            detected_mode = DeploymentMode.LOCAL_ONLY
            logger.info("🎯 检测到部署模式: 仅本地")

        return detected_mode

    def clear_cache(self):
        """清除检测缓存"""
        self._cache.clear()
        logger.info("🧹 已清除自动检测缓存")

    async def get_service_status(self) -> Dict[str, Any]:
        """获取所有服务的状态"""
        db_result = await self.check_external_database()
        r2_result = await self.check_r2_storage()

        return {
            "external_database": {
                "status": db_result.status.value,
                "message": db_result.message,
                "response_time_ms": db_result.response_time_ms,
                "error_details": db_result.error_details
            },
            "r2_storage": {
                "status": r2_result.status.value,
                "message": r2_result.message,
                "response_time_ms": r2_result.response_time_ms,
                "error_details": r2_result.error_details
            }
        }


# 创建全局自动检测服务实例
auto_detection_service = AutoDetectionService()