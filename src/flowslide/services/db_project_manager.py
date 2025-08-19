"""
Database-aware Project and TODO Board Management Service
Replaces the in-memory ProjectManager with persistent database storage
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..api.models import (
    EnhancedPPTOutline,
    PPTGenerationRequest,
    PPTOutline,
    PPTProject,
    ProjectListResponse,
    TodoBoard,
    TodoStage,
)
from ..database.database import get_async_db
from ..database.service import DatabaseService

# Configure logger for this module
logger = logging.getLogger(__name__)


class DatabaseProjectManager:
    """Database-aware project manager with persistent storage"""

    def __init__(self):
        pass

    async def _get_db_service(self) -> DatabaseService:
        """Get database service instance with a new session"""
        from ..database.database import AsyncSessionLocal

        session = AsyncSessionLocal()
        return DatabaseService(session)

    async def create_project(
        self, request: PPTGenerationRequest, owner_id: Optional[int] = None
    ) -> PPTProject:
        """Create a new PPT project with TODO board"""
        db_service = await self._get_db_service()
        try:
            project = await db_service.create_project(request, owner_id=owner_id)
            logger.info(f"Created project {project.project_id}: {project.title}")
            return project
        finally:
            await db_service.session.close()

    async def update_todo_board_after_requirements(
        self, project_id: str, confirmed_requirements: Dict[str, Any]
    ) -> bool:
        """Update TODO board after requirements confirmation"""
        db_service = await self._get_db_service()
        try:
            # Update project with confirmed requirements
            project = await db_service.get_project(project_id)
            if not project:
                return False

            # Save confirmed requirements
            await db_service.project_repo.update(
                project_id, {"confirmed_requirements": confirmed_requirements}
            )

            # Update requirements confirmation stage to completed
            await db_service.update_stage_status(
                project_id,
                "requirements_confirmation",
                "completed",
                100.0,
                confirmed_requirements,
            )

            logger.info(
                f"Updated TODO board for project {project_id} after requirements confirmation"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating TODO board: {e}")
            return False
        finally:
            await db_service.session.close()

    async def update_todo_board_with_confirmed_requirements(
        self, project_id: str, confirmed_requirements: Dict[str, Any]
    ) -> bool:
        """Compatibility method for EnhancedPPTService"""
        return await self.update_todo_board_after_requirements(project_id, confirmed_requirements)

    async def get_project(self, project_id: str) -> Optional[PPTProject]:
        """Get project by ID"""
        db_service = await self._get_db_service()
        try:
            return await db_service.get_project(project_id)
        finally:
            await db_service.session.close()

    async def list_projects(
        self,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
        owner_id: Optional[int] = None,
    ) -> ProjectListResponse:
        """List projects with pagination"""
        db_service = await self._get_db_service()
        try:
            return await db_service.list_projects(page, page_size, status, owner_id=owner_id)
        finally:
            await db_service.session.close()

    async def update_project_status(self, project_id: str, status: str) -> bool:
        """Update project status"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.update_project_status(project_id, status)

            if success:
                logger.info(f"Updated project {project_id} status to {status}")

            return success
        finally:
            await db_service.session.close()

    async def get_todo_board(self, project_id: str) -> Optional[TodoBoard]:
        """Get TODO board for project"""
        project = await self.get_project(project_id)
        return project.todo_board if project else None

    async def update_stage_status(
        self,
        project_id: str,
        stage_id: str,
        status: str,
        progress: float = None,
        result: Dict[str, Any] = None,
    ) -> bool:
        """Update stage status in TODO board"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.update_stage_status(
                project_id, stage_id, status, progress, result
            )

            if success:
                logger.info(f"Updated stage {stage_id} to {status}, progress: {progress}%")

            return success
        finally:
            await db_service.session.close()

    async def save_project_outline(self, project_id: str, outline: Dict[str, Any]) -> bool:
        """Save project outline"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.save_project_outline(project_id, outline)

            if success:
                logger.info(f"Saved outline for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def save_project_slides(
        self,
        project_id: str,
        slides_html: str,
        slides_data: List[Dict[str, Any]] = None,
    ) -> bool:
        """Save project slides using optimized batch update"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.save_project_slides(project_id, slides_html, slides_data)

            if success:
                logger.info(f"Saved slides for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def batch_save_slides(self, project_id: str, slides_data: List[Dict[str, Any]]) -> bool:
        """批量保存幻灯片 - 高效版本"""
        db_service = await self._get_db_service()
        try:
            # 准备幻灯片数据
            slides_records = []
            for i, slide_data in enumerate(slides_data):
                slide_record = {
                    "project_id": project_id,
                    "slide_index": i,
                    "slide_id": slide_data.get("slide_id", f"slide_{i}"),
                    "title": slide_data.get("title", f"Slide {i+1}"),
                    "content_type": slide_data.get("content_type", "content"),
                    "html_content": slide_data.get("html_content", ""),
                    "slide_metadata": slide_data.get("metadata", {}),
                    "is_user_edited": slide_data.get("is_user_edited", False),
                }
                slides_records.append(slide_record)

            # 使用批量upsert
            success = await db_service.slide_repo.batch_upsert_slides(project_id, slides_records)

            if success:
                logger.info(f"Batch saved {len(slides_data)} slides for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def replace_all_project_slides(
        self,
        project_id: str,
        slides_html: str,
        slides_data: List[Dict[str, Any]] = None,
    ) -> bool:
        """完全替换项目的所有幻灯片 - 用于重新生成PPT等场景"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.replace_all_project_slides(
                project_id, slides_html, slides_data
            )

            if success:
                logger.info(f"Replaced all slides for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def cleanup_excess_slides(self, project_id: str, current_slide_count: int) -> int:
        """清理多余的幻灯片"""
        db_service = await self._get_db_service()
        try:
            deleted_count = await db_service.cleanup_excess_slides(project_id, current_slide_count)
            logger.info(f"Cleaned up {deleted_count} excess slides for project {project_id}")
            return deleted_count
        finally:
            await db_service.session.close()

    async def save_single_slide(
        self, project_id: str, slide_index: int, slide_data: Dict[str, Any]
    ) -> bool:
        """Save a single slide to database immediately"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.save_single_slide(project_id, slide_index, slide_data)

            if success:
                logger.info(f"Saved slide {slide_index + 1} for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def update_project_data(self, project_id: str, update_data: Dict[str, Any]) -> bool:
        """Update project data without affecting individual slides"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.update_project(project_id, update_data)

            if success:
                logger.info(f"Updated project data for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def update_project(self, project_id: str, update_data: Dict[str, Any]) -> bool:
        """Alias for update_project_data for backward compatibility"""
        return await self.update_project_data(project_id, update_data)

    async def save_project_version(self, project_id: str, version_data: Dict[str, Any]) -> bool:
        """Save a version of the project"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.save_project_version(project_id, version_data)

            if success:
                logger.info(f"Saved new version for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def get_project_versions(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all versions of a project"""
        db_service = await self._get_db_service()
        try:
            project = await db_service.get_project(project_id)

            if not project:
                return []

            return project.versions
        finally:
            await db_service.session.close()

    async def save_confirmed_requirements(
        self, project_id: str, requirements: Dict[str, Any]
    ) -> bool:
        """Save confirmed requirements for a project"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.project_repo.update(
                project_id, {"confirmed_requirements": requirements}
            )

            if success:
                logger.info(f"Saved confirmed requirements for project {project_id}")

            return success is not None
        finally:
            await db_service.session.close()

    async def get_confirmed_requirements(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get confirmed requirements for a project"""
        project = await self.get_project(project_id)
        return project.confirmed_requirements if project else None

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.project_repo.delete(project_id)

            if success:
                logger.info(f"Deleted project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def update_project_metadata(self, project_id: str, metadata: Dict[str, Any]) -> bool:
        """Update project metadata"""
        db_service = await self._get_db_service()
        try:
            success = await db_service.project_repo.update(
                project_id, {"project_metadata": metadata}
            )

            if success:
                logger.info(f"Updated metadata for project {project_id}")

            return success
        finally:
            await db_service.session.close()

    async def archive_project(self, project_id: str) -> bool:
        """Archive a project"""
        return await self.update_project_status(project_id, "archived")

    async def complete_project(self, project_id: str) -> bool:
        """Mark project as completed"""
        return await self.update_project_status(project_id, "completed")

    async def start_stage(self, project_id: str, stage_id: str) -> bool:
        """Start a specific stage"""
        return await self.update_stage_status(project_id, stage_id, "running", 0.0)

    async def complete_stage(
        self, project_id: str, stage_id: str, result: Dict[str, Any] = None
    ) -> bool:
        """Complete a specific stage"""
        return await self.update_stage_status(project_id, stage_id, "completed", 100.0, result)

    async def fail_stage(self, project_id: str, stage_id: str, error_message: str) -> bool:
        """Mark a stage as failed"""
        result = {"error": error_message, "timestamp": time.time()}
        return await self.update_stage_status(project_id, stage_id, "failed", 0.0, result)

    async def close(self):
        """Close database connections - no longer needed as we use per-request sessions"""
        pass
