"""
备份服务 - 集成R2云备份和本地备份功能
"""

import asyncio
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class BackupService:
    """备份服务"""

    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        self.backup_dir = Path("./backups")
        self.backup_dir.mkdir(exist_ok=True)

        # R2配置
        self.r2_config = {
            "access_key": os.getenv("R2_ACCESS_KEY_ID"),
            "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
            "endpoint": os.getenv("R2_ENDPOINT"),
            "bucket": os.getenv("R2_BUCKET_NAME")
        }

        # 备份配置
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        self.webhook_url = os.getenv("BACKUP_WEBHOOK_URL")

    async def create_backup(self, backup_type: str = "full") -> str:
        """创建备份

        Args:
            backup_type: 备份类型 (full, db_only, config_only)

        Returns:
            备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"flowslide_backup_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)

        try:
            logger.info(f"📦 Creating {backup_type} backup: {backup_name}")

            if backup_type in ["full", "db_only"]:
                await self._backup_database(backup_path)

            if backup_type in ["full", "config_only"]:
                await self._backup_config(backup_path)

            if backup_type == "full":
                await self._backup_uploads(backup_path)

            # 压缩备份
            archive_path = await self._compress_backup(backup_path)

            # 上传到R2（如果配置了）
            if self._is_r2_configured():
                await self._upload_to_r2(archive_path)

            # 清理旧备份
            await self._cleanup_old_backups()

            # 发送通知
            if self.webhook_url:
                await self._send_notification(backup_name, "success")

            logger.info(f"✅ Backup completed: {archive_path}")
            return str(archive_path)

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            if self.webhook_url:
                await self._send_notification(backup_name, "failed", str(e))
            raise

    async def _backup_database(self, backup_path: Path):
        """备份数据库"""
        try:
            from ..database import db_manager

            if db_manager.database_type == "sqlite":
                # SQLite数据库备份
                db_file = Path("./data/flowslide.db")
                if db_file.exists():
                    shutil.copy2(db_file, backup_path / "flowslide.db")
                    logger.info("💾 Database backup completed")
            else:
                # 外部数据库备份
                await self._backup_external_database(backup_path)

        except Exception as e:
            logger.error(f"❌ Database backup failed: {e}")
            raise

    async def _backup_external_database(self, backup_path: Path):
        """备份外部数据库"""
        # 这里可以实现外部数据库的备份逻辑
        # 例如使用pg_dump for PostgreSQL
        logger.info("💾 External database backup (not implemented)")

    async def _backup_config(self, backup_path: Path):
        """备份配置文件"""
        config_files = [".env", "pyproject.toml", "uv.toml"]

        for config_file in config_files:
            if Path(config_file).exists():
                shutil.copy2(config_file, backup_path / config_file)

        logger.info("⚙️ Config backup completed")

    async def _backup_uploads(self, backup_path: Path):
        """备份上传文件"""
        uploads_dir = Path("./uploads")
        if uploads_dir.exists():
            shutil.copytree(uploads_dir, backup_path / "uploads", dirs_exist_ok=True)
            logger.info("📁 Uploads backup completed")

    async def _compress_backup(self, backup_path: Path) -> Path:
        """压缩备份文件"""
        import zipfile

        archive_path = backup_path.with_suffix('.zip')

        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in backup_path.rglob('*'):
                if file_path.is_file():
                    zipf.write(file_path, file_path.relative_to(backup_path.parent))

        # 删除原始备份目录
        shutil.rmtree(backup_path)

        logger.info(f"🗜️ Backup compressed: {archive_path}")
        return archive_path

    async def _upload_to_r2(self, backup_path: Path):
        """上传备份到R2"""
        if not self._is_r2_configured():
            logger.info("ℹ️ R2 not configured, skipping cloud backup")
            return

        try:
            logger.info(f"☁️ Starting R2 upload: {backup_path.name}")

            # 创建S3客户端，配置为R2
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.r2_config['access_key'],
                aws_secret_access_key=self.r2_config['secret_key'],
                endpoint_url=self.r2_config['endpoint'],
                region_name='auto'  # R2使用auto region
            )

            # 生成备份日期目录
            backup_date = datetime.now().strftime("%Y-%m-%d")
            s3_key = f"backups/{backup_date}/{backup_path.name}"

            # 上传文件
            logger.info(f"Uploading to R2: {self.r2_config['bucket']}/{s3_key}")

            # 使用asyncio.to_thread在后台线程中运行同步的boto3操作
            await asyncio.to_thread(
                s3_client.upload_file,
                str(backup_path),
                self.r2_config['bucket'],
                s3_key
            )

            logger.info(f"✅ R2 upload completed successfully: {backup_path.name}")

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"❌ R2 upload failed (AWS Error {error_code}): {error_msg}")
            raise Exception(f"R2 upload failed: {error_msg}")
        except Exception as e:
            logger.error(f"❌ R2 upload failed: {e}")
            # 不抛出异常，因为本地备份已经成功

    def _is_r2_configured(self) -> bool:
        """检查R2是否配置"""
        return all(self.r2_config.values())

    async def _cleanup_old_backups(self):
        """清理旧备份"""
        try:
            cutoff_date = datetime.now().timestamp() - (self.retention_days * 24 * 60 * 60)

            for backup_file in self.backup_dir.glob("*.zip"):
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()
                    logger.info(f"🗑️ Cleaned up old backup: {backup_file.name}")

        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")

    async def _send_notification(self, backup_name: str, status: str, error: Optional[str] = None):
        """发送备份通知"""
        if not self.webhook_url:
            return

        try:
            import aiohttp

            message = {
                "backup_name": backup_name,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "error": error
            }

            async with aiohttp.ClientSession() as session:
                await session.post(self.webhook_url, json=message)

        except Exception as e:
            logger.error(f"❌ Notification failed: {e}")

    async def sync_to_r2(self, backup_path: Optional[Path] = None) -> Dict[str, Any]:
        """同步备份到R2云存储

        Args:
            backup_path: 指定的备份文件路径，如果为None则使用最新的备份

        Returns:
            同步结果信息
        """
        if not self._is_r2_configured():
            raise Exception("R2云存储未配置")

        try:
            # 如果没有指定备份路径，使用最新的备份
            if backup_path is None:
                backups = await list_backups()
                if not backups:
                    raise Exception("没有找到备份文件进行同步")
                backup_path = Path(backups[0]["path"])

            # 确保备份文件存在
            if not backup_path.exists():
                raise FileNotFoundError(f"备份文件不存在: {backup_path}")

            logger.info(f"☁️ Starting R2 sync: {backup_path.name}")

            # 上传到R2
            await self._upload_to_r2(backup_path)

            sync_info = {
                "filename": backup_path.name,
                "size": backup_path.stat().st_size,
                "timestamp": datetime.now().isoformat(),
                "success": True
            }

            logger.info(f"✅ R2 sync completed: {backup_path.name}")
            return sync_info

        except Exception as e:
            logger.error(f"❌ R2 sync failed: {e}")
            raise

    def list_backups(self) -> list:
        """列出所有备份"""
        backups = []
        for backup_file in self.backup_dir.glob("*.zip"):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(backup_file)
            })

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    async def restore_backup(self, backup_name: str) -> bool:
        """恢复备份"""
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")

        try:
            logger.info(f"🔄 Restoring backup: {backup_name}")

            # 创建临时恢复目录
            restore_temp_dir = self.backup_dir / f"restore_temp_{int(time.time())}"
            restore_temp_dir.mkdir(exist_ok=True)

            def extract_and_restore():
                import zipfile
                import shutil
                from pathlib import Path

                try:
                    # 解压备份文件
                    logger.info(f"📦 Extracting backup: {backup_name}")
                    with zipfile.ZipFile(str(backup_path), 'r') as zip_ref:
                        zip_ref.extractall(str(restore_temp_dir))

                    # 查找数据库文件
                    db_files = list(restore_temp_dir.glob("*.db"))
                    if not db_files:
                        raise Exception("备份文件中没有找到数据库文件")

                    db_file = db_files[0]
                    logger.info(f"🗄️ Found database file: {db_file.name}")

                    # 备份当前数据库
                    current_db_path = Path("./data/flowslide.db")
                    if current_db_path.exists():
                        backup_current = current_db_path.with_suffix('.db.backup')
                        shutil.copy2(str(current_db_path), str(backup_current))
                        logger.info(f"💾 Backed up current database to: {backup_current}")

                    # 恢复数据库文件
                    shutil.copy2(str(db_file), str(current_db_path))
                    logger.info(f"✅ Database restored from: {db_file.name}")

                    # 恢复上传文件（如果存在）
                    uploads_dir = restore_temp_dir / "uploads"
                    if uploads_dir.exists():
                        target_uploads = Path("./uploads")
                        if target_uploads.exists():
                            shutil.rmtree(str(target_uploads))
                        shutil.copytree(str(uploads_dir), str(target_uploads))
                        logger.info("📁 Uploads directory restored")

                    # 恢复配置文件（如果存在）
                    config_files = list(restore_temp_dir.glob("*.json")) + list(restore_temp_dir.glob("*.yaml")) + list(restore_temp_dir.glob("*.yml"))
                    for config_file in config_files:
                        if "flowslide" in config_file.name.lower():
                            target_config = Path(".") / config_file.name
                            shutil.copy2(str(config_file), str(target_config))
                            logger.info(f"⚙️ Config file restored: {config_file.name}")

                    logger.info("✅ Backup restored successfully")
                    return True

                except Exception as e:
                    logger.error(f"❌ Restore operation failed: {e}")
                    # 尝试恢复原始数据库
                    current_db_path = Path("./data/flowslide.db")
                    backup_current = current_db_path.with_suffix('.db.backup')
                    if backup_current.exists():
                        shutil.copy2(str(backup_current), str(current_db_path))
                        logger.info("🔄 Original database restored from backup")
                    raise
                finally:
                    # 清理临时文件
                    if restore_temp_dir.exists():
                        shutil.rmtree(str(restore_temp_dir))
                        logger.info("🧹 Temporary restore files cleaned up")

            # 在线程池中运行恢复操作
            await asyncio.to_thread(extract_and_restore)
            return True

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False

    async def restore_from_r2(self) -> Dict[str, Any]:
        """从R2恢复最新的备份"""
        if not self._is_r2_configured():
            raise Exception("R2云存储未配置")

        try:
            logger.info("🔄 Starting R2 restore...")

            # 创建S3客户端，配置为R2
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.r2_config['access_key'],
                aws_secret_access_key=self.r2_config['secret_key'],
                endpoint_url=self.r2_config['endpoint'],
                region_name='auto'  # R2使用auto region
            )

            # 列出R2中的备份文件
            response = s3_client.list_objects_v2(
                Bucket=self.r2_config['bucket'],
                Prefix='backups/'
            )

            if 'Contents' not in response or not response['Contents']:
                raise Exception("R2中没有找到备份文件")

            # 找到最新的备份文件
            latest_backup = max(response['Contents'], key=lambda x: x['LastModified'])
            backup_key = latest_backup['Key']
            backup_size = latest_backup['Size']
            local_backup_path = self.backup_dir / Path(backup_key).name

            logger.info(f"📥 Downloading latest backup from R2: {backup_key} (Size: {backup_size} bytes)")

            # 确保备份目录存在
            self.backup_dir.mkdir(exist_ok=True)

            # 下载备份文件
            await asyncio.to_thread(
                s3_client.download_file,
                self.r2_config['bucket'],
                backup_key,
                str(local_backup_path)
            )

            # 验证下载的文件
            if not local_backup_path.exists():
                raise Exception("下载的文件不存在")

            downloaded_size = local_backup_path.stat().st_size
            if downloaded_size != backup_size:
                raise Exception(f"文件下载不完整。期望: {backup_size} bytes, 实际: {downloaded_size} bytes")

            logger.info(f"✅ Backup downloaded successfully: {local_backup_path} ({downloaded_size} bytes)")

            # 恢复备份
            success = await self.restore_backup(local_backup_path.name)

            if success:
                restore_info = {
                    "filename": local_backup_path.name,
                    "size": downloaded_size,
                    "timestamp": datetime.now().isoformat(),
                    "source": "r2",
                    "r2_key": backup_key,
                    "success": True
                }
                logger.info(f"✅ R2 restore completed: {local_backup_path.name}")
                return restore_info
            else:
                raise Exception("备份恢复失败")

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"❌ R2 restore failed (AWS Error {error_code}): {error_msg}")
            raise Exception(f"R2恢复失败: {error_msg}")
        except Exception as e:
            logger.error(f"❌ R2 restore failed: {e}")
            raise


# 创建全局备份服务实例
backup_service = BackupService()


async def create_backup(backup_type: str = "full") -> str:
    """创建备份"""
    return await backup_service.create_backup(backup_type)


async def list_backups() -> list:
    """列出备份"""
    return backup_service.list_backups()


async def restore_backup(backup_name: str) -> bool:
    """恢复备份"""
    return await backup_service.restore_backup(backup_name)
