"""
部署模式切换API接口
提供REST API来管理部署模式切换
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from ..core.deployment_mode_manager import (
    mode_manager,
    DeploymentMode,
    ModeTransition,
    get_current_deployment_mode,
    is_mode_switch_in_progress
)
from ..core.deployment_config_manager import (
    config_manager,
    ModeSwitchConfig,
    get_deployment_config as core_get_deployment_config,
    save_deployment_config as core_save_deployment_config
)

router = APIRouter(tags=["deployment"])


class ModeSwitchRequest(BaseModel):
    """模式切换请求"""
    target_mode: str
    reason: Optional[str] = "API请求切换"


class ModeSwitchConfigUpdate(BaseModel):
    """模式切换配置更新"""
    enabled: Optional[bool] = None
    auto_switch: Optional[bool] = None
    check_interval: Optional[int] = None
    max_switch_attempts: Optional[int] = None
    switch_timeout: Optional[int] = None
    rollback_enabled: Optional[bool] = None
    data_backup_before_switch: Optional[bool] = None
    notify_on_switch: Optional[bool] = None
    maintenance_mode: Optional[bool] = None
    force_mode: Optional[str] = None
    preferred_modes: Optional[List[str]] = None
    restricted_modes: Optional[List[str]] = None
    switch_triggers: Optional[List[str]] = None
    load_threshold: Optional[float] = None
    error_rate_threshold: Optional[float] = None
    notification_webhook: Optional[str] = None
    notification_email: Optional[str] = None


@router.get("/mode")
async def get_current_mode():
    """获取当前部署模式"""
    try:
        current_mode = get_current_deployment_mode()
        mode_info = mode_manager.get_current_mode_info()

        return {
            "current_mode": current_mode.value,
            "detected_mode": mode_info["current_mode"],
            "switch_in_progress": mode_info["switch_in_progress"],
            "last_check": mode_info["last_mode_check"],
            "switch_context": mode_info["switch_context"]
        }
    except Exception as e:
        logger.error(f"获取当前模式失败: {e}")
        # 返回默认值而不是抛出异常
        return {
            "current_mode": DeploymentMode.LOCAL_ONLY.value,
            "detected_mode": DeploymentMode.LOCAL_ONLY.value,
            "switch_in_progress": False,
            "last_check": None,
            "switch_context": None
        }


@router.get("/modes")
async def get_available_modes():
    """获取所有可用的部署模式"""
    return {
        "modes": [mode.value for mode in DeploymentMode],
        "current_mode": get_current_deployment_mode().value,
        "descriptions": {
            "local_only": "仅本地存储",
            "local_external": "本地 + 外部数据库",
            "local_r2": "本地 + R2云存储",
            "local_external_r2": "本地 + 外部数据库 + R2云存储"
        }
    }


@router.get("/available-modes")
async def get_available_modes_based_on_config():
    """根据环境变量配置获取可用的部署模式"""
    import os

    # 检查环境变量配置（更严格判定）
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    # 仅当为非SQLite且为常见外部驱动时视为外部数据库
    has_external_db = db_url.startswith("postgresql://") or db_url.startswith("mysql://")

    # R2 需关键配置齐全才视为可用
    r2_access_key = (os.getenv("R2_ACCESS_KEY_ID") or "").strip()
    r2_secret = (os.getenv("R2_SECRET_ACCESS_KEY") or "").strip()
    r2_endpoint = (os.getenv("R2_ENDPOINT") or "").strip()
    r2_bucket = (os.getenv("R2_BUCKET_NAME") or "").strip()
    has_r2 = all([r2_access_key, r2_secret, r2_endpoint, r2_bucket])

    # 根据配置情况确定可用的模式
    available_modes = []

    # 始终可以选择本地模式
    available_modes.append({
        "mode": "local_only",
        "name": "仅本地存储",
        "description": "数据仅存储在本地数据库中",
        "available": True,
        "recommended": not has_external_db and not has_r2
    })

    # 如果有外部数据库，可以选择本地+外部模式
    if has_external_db:
        available_modes.append({
            "mode": "local_external",
            "name": "本地 + 外部数据库",
            "description": "本地数据与外部数据库同步",
            "available": True,
            "recommended": has_external_db and not has_r2
        })

    # 如果有R2配置，可以选择本地+R2模式
    if has_r2:
        available_modes.append({
            "mode": "local_r2",
            "name": "本地 + R2云存储",
            "description": "本地数据备份到R2云存储",
            "available": True,
            "recommended": not has_external_db and has_r2
        })

    # 如果既有外部数据库又有R2，可以选择全功能模式
    if has_external_db and has_r2:
        available_modes.append({
            "mode": "local_external_r2",
            "name": "本地 + 外部数据库 + R2云存储",
            "description": "完整的数据同步和备份方案",
            "available": True,
            "recommended": True
        })

    # 获取当前模式
    # 使用已初始化的当前模式，避免在此处重复触发检测导致界面闪烁
    current_mode = get_current_deployment_mode().value

    return {
        "success": True,
        "available_modes": available_modes,
        "current_mode": current_mode,
        "config_status": {
            "has_external_db": has_external_db,
            "has_r2": has_r2
        }
    }


@router.post("/switch")
async def switch_deployment_mode(request: ModeSwitchRequest, background_tasks: BackgroundTasks):
    """切换部署模式"""
    try:
        # 验证目标模式参数
        if not request.target_mode or not request.target_mode.strip():
            raise HTTPException(status_code=400, detail="目标模式不能为空")

        # 验证目标模式
        try:
            target_mode = DeploymentMode(request.target_mode.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的目标模式: {request.target_mode}")

        # 检查是否有切换正在进行
        if is_mode_switch_in_progress():
            raise HTTPException(status_code=409, detail="模式切换正在进行中，请稍后再试")

        # 检查模式兼容性
        current_mode = get_current_deployment_mode()
        
        # 检查目标模式是否已经是当前模式
        if current_mode == target_mode:
            raise HTTPException(
                status_code=400, 
                detail=f"目标模式 {target_mode.value} 已经是当前激活模式"
            )
        
        if not mode_manager._is_mode_compatible(current_mode, target_mode):
            raise HTTPException(
                status_code=400,
                detail=f"无法从 {current_mode.value} 切换到 {target_mode.value}"
            )

        # 执行模式切换（同步等待完成）
        logger.info(f"开始模式切换: {current_mode.value} -> {target_mode.value}")
        switch_success = await mode_manager.switch_mode(
            target_mode,
            request.reason or "API请求切换"
        )

        if not switch_success:
            raise HTTPException(status_code=500, detail="模式切换执行失败")

        # 验证切换结果
        new_current_mode = get_current_deployment_mode()
        if new_current_mode != target_mode:
            raise HTTPException(
                status_code=500, 
                detail=f"模式切换验证失败，当前模式仍为 {new_current_mode.value}"
            )

        return {
            "message": "模式切换已完成",
            "from_mode": current_mode.value,
            "to_mode": target_mode.value,
            "status": "completed",
            "verified": True
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动模式切换失败: {str(e)}")


@router.get("/status")
async def get_switch_status():
    """获取模式切换状态"""
    try:
        mode_info = mode_manager.get_current_mode_info()

        return {
            "switch_in_progress": mode_info["switch_in_progress"],
            "current_mode": mode_info["current_mode"],
            "switch_context": mode_info["switch_context"],
            "last_mode_check": mode_info["last_mode_check"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取切换状态失败: {str(e)}")


@router.get("/history")
async def get_mode_switch_history():
    """获取模式切换历史"""
    try:
        history = mode_manager.get_mode_history()

        return {
            "total_switches": len(history),
            "history": history[-50:]  # 返回最近50条记录
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取切换历史失败: {str(e)}")


@router.get("/config")
async def get_deployment_config():
    """获取部署配置"""
    try:
        config = core_get_deployment_config()

        return {
            "enabled": config.enabled,
            "auto_switch": config.auto_switch,
            "check_interval": config.check_interval,
            "max_switch_attempts": config.max_switch_attempts,
            "switch_timeout": config.switch_timeout,
            "rollback_enabled": config.rollback_enabled,
            "data_backup_before_switch": config.data_backup_before_switch,
            "notify_on_switch": config.notify_on_switch,
            "maintenance_mode": config.maintenance_mode,
            "force_mode": config.force_mode,
            "preferred_modes": config.preferred_modes,
            "restricted_modes": config.restricted_modes,
            "switch_triggers": config.switch_triggers,
            "load_threshold": config.load_threshold,
            "error_rate_threshold": config.error_rate_threshold,
            "notification_webhook": config.notification_webhook,
            "notification_email": config.notification_email
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取部署配置失败: {str(e)}")


@router.put("/config")
async def update_deployment_config(config_update: ModeSwitchConfigUpdate):
    """更新部署配置"""
    try:
        current_config = core_get_deployment_config()

        # 更新配置
        update_data = config_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(current_config, key):
                setattr(current_config, key, value)

        # 保存配置
        if core_save_deployment_config(current_config):
            return {
                "message": "部署配置已更新",
                "config": {
                    "enabled": current_config.enabled,
                    "auto_switch": current_config.auto_switch,
                    "check_interval": current_config.check_interval,
                    "max_switch_attempts": current_config.max_switch_attempts,
                    "switch_timeout": current_config.switch_timeout,
                    "rollback_enabled": current_config.rollback_enabled,
                    "data_backup_before_switch": current_config.data_backup_before_switch,
                    "notify_on_switch": current_config.notify_on_switch,
                    "maintenance_mode": current_config.maintenance_mode,
                    "force_mode": current_config.force_mode,
                    "preferred_modes": current_config.preferred_modes,
                    "restricted_modes": current_config.restricted_modes,
                    "switch_triggers": current_config.switch_triggers,
                    "load_threshold": current_config.load_threshold,
                    "error_rate_threshold": current_config.error_rate_threshold,
                    "notification_webhook": current_config.notification_webhook,
                    "notification_email": current_config.notification_email
                }
            }
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新部署配置失败: {str(e)}")


@router.post("/check")
async def check_mode_compatibility():
    """检查模式兼容性"""
    try:
        current_mode = get_current_deployment_mode()
        available_modes = [mode.value for mode in DeploymentMode]
        compatible_modes = mode_manager.compatibility_matrix.get(current_mode.value, [])

        return {
            "current_mode": current_mode.value,
            "available_modes": available_modes,
            "compatible_modes": compatible_modes,
            "compatibility_matrix": mode_manager.compatibility_matrix
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查模式兼容性失败: {str(e)}")


@router.post("/maintenance/{enable}")
async def set_maintenance_mode(enable: bool):
    """设置维护模式"""
    try:
        config = core_get_deployment_config()
        config.maintenance_mode = enable

        if core_save_deployment_config(config):
            return {
                "message": f"维护模式已{'启用' if enable else '禁用'}",
                "maintenance_mode": enable
            }
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置维护模式失败: {str(e)}")


@router.get("/health")
async def get_deployment_health():
    """获取部署健康状态"""
    try:
        current_mode = get_current_deployment_mode()
        switch_in_progress = is_mode_switch_in_progress()
        config = core_get_deployment_config()

        health_status = "healthy"
        issues = []

        # 检查配置问题
        if not config.enabled:
            health_status = "disabled"
            issues.append("部署模式切换已禁用")

        if config.maintenance_mode:
            health_status = "maintenance"
            issues.append("系统处于维护模式")

        if switch_in_progress:
            health_status = "switching"
            issues.append("模式切换正在进行")

        return {
            "status": health_status,
            "current_mode": current_mode.value,
            "switch_in_progress": switch_in_progress,
            "maintenance_mode": config.maintenance_mode,
            "issues": issues,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
