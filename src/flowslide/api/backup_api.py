"""
备份管理API接口
提供REST API来管理数据备份、恢复和监控功能
"""

import os
import psutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..services.backup_service import backup_service, create_backup, list_backups
from ..database import db_manager

router = APIRouter(prefix="/api/backup", tags=["Backup Management"])
logger = logging.getLogger(__name__)


class BackupConfig(BaseModel):
    """备份配置"""
    auto_backup_enabled: bool = True
    backup_interval: int = 24  # 小时
    max_backups: int = 10
    retention_days: int = 30


@router.post("/database")
async def create_database_backup():
    """创建数据库备份"""
    try:
        logger.info("📦 Starting database backup...")

        # 创建数据库备份
        backup_path = await create_backup("db_only")

        # 获取备份信息
        backup_file = Path(backup_path)
        backup_info = {
            "filename": backup_file.name,
            "size": backup_file.stat().st_size,
            "created_at": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
            "path": str(backup_file)
        }

        logger.info(f"✅ Database backup completed: {backup_file.name}")
        return {
            "success": True,
            "message": "数据库备份创建成功",
            "backup_info": backup_info
        }

    except Exception as e:
        logger.error(f"❌ Database backup failed: {e}")
        raise HTTPException(status_code=500, detail=f"创建数据库备份失败: {str(e)}")


@router.get("/download/latest")
async def download_latest_backup():
    """下载最新的备份文件"""
    try:
        backups = await list_backups()
        if not backups:
            raise HTTPException(status_code=404, detail="没有找到备份文件")

        latest_backup = backups[0]  # 已经按时间排序
        backup_path = Path(latest_backup["path"])

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="备份文件不存在")

        return FileResponse(
            path=backup_path,
            filename=backup_path.name,
            media_type="application/zip"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download backup failed: {e}")
        raise HTTPException(status_code=500, detail=f"下载备份失败: {str(e)}")


@router.post("/sync/r2")
async def sync_to_r2():
    """同步备份到R2云存储"""
    try:
        logger.info("☁️ Starting R2 sync...")

        # 同步到R2
        sync_info = await backup_service.sync_to_r2()

        # 更新最后同步时间到环境变量
        import os
        from datetime import datetime
        os.environ["LAST_R2_SYNC_TIME"] = datetime.now().isoformat()

        # 如果有.env文件，也更新到文件
        try:
            env_file = Path(".env")
            if env_file.exists():
                content = env_file.read_text()
                if "LAST_R2_SYNC_TIME" in content:
                    # 更新现有行
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith("LAST_R2_SYNC_TIME="):
                            lines[i] = f"LAST_R2_SYNC_TIME={datetime.now().isoformat()}"
                            break
                    content = '\n'.join(lines)
                else:
                    # 添加新行
                    content += f"\nLAST_R2_SYNC_TIME={datetime.now().isoformat()}"
                env_file.write_text(content)
        except Exception as e:
            logger.warning(f"更新.env文件失败: {e}")

        logger.info(f"✅ R2 sync completed: {sync_info['filename']}")
        return {
            "success": True,
            "message": "备份同步到R2成功",
            "sync_info": sync_info
        }

    except Exception as e:
        logger.error(f"❌ R2 sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"同步到R2失败: {str(e)}")


@router.post("/restore/r2")
async def restore_from_r2():
    """从R2云存储恢复数据"""
    try:
        logger.info("🔄 Starting R2 restore...")

        # 检查R2配置
        if not backup_service._is_r2_configured():
            raise HTTPException(status_code=400, detail="R2云存储未配置")

        # 实现R2恢复逻辑
        restore_result = await backup_service.restore_from_r2()

        logger.info(f"✅ R2 restore completed: {restore_result}")
        return {
            "message": "从R2恢复成功",
            "restore_info": restore_result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ R2 restore failed: {e}")
        raise HTTPException(status_code=500, detail=f"从R2恢复失败: {str(e)}")


@router.get("/history")
async def get_backup_history():
    """获取备份历史"""
    try:
        backups = await list_backups()

        # 格式化备份信息
        formatted_backups = []
        for backup in backups:
            backup_file = Path(backup["path"])
            formatted_backups.append({
                "filename": backup["name"],
                "size": backup["size"],
                "created_at": backup["created"],
                "path": backup["path"]
            })

        return {
            "success": True,
            "backups": formatted_backups
        }

    except Exception as e:
        logger.error(f"❌ Get backup history failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取备份历史失败: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_backups():
    """清理旧备份文件"""
    try:
        logger.info("🗑️ Starting backup cleanup...")

        initial_count = len(await list_backups())

        # 清理旧备份
        await backup_service._cleanup_old_backups()

        final_count = len(await list_backups())
        deleted_count = initial_count - final_count

        logger.info(f"✅ Cleanup completed. Deleted {deleted_count} old backups")
        return {
            "success": True,
            "message": f"清理完成，删除了 {deleted_count} 个旧备份文件",
            "deleted_count": deleted_count
        }

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"清理旧备份失败: {str(e)}")


@router.get("/config")
async def get_backup_config():
    """获取备份配置"""
    try:
        config = {
            "auto_backup_enabled": os.getenv("AUTO_BACKUP_ENABLED", "true").lower() == "true",
            "backup_interval": int(os.getenv("BACKUP_INTERVAL", "24")),
            "max_backups": int(os.getenv("MAX_BACKUPS", "10")),
            "retention_days": backup_service.retention_days
        }

        return {
            "success": True,
            "config": config
        }

    except Exception as e:
        logger.error(f"❌ Get backup config failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取备份配置失败: {str(e)}")


@router.post("/config")
async def save_backup_config(config: BackupConfig):
    """保存备份配置"""
    try:
        logger.info("⚙️ Saving backup configuration...")

        # 保存配置到环境变量
        import os
        from pathlib import Path

        # 获取.env文件路径
        env_file = Path(".env")

        # 读取现有环境变量
        env_vars = {}
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()

        # 更新备份相关配置
        env_vars['AUTO_BACKUP_ENABLED'] = str(config.auto_backup_enabled).lower()
        env_vars['BACKUP_INTERVAL'] = str(config.backup_interval)
        env_vars['MAX_BACKUPS'] = str(config.max_backups)
        env_vars['BACKUP_RETENTION_DAYS'] = str(config.retention_days)

        # 写回.env文件
        with open(env_file, 'w', encoding='utf-8') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        # 更新运行时环境变量
        os.environ['AUTO_BACKUP_ENABLED'] = str(config.auto_backup_enabled).lower()
        os.environ['BACKUP_INTERVAL'] = str(config.backup_interval)
        os.environ['MAX_BACKUPS'] = str(config.max_backups)
        os.environ['BACKUP_RETENTION_DAYS'] = str(config.retention_days)

        # 更新backup_service的配置
        backup_service.retention_days = config.retention_days

        logger.info("✅ Backup configuration saved")
        return {
            "success": True,
            "message": "备份配置保存成功",
            "config": config.dict()
        }

    except Exception as e:
        logger.error(f"❌ Save backup config failed: {e}")
        raise HTTPException(status_code=500, detail=f"保存备份配置失败: {str(e)}")
