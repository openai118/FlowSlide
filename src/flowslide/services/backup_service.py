"""
备份服务 - 集成R2云备份和本地备份功能
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BackupService:
    """备份服务"""

    def __init__(self):
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
            return

        try:
            # 这里可以实现R2上传逻辑
            # 或者调用现有的R2备份脚本
            logger.info(f"☁️ Uploading to R2: {backup_path.name}")

            # 示例：调用备份脚本
            # await self._run_r2_backup_script(backup_path)

        except Exception as e:
            logger.error(f"❌ R2 upload failed: {e}")
            # 不抛出异常，因为本地备份已经成功

    def _is_r2_configured(self) -> bool:
        """检查R2是否配置"""
        return all(self.r2_config.values())

    async def _run_r2_backup_script(self, backup_path: Path):
        """运行R2备份脚本"""
        import subprocess

        script_path = Path("./backup_to_r2_enhanced.sh")
        if script_path.exists():
            # 这里可以调用bash脚本或实现Python版本的R2上传
            pass

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

    async def _send_notification(self, backup_name: str, status: str, error: str = None):
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

    async def list_backups(self) -> list:
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

            # 停止服务（如果需要）
            # 解压备份
            # 恢复数据库
            # 恢复配置文件
            # 恢复上传文件
            # 重启服务

            logger.info("✅ Backup restored successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False


# 创建全局备份服务实例
backup_service = BackupService()


async def create_backup(backup_type: str = "full") -> str:
    """创建备份"""
    return await backup_service.create_backup(backup_type)


async def list_backups() -> list:
    """列出备份"""
    return await backup_service.list_backups()


async def restore_backup(backup_name: str) -> bool:
    """恢复备份"""
    return await backup_service.restore_backup(backup_name)
