"""
Repository classes for database operations
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    GlobalMasterTemplate,
    PPTTemplate,
    Project,
    ProjectVersion,
    SlideData,
    TodoBoard,
    TodoStage,
)

logger = logging.getLogger(__name__)


def _normalize_image_entry(entry: dict) -> dict:
    """Convert various image-like dict shapes into a compact storage-reference form.

    Keeps absolute_url when available, and produces a `storage` object with
    provider/bucket/object_key/cache_key when possible. If the entry is a
    data URI it is left untouched (client should have uploaded via presign).
    """
    try:
        if not isinstance(entry, dict):
            return entry

        # direct storage-style fields
        object_key = entry.get("object_key") or entry.get("image_id")
        cache_key = entry.get("cache_key")
        absolute_url = entry.get("absolute_url") or entry.get("url") or entry.get("local_path")

        # src handling (data:, s3://, http://)
        src = entry.get("src")
        if isinstance(src, str):
            if src.startswith("data:"):
                # leave embedded data URIs as-is — they should be converted client-side
                return entry
            if src.startswith("s3://") or src.startswith("/api/image/view/") or src.startswith("http"):
                # prefer using the src as absolute_url
                absolute_url = absolute_url or src
                if src.startswith("s3://"):
                    # s3://bucket/key
                    try:
                        _, rest = src.split("s3://", 1)
                        if "/" in rest:
                            bucket, key = rest.split("/", 1)
                        else:
                            bucket, key = rest, ""
                        object_key = object_key or key
                        cache_key = cache_key or object_key
                        storage = {"provider": "s3", "bucket": bucket, "object_key": object_key}
                        if cache_key:
                            storage["cache_key"] = cache_key
                        return {"storage": storage, "image_id": object_key, "absolute_url": absolute_url}
                    except Exception:
                        pass

        # If we already have an object_key or image_id assume it's a storage ref
        if object_key:
            storage = {"provider": entry.get("provider") or "s3", "object_key": object_key}
            if entry.get("bucket"):
                storage["bucket"] = entry.get("bucket")
            if cache_key:
                storage["cache_key"] = cache_key
            out = {"storage": storage, "image_id": object_key}
            if absolute_url:
                out["absolute_url"] = absolute_url
            return out

        # fallback: return original entry
        return entry
    except Exception:
        return entry


def _normalize_slides_for_outbox(slides: list) -> list:
    """Recursively normalize slides_data so image-like dicts become storage refs.

    This is defensive: it will not modify plain strings or other content. It
    traverses lists/dicts and converts any dict that contains common image keys.
    """
    def walk(obj):
        if isinstance(obj, list):
            return [walk(i) for i in obj]
        if isinstance(obj, dict):
            # detect image-like dicts quickly
            keys = set(obj.keys())
            if keys & {"image_id", "object_key", "absolute_url", "src", "local_path", "cache_key"}:
                return _normalize_image_entry(obj)
            return {k: walk(v) for k, v in obj.items()}
        return obj

    if not isinstance(slides, list):
        return slides
    return [walk(s) for s in slides]


class ProjectRepository:
    """Repository for Project operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_data: Dict[str, Any]) -> Project:
        """Create a new project"""
        project = Project(**project_data)
        self.session.add(project)
        # flush so generated defaults (ids/project_id) are available before enqueue
        await self.session.flush()
        # enqueue outbox to push this new project to external DB asynchronously
        try:
            import json
            from ..services.data_sync_service import sync_service

            slides_data_normalized = _normalize_slides_for_outbox(getattr(project, 'slides_data', None) or [])
            payload = json.dumps({
                "project_id": project.project_id,
                "title": project.title,
                "scenario": getattr(project, 'scenario', None),
                "topic": getattr(project, 'topic', None),
                "requirements": getattr(project, 'requirements', None),
                "status": getattr(project, 'status', None),
                "owner_id": getattr(project, 'owner_id', None),
                "outline": getattr(project, 'outline', None),
                "slides_html": getattr(project, 'slides_html', None),
                "slides_data": slides_data_normalized,
                "confirmed_requirements": getattr(project, 'confirmed_requirements', None),
                "project_metadata": getattr(project, 'project_metadata', None),
                "version": getattr(project, 'version', None),
                "created_at": getattr(project, 'created_at', None),
                "updated_at": getattr(project, 'updated_at', None),
            }, ensure_ascii=False)
            # Prefer to enqueue within the current session to keep outbox atomic with business changes
            try:
                await sync_service.enqueue_outbox_session(self.session, 'presentation_upsert', payload)
            except Exception:
                # Fallback to global enqueue which uses a separate session
                sync_service.enqueue_outbox('presentation_upsert', payload)
        except Exception:
            pass
        # now commit flushed changes and outbox atomically
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """Get project by ID with all relationships"""
        stmt = (
            select(Project)
            .where(Project.project_id == project_id)
            .options(
                selectinload(Project.todo_board).selectinload(TodoBoard.stages),
                selectinload(Project.versions),
                selectinload(Project.slides),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_projects(
        self,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
        owner_id: Optional[int] = None,
    ) -> List[Project]:
        """List projects with pagination"""
        stmt = select(Project).options(
            selectinload(Project.todo_board).selectinload(TodoBoard.stages),
            selectinload(Project.versions),
            selectinload(Project.slides),
        )

        if status:
            stmt = stmt.where(Project.status == status)
        if owner_id is not None:
            stmt = stmt.where((Project.owner_id == owner_id))

        stmt = stmt.order_by(Project.updated_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_projects(
        self, status: Optional[str] = None, owner_id: Optional[int] = None
    ) -> int:
        """Count total projects"""
        from sqlalchemy import func

        stmt = select(func.count(Project.id))
        if status:
            stmt = stmt.where(Project.status == status)
        if owner_id is not None:
            stmt = stmt.where((Project.owner_id == owner_id))

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def update(self, project_id: str, update_data: Dict[str, Any]) -> Optional[Project]:
        """Update project"""
        try:
            # 首先获取项目
            project = await self.get_by_id(project_id)
            if not project:
                logger.warning(f"No project found with ID {project_id} for update")
                return None

            # 更新项目属性
            for key, value in update_data.items():
                if hasattr(project, key):
                    setattr(project, key, value)

            # 设置更新时间
            project.updated_at = time.time()

            # flush changes so they are visible to session-local outbox insert
            await self.session.flush()

            logger.info(f"Successfully updated project {project_id}")
            # enqueue outbox to push updated project to external DB asynchronously
            try:
                import json
                from ..services.data_sync_service import sync_service

                slides_data_normalized = _normalize_slides_for_outbox(getattr(project, 'slides_data', None) or [])
                payload = json.dumps({
                    "project_id": project.project_id,
                    "title": project.title,
                    "scenario": getattr(project, 'scenario', None),
                    "topic": getattr(project, 'topic', None),
                    "requirements": getattr(project, 'requirements', None),
                    "status": getattr(project, 'status', None),
                    "owner_id": getattr(project, 'owner_id', None),
                    "outline": getattr(project, 'outline', None),
                    "slides_html": getattr(project, 'slides_html', None),
                    "slides_data": slides_data_normalized,
                    "confirmed_requirements": getattr(project, 'confirmed_requirements', None),
                    "project_metadata": getattr(project, 'project_metadata', None),
                    "version": getattr(project, 'version', None),
                    "created_at": getattr(project, 'created_at', None),
                    "updated_at": getattr(project, 'updated_at', None),
                }, ensure_ascii=False)
                try:
                    await sync_service.enqueue_outbox_session(self.session, 'presentation_upsert', payload)
                except Exception:
                    sync_service.enqueue_outbox('presentation_upsert', payload)
            except Exception:
                pass
            await self.session.commit()
            await self.session.refresh(project)
            return project

        except Exception as e:
            logger.error(f"Error updating project {project_id}: {e}")
            await self.session.rollback()
            raise

    async def delete(self, project_id: str) -> bool:
        """Delete project and all dependent records to avoid FK constraint errors.

        This method deletes TodoStage, TodoBoard, SlideData, PPTTemplate and
        ProjectVersion rows that reference the project, then deletes the Project
        row. All deletes are performed in the current session and committed once.
        On error the transaction is rolled back and the exception is raised.
        """
        try:
            # Delete todo stages (they reference project_id and todo_board)
            await self.session.execute(delete(TodoStage).where(TodoStage.project_id == project_id))

            # Delete todo board (one-to-one with project)
            await self.session.execute(delete(TodoBoard).where(TodoBoard.project_id == project_id))

            # Delete slide data and templates that reference the project
            await self.session.execute(delete(SlideData).where(SlideData.project_id == project_id))
            await self.session.execute(delete(PPTTemplate).where(PPTTemplate.project_id == project_id))

            # Delete project versions
            await self.session.execute(delete(ProjectVersion).where(ProjectVersion.project_id == project_id))

            # Finally delete the project itself
            result = await self.session.execute(delete(Project).where(Project.project_id == project_id))

            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            await self.session.rollback()
            raise


class TodoBoardRepository:
    """Repository for TodoBoard operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, board_data: Dict[str, Any]) -> TodoBoard:
        """Create a new todo board"""
        board = TodoBoard(**board_data)
        self.session.add(board)
        await self.session.commit()
        await self.session.refresh(board)
        return board

    async def get_by_project_id(self, project_id: str) -> Optional[TodoBoard]:
        """Get todo board by project ID"""
        stmt = (
            select(TodoBoard)
            .where(TodoBoard.project_id == project_id)
            .options(selectinload(TodoBoard.stages))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, project_id: str, update_data: Dict[str, Any]) -> Optional[TodoBoard]:
        """Update todo board"""
        update_data["updated_at"] = time.time()
        stmt = update(TodoBoard).where(TodoBoard.project_id == project_id).values(**update_data)
        await self.session.execute(stmt)
        await self.session.commit()
        return await self.get_by_project_id(project_id)


class TodoStageRepository:
    """Repository for TodoStage operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_stages(self, stages_data: List[Dict[str, Any]]) -> List[TodoStage]:
        """Create multiple stages"""
        stages = [TodoStage(**stage_data) for stage_data in stages_data]
        self.session.add_all(stages)
        await self.session.commit()
        for stage in stages:
            await self.session.refresh(stage)
        return stages

    async def update_stage(self, stage_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a specific stage"""
        update_data["updated_at"] = time.time()
        stmt = update(TodoStage).where(TodoStage.stage_id == stage_id).values(**update_data)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def update_stage_by_project_and_stage(
        self, project_id: str, stage_id: str, update_data: Dict[str, Any]
    ) -> bool:
        """Update a specific stage by project_id and stage_id for better performance"""
        update_data["updated_at"] = time.time()
        stmt = (
            update(TodoStage)
            .where(TodoStage.project_id == project_id, TodoStage.stage_id == stage_id)
            .values(**update_data)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_stages_by_board_id(self, board_id: int) -> List[TodoStage]:
        """Get all stages for a todo board"""
        stmt = (
            select(TodoStage)
            .where(TodoStage.todo_board_id == board_id)
            .order_by(TodoStage.stage_index)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ProjectVersionRepository:
    """Repository for ProjectVersion operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, version_data: Dict[str, Any]) -> ProjectVersion:
        """Create a new project version"""
        version = ProjectVersion(**version_data)
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def get_versions_by_project_id(self, project_id: str) -> List[ProjectVersion]:
        """Get all versions for a project"""
        stmt = (
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class SlideDataRepository:
    """Repository for SlideData operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_slides(self, slides_data: List[Dict[str, Any]]) -> List[SlideData]:
        """Create multiple slides"""
        slides = [SlideData(**slide_data) for slide_data in slides_data]
        self.session.add_all(slides)
        await self.session.commit()
        for slide in slides:
            await self.session.refresh(slide)
        return slides

    async def create_single_slide(self, slide_data: Dict[str, Any]) -> SlideData:
        """Create a single slide"""
        slide = SlideData(**slide_data)
        self.session.add(slide)
        await self.session.commit()
        await self.session.refresh(slide)
        # enqueue outbox for slide upsert
        try:
            import json
            from ..services.data_sync_service import sync_service
            payload = json.dumps({
                "project_id": slide.project_id,
                "slide_index": slide.slide_index,
                "content": getattr(slide, 'content', None),
                "updated_at": slide.updated_at,
            }, ensure_ascii=False)
            try:
                await sync_service.enqueue_outbox_session(self.session, 'presentation_upsert', payload)
            except Exception:
                sync_service.enqueue_outbox('presentation_upsert', payload)
        except Exception:
            pass
        return slide

    async def upsert_slide(
        self, project_id: str, slide_index: int, slide_data: Dict[str, Any]
    ) -> SlideData:
        """Insert or update a single slide"""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(f"🔄 数据库仓库开始upsert幻灯片: 项目ID={project_id}, 索引={slide_index}")

        # Check if slide already exists
        stmt = select(SlideData).where(
            SlideData.project_id == project_id, SlideData.slide_index == slide_index
        )
        result = await self.session.execute(stmt)
        existing_slide = result.scalar_one_or_none()

        if existing_slide:
            # Update existing slide
            logger.info(
                f"📝 更新现有幻灯片: 数据库ID={existing_slide.id}, 项目ID={project_id}, 索引={slide_index}"
            )
            slide_data["updated_at"] = time.time()

            updated_fields = []
            for key, value in slide_data.items():
                if hasattr(existing_slide, key):
                    old_value = getattr(existing_slide, key)
                    if old_value != value:
                        setattr(existing_slide, key, value)
                        updated_fields.append(key)

            logger.info(f"📊 更新的字段: {updated_fields}")
            await self.session.commit()
            await self.session.refresh(existing_slide)
            logger.info(f"✅ 幻灯片更新成功: 数据库ID={existing_slide.id}")
            # enqueue outbox for slide upsert
            try:
                import json
                from ..services.data_sync_service import sync_service
                payload = json.dumps({
                    "project_id": existing_slide.project_id,
                    "slide_index": existing_slide.slide_index,
                    "content": getattr(existing_slide, 'content', None),
                    "updated_at": existing_slide.updated_at,
                }, ensure_ascii=False)
                try:
                    await sync_service.enqueue_outbox_session(self.session, 'presentation_upsert', payload)
                except Exception:
                    sync_service.enqueue_outbox('presentation_upsert', payload)
            except Exception:
                pass
            return existing_slide
        else:
            # Create new slide
            logger.info(f"➕ 创建新幻灯片: 项目ID={project_id}, 索引={slide_index}")
            slide_data["created_at"] = time.time()
            slide_data["updated_at"] = time.time()
            new_slide = await self.create_single_slide(slide_data)
            logger.info(f"✅ 新幻灯片创建成功: 数据库ID={new_slide.id}")
            return new_slide

    async def get_slides_by_project_id(self, project_id: str) -> List[SlideData]:
        """Get all slides for a project"""
        stmt = (
            select(SlideData)
            .where(SlideData.project_id == project_id)
            .order_by(SlideData.slide_index)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_slide(self, slide_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a specific slide"""
        update_data["updated_at"] = time.time()
        stmt = update(SlideData).where(SlideData.slide_id == slide_id).values(**update_data)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def delete_slides_by_project_id(self, project_id: str) -> bool:
        """Delete all slides for a project"""
        stmt = delete(SlideData).where(SlideData.project_id == project_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def delete_slides_after_index(self, project_id: str, start_index: int) -> int:
        """Delete slides with index >= start_index for a project"""
        logger.debug(f"🗑️ 删除项目 {project_id} 中索引 >= {start_index} 的幻灯片")
        stmt = delete(SlideData).where(
            and_(SlideData.project_id == project_id, SlideData.slide_index >= start_index)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        deleted_count = result.rowcount
        logger.debug(f"✅ 成功删除 {deleted_count} 张多余的幻灯片")
        return deleted_count

    async def batch_upsert_slides(self, project_id: str, slides_data: List[Dict[str, Any]]) -> bool:
        """批量插入或更新幻灯片 - 优化版本"""
        logger.debug(f"🔄 开始批量upsert幻灯片: 项目ID={project_id}, 数量={len(slides_data)}")

        try:
            # 获取现有幻灯片
            existing_slides_stmt = select(SlideData).where(SlideData.project_id == project_id)
            result = await self.session.execute(existing_slides_stmt)
            existing_slides = {slide.slide_index: slide for slide in result.scalars().all()}

            updated_count = 0
            created_count = 0
            current_time = time.time()

            # 批量处理幻灯片
            for i, slide_data in enumerate(slides_data):
                slide_index = i

                if slide_index in existing_slides:
                    # 更新现有幻灯片
                    existing_slide = existing_slides[slide_index]
                    slide_data["updated_at"] = current_time

                    # 只更新有变化的字段
                    has_changes = False
                    for key, value in slide_data.items():
                        if hasattr(existing_slide, key) and getattr(existing_slide, key) != value:
                            setattr(existing_slide, key, value)
                            has_changes = True

                    if has_changes:
                        updated_count += 1
                else:
                    # 创建新幻灯片
                    slide_data.update(
                        {
                            "project_id": project_id,
                            "slide_index": slide_index,
                            "created_at": current_time,
                            "updated_at": current_time,
                        }
                    )
                    new_slide = SlideData(**slide_data)
                    self.session.add(new_slide)
                    created_count += 1

            # 一次性提交所有更改
            await self.session.commit()

            logger.debug(f"✅ 批量upsert完成: 更新={updated_count}, 创建={created_count}")
            return True

        except Exception as e:
            logger.error(f"❌ 批量upsert失败: {e}")
            await self.session.rollback()
            return False

    async def update_slide_user_edited_status(
        self, project_id: str, slide_index: int, is_user_edited: bool = True
    ) -> bool:
        """Update the user edited status for a specific slide"""
        stmt = (
            update(SlideData)
            .where(SlideData.project_id == project_id, SlideData.slide_index == slide_index)
            .values(is_user_edited=is_user_edited, updated_at=time.time())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0


class PPTTemplateRepository:
    """Repository for PPT template operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_template(self, template_data: Dict[str, Any]) -> PPTTemplate:
        """Create a new PPT template"""
        template_data["created_at"] = time.time()
        template_data["updated_at"] = time.time()
        template = PPTTemplate(**template_data)
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        # enqueue outbox for template upsert
        try:
            import json
            from ..services.data_sync_service import sync_service
            payload = json.dumps({
                "id": template.id,
                "project_id": template.project_id,
                "template_type": template.template_type,
                "template_name": template.template_name,
                "description": template.description,
                "html_template": template.html_template,
                "applicable_scenarios": template.applicable_scenarios,
                "style_config": template.style_config,
                "usage_count": template.usage_count,
                "created_at": template.created_at,
                "updated_at": template.updated_at,
            }, ensure_ascii=False)
            try:
                await sync_service.enqueue_outbox_session(self.session, 'template_upsert', payload)
            except Exception:
                sync_service.enqueue_outbox('template_upsert', payload)
        except Exception:
            pass
        return template

    async def get_template_by_id(self, template_id: int) -> Optional[PPTTemplate]:
        """Get template by ID"""
        stmt = select(PPTTemplate).where(PPTTemplate.id == template_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_templates_by_project_id(self, project_id: str) -> List[PPTTemplate]:
        """Get all templates for a project"""
        stmt = (
            select(PPTTemplate)
            .where(PPTTemplate.project_id == project_id)
            .order_by(PPTTemplate.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_templates_by_type(self, project_id: str, template_type: str) -> List[PPTTemplate]:
        """Get templates by type for a project"""
        stmt = (
            select(PPTTemplate)
            .where(
                PPTTemplate.project_id == project_id,
                PPTTemplate.template_type == template_type,
            )
            .order_by(PPTTemplate.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_template(self, template_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a template"""
        update_data["updated_at"] = time.time()
        stmt = update(PPTTemplate).where(PPTTemplate.id == template_id).values(**update_data)
        result = await self.session.execute(stmt)
        await self.session.commit()
        # enqueue outbox for template upsert (updated)
        try:
            import json
            from ..services.data_sync_service import sync_service
            tpl = await self.get_template_by_id(template_id)
            if tpl:
                payload = json.dumps({
                    "id": tpl.id,
                    "project_id": tpl.project_id,
                    "template_type": tpl.template_type,
                    "template_name": tpl.template_name,
                    "description": tpl.description,
                    "html_template": tpl.html_template,
                    "applicable_scenarios": tpl.applicable_scenarios,
                    "style_config": tpl.style_config,
                    "usage_count": tpl.usage_count,
                    "created_at": tpl.created_at,
                    "updated_at": tpl.updated_at,
                }, ensure_ascii=False)
                try:
                    await sync_service.enqueue_outbox_session(self.session, 'template_upsert', payload)
                except Exception:
                    sync_service.enqueue_outbox('template_upsert', payload)
        except Exception:
            pass
        return result.rowcount > 0

    async def increment_usage_count(self, template_id: int) -> bool:
        """Increment template usage count"""
        stmt = (
            update(PPTTemplate)
            .where(PPTTemplate.id == template_id)
            .values(usage_count=PPTTemplate.usage_count + 1, updated_at=time.time())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def delete_template(self, template_id: int) -> bool:
        """Delete a template"""
        stmt = delete(PPTTemplate).where(PPTTemplate.id == template_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0


class GlobalMasterTemplateRepository:
    """Repository for Global Master Template operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_template(self, template_data: Dict[str, Any]) -> GlobalMasterTemplate:
        """Create a new global master template"""
        template_data["created_at"] = time.time()
        template_data["updated_at"] = time.time()
        template = GlobalMasterTemplate(**template_data)
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def get_template_by_id(self, template_id: int) -> Optional[GlobalMasterTemplate]:
        """Get template by ID"""
        stmt = select(GlobalMasterTemplate).where(GlobalMasterTemplate.id == template_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_template_by_name(self, template_name: str) -> Optional[GlobalMasterTemplate]:
        """Get template by name"""
        stmt = select(GlobalMasterTemplate).where(
            GlobalMasterTemplate.template_name == template_name
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_templates(self, active_only: bool = True) -> List[GlobalMasterTemplate]:
        """Get all global master templates"""
        stmt = select(GlobalMasterTemplate)
        if active_only:
            stmt = stmt.where(GlobalMasterTemplate.is_active == True)
        stmt = stmt.order_by(
            GlobalMasterTemplate.is_default.desc(),
            GlobalMasterTemplate.usage_count.desc(),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_templates_by_tags(
        self, tags: List[str], active_only: bool = True
    ) -> List[GlobalMasterTemplate]:
        """Get templates by tags"""
        stmt = select(GlobalMasterTemplate)
        if active_only:
            stmt = stmt.where(GlobalMasterTemplate.is_active == True)

        # Filter by tags (any tag matches)
        for tag in tags:
            stmt = stmt.where(GlobalMasterTemplate.tags.contains([tag]))

        stmt = stmt.order_by(GlobalMasterTemplate.usage_count.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_templates_paginated(
        self,
        active_only: bool = True,
        offset: int = 0,
        limit: int = 6,
        search: Optional[str] = None,
    ) -> Tuple[List[GlobalMasterTemplate], int]:
        """Get templates with pagination"""
        from sqlalchemy import func, or_

        # Base query
        stmt = select(GlobalMasterTemplate)
        count_stmt = select(func.count(GlobalMasterTemplate.id))

        if active_only:
            stmt = stmt.where(GlobalMasterTemplate.is_active == True)
            count_stmt = count_stmt.where(GlobalMasterTemplate.is_active == True)

        # Add search filter
        if search and search.strip():
            search_filter = or_(
                GlobalMasterTemplate.template_name.ilike(f"%{search}%"),
                GlobalMasterTemplate.description.ilike(f"%{search}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Order and paginate
        stmt = (
            stmt.order_by(
                GlobalMasterTemplate.is_default.desc(),
                GlobalMasterTemplate.usage_count.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        # Execute queries
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)

        templates = result.scalars().all()
        total_count = count_result.scalar()

        return templates, total_count

    async def get_templates_by_tags_paginated(
        self,
        tags: List[str],
        active_only: bool = True,
        offset: int = 0,
        limit: int = 6,
        search: Optional[str] = None,
    ) -> Tuple[List[GlobalMasterTemplate], int]:
        """Get templates by tags with pagination"""
        from sqlalchemy import func, or_

        # Base query
        stmt = select(GlobalMasterTemplate)
        count_stmt = select(func.count(GlobalMasterTemplate.id))

        if active_only:
            stmt = stmt.where(GlobalMasterTemplate.is_active == True)
            count_stmt = count_stmt.where(GlobalMasterTemplate.is_active == True)

        # Filter by tags (any tag matches)
        for tag in tags:
            tag_filter = GlobalMasterTemplate.tags.contains([tag])
            stmt = stmt.where(tag_filter)
            count_stmt = count_stmt.where(tag_filter)

        # Add search filter
        if search and search.strip():
            search_filter = or_(
                GlobalMasterTemplate.template_name.ilike(f"%{search}%"),
                GlobalMasterTemplate.description.ilike(f"%{search}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Order and paginate
        stmt = stmt.order_by(GlobalMasterTemplate.usage_count.desc()).offset(offset).limit(limit)

        # Execute queries
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)

        templates = result.scalars().all()
        total_count = count_result.scalar()

        return templates, total_count

    async def update_template(self, template_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a global master template"""
        update_data["updated_at"] = time.time()
        stmt = (
            update(GlobalMasterTemplate)
            .where(GlobalMasterTemplate.id == template_id)
            .values(**update_data)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def delete_template(self, template_id: int) -> bool:
        """Delete a global master template"""
        try:
            stmt = delete(GlobalMasterTemplate).where(GlobalMasterTemplate.id == template_id)
            result = await self.session.execute(stmt)
            await self.session.commit()

            rows_affected = result.rowcount
            logger.info(
                f"Delete operation for template {template_id}: {rows_affected} rows affected"
            )

            return rows_affected > 0
        except Exception as e:
            logger.error(f"Error deleting template {template_id}: {e}")
            await self.session.rollback()
            raise

    async def increment_usage_count(self, template_id: int) -> bool:
        """Increment template usage count"""
        stmt = (
            update(GlobalMasterTemplate)
            .where(GlobalMasterTemplate.id == template_id)
            .values(usage_count=GlobalMasterTemplate.usage_count + 1, updated_at=time.time())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def set_default_template(self, template_id: int) -> bool:
        """Set a template as default (and unset others)"""
        # First, unset all default templates
        stmt = update(GlobalMasterTemplate).values(is_default=False, updated_at=time.time())
        await self.session.execute(stmt)

        # Then set the specified template as default
        stmt = (
            update(GlobalMasterTemplate)
            .where(GlobalMasterTemplate.id == template_id)
            .values(is_default=True, updated_at=time.time())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_default_template(self) -> Optional[GlobalMasterTemplate]:
        """Get the default template"""
        stmt = select(GlobalMasterTemplate).where(
            GlobalMasterTemplate.is_default == True,
            GlobalMasterTemplate.is_active == True,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_templates_by_project_id(self, project_id: str) -> bool:
        """Delete all templates for a project"""
        stmt = delete(PPTTemplate).where(PPTTemplate.project_id == project_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
