"""
Database management API endpoints
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database.health_check import health_checker
from ..database.migrations import migration_manager
from ..services.db_project_manager import DatabaseProjectManager

router = APIRouter(prefix="/api/database", tags=["database"])
logger = logging.getLogger(__name__)


class HealthCheckResponse(BaseModel):
    """Health check response model"""

    overall_status: str
    timestamp: float
    critical_failures: List[str]
    checks: Dict[str, Any]
    summary: Dict[str, int]


class MigrationStatusResponse(BaseModel):
    """Migration status response model"""

    current_version: Optional[str]
    applied_migrations: List[str]
    available_migrations: List[str]
    pending_migrations: List[str]


class DatabaseStatsResponse(BaseModel):
    """Database statistics response model"""

    status: str
    stats: Dict[str, Any]
    timestamp: float


@router.get("/health", response_model=HealthCheckResponse)
async def get_database_health(
    checks: Optional[List[str]] = Query(None, description="Specific checks to run")
):
    """
    Get database health status

    Available checks:
    - connection: Database connection test
    - tables: Table existence and structure
    - data_integrity: Data integrity and relationships
    - performance: Database performance metrics
    - storage: Storage usage and optimization
    """
    try:
        result = await health_checker.run_health_check(checks)
        return HealthCheckResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/quick")
async def get_quick_health_check():
    """
    Quick health check (connection only)
    """
    try:
        result = await health_checker.run_health_check(["connection"])
        return {
            "status": result["overall_status"],
            "timestamp": result["timestamp"],
            "connection": result["checks"]["connection"]["status"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick health check failed: {str(e)}")


@router.get("/stats", response_model=DatabaseStatsResponse)
async def get_database_stats():
    """
    Get comprehensive database statistics
    """
    try:
        result = await health_checker.get_database_stats()
        return DatabaseStatsResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {str(e)}")


@router.get("/migrations/status", response_model=MigrationStatusResponse)
async def get_migration_status():
    """
    Get database migration status
    """
    try:
        result = await migration_manager.get_migration_status()
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return MigrationStatusResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get migration status: {str(e)}")


@router.post("/migrations/run")
async def run_migrations(target_version: Optional[str] = None, rollback: bool = False):
    """
    Run database migrations

    - target_version: Target migration version (optional)
    - rollback: Whether to rollback migrations (requires target_version)
    """
    try:
        if rollback:
            if not target_version:
                raise HTTPException(status_code=400, detail="Target version required for rollback")
            success = await migration_manager.migrate_down(target_version)
            action = "rollback"
        else:
            success = await migration_manager.migrate_up(target_version)
            action = "migration"

        if success:
            return {
                "status": "success",
                "message": f"Database {action} completed successfully",
                "target_version": target_version,
            }
        else:
            raise HTTPException(status_code=500, detail=f"Database {action} failed")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration operation failed: {str(e)}")


@router.get("/projects/summary")
async def get_projects_summary():
    """
    Get summary of projects in database
    """
    try:
        project_manager = DatabaseProjectManager()

        # Get project list
        project_list = await project_manager.list_projects(page=1, page_size=100)

        # Calculate summary statistics
        total_projects = project_list.total
        status_counts = {}
        scenario_counts = {}

        for project in project_list.projects:
            # Count by status
            status = project.status
            status_counts[status] = status_counts.get(status, 0) + 1

            # Count by scenario
            scenario = project.scenario
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

        await project_manager.close()

        return {
            "total_projects": total_projects,
            "status_distribution": status_counts,
            "scenario_distribution": scenario_counts,
            "recent_projects": len([p for p in project_list.projects[:10]]),  # Last 10 projects
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get projects summary: {str(e)}")


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """
    Delete a project from database
    """
    try:
        project_manager = DatabaseProjectManager()

        # Check if project exists
        project = await project_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Delete project
        success = await project_manager.delete_project(project_id)
        await project_manager.close()

        if success:
            return {
                "status": "success",
                "message": f"Project {project_id} deleted successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete project")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


@router.post("/cleanup/orphaned")
async def cleanup_orphaned_data():
    """
    Clean up orphaned data in database
    """
    try:
        from sqlalchemy import text

        from ..database.database import AsyncSessionLocal

        cleanup_results = {}

        async with AsyncSessionLocal() as session:
            # Clean up orphaned todo_boards
            result = await session.execute(
                text(
                    """
                DELETE FROM todo_boards
                WHERE project_id NOT IN (SELECT project_id FROM projects)
            """
                )
            )
            cleanup_results["orphaned_todo_boards"] = result.rowcount

            # Clean up orphaned todo_stages
            result = await session.execute(
                text(
                    """
                DELETE FROM todo_stages
                WHERE todo_board_id NOT IN (SELECT id FROM todo_boards)
            """
                )
            )
            cleanup_results["orphaned_todo_stages"] = result.rowcount

            # Clean up orphaned slide_data
            result = await session.execute(
                text(
                    """
                DELETE FROM slide_data
                WHERE project_id NOT IN (SELECT project_id FROM projects)
            """
                )
            )
            cleanup_results["orphaned_slide_data"] = result.rowcount

            # Clean up orphaned project_versions
            result = await session.execute(
                text(
                    """
                DELETE FROM project_versions
                WHERE project_id NOT IN (SELECT project_id FROM projects)
            """
                )
            )
            cleanup_results["orphaned_project_versions"] = result.rowcount

            await session.commit()

        total_cleaned = sum(cleanup_results.values())

        return {
            "status": "success",
            "message": f"Cleaned up {total_cleaned} orphaned records",
            "details": cleanup_results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/backup/info")
async def get_backup_info():
    """
    Get backup information and recommendations
    """
    try:
        import os

        from ..core.config import app_config

        # Get database file info
        db_url = app_config.database_url
        if db_url.startswith("sqlite:///"):
            db_file = db_url.replace("sqlite:///", "")
            if db_file.startswith("./"):
                db_file = db_file[2:]

            if os.path.exists(db_file):
                file_size = os.path.getsize(db_file)
                file_modified = os.path.getmtime(db_file)

                return {
                    "database_type": "SQLite",
                    "database_file": db_file,
                    "file_size_bytes": file_size,
                    "file_size_mb": round(file_size / (1024 * 1024), 2),
                    "last_modified": file_modified,
                    "backup_recommendation": "Use 'python manage_database.py backup <filename>' to create backup",
                    "restore_recommendation": "Use 'python manage_database.py restore <filename>' to restore backup",
                }
            else:
                return {
                    "database_type": "SQLite",
                    "database_file": db_file,
                    "status": "not_found",
                    "message": "Database file not found",
                }
        else:
            return {
                "database_type": "Other",
                "database_url": db_url,
                "backup_recommendation": "Use database-specific backup tools",
                "message": "Backup info only available for SQLite databases",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup info: {str(e)}")


# 同步相关API端点
class SyncStatusResponse(BaseModel):
    """同步状态响应模型"""
    enabled: bool
    running: bool
    last_sync: Optional[str]
    mode: str
    interval: int
    directions: List[str]
    external_db_type: Optional[str]
    external_db_configured: bool


class SyncTriggerResponse(BaseModel):
    """同步触发响应模型"""
    status: str
    message: str


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status():
    """获取数据同步状态"""
    try:
        from ..services.data_sync_service import get_sync_status
        status = await get_sync_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.post("/sync/trigger", response_model=SyncTriggerResponse)
async def trigger_manual_sync():
    """手动触发数据同步"""
    try:
        from ..services.data_sync_service import trigger_manual_sync
        result = await trigger_manual_sync()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger sync: {str(e)}")


@router.post("/sync/to-external")
async def sync_to_external():
    """同步本地数据到外部数据库"""
    try:
        from ..database import db_manager
        from ..services.data_sync_service import sync_service

        if not db_manager.external_engine:
            raise HTTPException(status_code=400, detail="外部数据库未配置")

        logger.info("🔄 Starting manual sync to external database...")

        # 执行本地到外部的同步
        await sync_service._sync_local_to_external()

        return {
            "success": True,
            "message": "数据同步到外部数据库成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Sync to external failed: {e}")
        raise HTTPException(status_code=500, detail=f"同步到外部数据库失败: {str(e)}")


@router.post("/sync/from-external")
async def sync_from_external():
    """从外部数据库恢复数据到本地"""
    try:
        from ..database import db_manager
        from ..services.data_sync_service import sync_service

        if not db_manager.external_engine:
            raise HTTPException(status_code=400, detail="外部数据库未配置")

        logger.info("🔄 Starting manual sync from external database...")

        # 执行外部到本地的同步
        await sync_service._sync_external_to_local()

        return {
            "success": True,
            "message": "从外部数据库恢复数据成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Sync from external failed: {e}")
        raise HTTPException(status_code=500, detail=f"从外部数据库恢复失败: {str(e)}")


@router.get("/sync/config")
async def get_sync_config():
    """获取同步配置信息"""
    try:
        import os
        from ..database import db_manager

        config = {
            "sync_interval_seconds": int(os.getenv("SYNC_INTERVAL", "300")),
            "sync_mode": os.getenv("SYNC_MODE", "incremental"),
            "database_mode": os.getenv("DATABASE_MODE", "local"),
            "external_database_configured": bool(db_manager.external_url),
            "external_database_type": db_manager.database_type if db_manager.external_engine else None,
            "sync_enabled": db_manager.sync_enabled,
            "sync_directions": [],
            "recommendations": []
        }

        # 根据配置给出建议
        if not db_manager.external_url:
            config["recommendations"].append("未配置外部数据库，数据同步已禁用")
        elif db_manager.sync_enabled:
            config["sync_directions"] = ["local_to_external", "external_to_local"]
            config["recommendations"].append("双向同步已启用：本地 ↔ 外部数据库")
        elif db_manager.database_type == "postgresql":
            config["sync_directions"] = ["external_to_local"]
            config["recommendations"].append("单向同步已启用：外部数据库 → 本地数据库")

        return config

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync config: {str(e)}")
