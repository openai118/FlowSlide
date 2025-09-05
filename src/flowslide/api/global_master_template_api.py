"""
Global Master Template API endpoints
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
import asyncio

from ..services.global_master_template_service import GlobalMasterTemplateService
from ..services.global_master_template_service import GlobalMasterTemplateService
from ..ai import AIMessage, MessageRole
from ..database.create_default_template import ensure_default_templates_exist
from .models import (
    GlobalMasterTemplateCreate,
    GlobalMasterTemplateDetailResponse,
    GlobalMasterTemplateGenerateRequest,
    GlobalMasterTemplateResponse,
    GlobalMasterTemplateUpdate,
    AITemplateTransformRequest,
    AITemplateTransformResponse,
    TemplateSelectionRequest,
    TemplateSelectionResponse,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/global-master-templates", tags=["Global Master Templates"])

# Service instance
template_service = GlobalMasterTemplateService()


@router.post("/", response_model=GlobalMasterTemplateResponse)
async def create_template(template_data: GlobalMasterTemplateCreate):
    """Create a new global master template"""
    try:
        result = await template_service.create_template(template_data.model_dump())
        return GlobalMasterTemplateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.get("/", response_model=dict)
async def get_all_templates(
    active_only: bool = Query(True, description="Only return active templates"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(6, ge=1, le=1000, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search in template name and description"),
):
    """Get all global master templates with pagination"""
    try:
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",")]
            result = await template_service.get_templates_by_tags_paginated(
                tag_list, active_only, page, page_size, search
            )
        else:
            result = await template_service.get_all_templates_paginated(
                active_only, page, page_size, search
            )

        return {
            "templates": [
                GlobalMasterTemplateResponse(**template) for template in result["templates"]
            ],
            "pagination": result["pagination"],
        }
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to get templates")

@router.post("/seed", response_model=dict)
async def seed_templates(force: bool = Query(False, description="Force import from examples")):
    """Seed global master templates if missing (optionally force import)."""
    try:
        ids = await ensure_default_templates_exist(force_import=force)
        return {
            "success": True,
            "imported_count": len(ids),
            "template_ids": ids,
            "message": ("Imported from examples" if ids else "No import needed or failed"),
        }
    except Exception as e:
        logger.error(f"Failed to seed templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to seed templates")


@router.get("/{template_id}", response_model=GlobalMasterTemplateDetailResponse)
async def get_template_by_id(template_id: int):
    """Get a global master template by ID"""
    try:
        template = await template_service.get_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return GlobalMasterTemplateDetailResponse(**template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template")


@router.put("/{template_id}", response_model=dict)
async def update_template(template_id: int, update_data: GlobalMasterTemplateUpdate):
    """Update a global master template"""
    try:
        # Filter out None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided")

        success = await template_service.update_template(template_id, update_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"success": True, "message": "Template updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update template")


@router.delete("/{template_id}", response_model=dict)
async def delete_template(template_id: int):
    """Delete a global master template"""
    try:
        success = await template_service.delete_template(template_id)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"success": True, "message": "Template deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete template")


@router.post("/{template_id}/set-default", response_model=dict)
async def set_default_template(template_id: int):
    """Set a template as the default template"""
    try:
        success = await template_service.set_default_template(template_id)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"success": True, "message": "Default template set successfully"}
    except Exception as e:
        logger.error(f"Failed to set default template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to set default template")


@router.get("/default/template", response_model=GlobalMasterTemplateDetailResponse)
async def get_default_template():
    """Get the default global master template"""
    try:
        template = await template_service.get_default_template()
        if not template:
            raise HTTPException(status_code=404, detail="No default template found")

        return GlobalMasterTemplateDetailResponse(**template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get default template: {e}")
        raise HTTPException(status_code=500, detail="Failed to get default template")


@router.post("/generate", response_model=GlobalMasterTemplateResponse)
async def generate_template_with_ai(request: GlobalMasterTemplateGenerateRequest):
    """Generate a new template using AI"""
    try:
        result = await template_service.generate_template_with_ai(
            prompt=request.prompt,
            template_name=request.template_name,
            description=request.description,
            tags=request.tags,
        )
        return GlobalMasterTemplateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate template with AI: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate template")


@router.post("/generate-stream")
async def generate_template_with_ai_stream(
    request: GlobalMasterTemplateGenerateRequest,
):
    """Generate a new template using AI with streaming response"""
    import json

    from fastapi.responses import StreamingResponse

    async def generate_stream():
        try:
            # 发送初始状态
            yield f"data: {json.dumps({'type': 'status', 'message': '正在连接AI服务...'})}\n\n"

            # 使用流式生成服务
            async for chunk in template_service.generate_template_with_ai_stream(
                prompt=request.prompt,
                template_name=request.template_name,
                description=request.description,
                tags=request.tags,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"

        except Exception as e:
            logger.error(f"Failed to generate template with AI stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.post("/select", response_model=TemplateSelectionResponse)
async def select_template_for_project(request: TemplateSelectionRequest):
    """Select a template for PPT generation"""
    try:
        if request.selected_template_id:
            # Get the selected template
            template = await template_service.get_template_by_id(request.selected_template_id)
            if not template:
                raise HTTPException(status_code=404, detail="Selected template not found")

            # Increment usage count
            await template_service.increment_template_usage(request.selected_template_id)

            return TemplateSelectionResponse(
                success=True,
                message="Template selected successfully",
                selected_template=GlobalMasterTemplateResponse(**template),
            )
        else:
            # Use default template
            template = await template_service.get_default_template()
            if not template:
                raise HTTPException(status_code=404, detail="No default template found")

            # Increment usage count
            await template_service.increment_template_usage(template["id"])

            return TemplateSelectionResponse(
                success=True,
                message="Default template selected",
                selected_template=GlobalMasterTemplateResponse(**template),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to select template: {e}")
        raise HTTPException(status_code=500, detail="Failed to select template")


@router.post("/{template_id}/duplicate", response_model=GlobalMasterTemplateResponse)
async def duplicate_template(
    template_id: int, new_name: str = Query(..., description="New template name")
):
    """Duplicate an existing template"""
    try:
        # Get the original template
        original = await template_service.get_template_by_id(template_id)
        if not original:
            raise HTTPException(status_code=404, detail="Template not found")

        # Create duplicate data
        duplicate_data = {
            "template_name": new_name,
            "description": f"复制自: {original['template_name']}",
            "html_template": original["html_template"],
            "tags": original["tags"] + ["复制"],
            "created_by": "duplicate",
        }

        result = await template_service.create_template(duplicate_data)
        return GlobalMasterTemplateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to duplicate template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to duplicate template")


@router.get("/{template_id}/preview", response_model=dict)
async def get_template_preview(template_id: int):
    """Get template preview data"""
    try:
        template = await template_service.get_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return {
            "id": template["id"],
            "template_name": template["template_name"],
            "preview_image": template["preview_image"],
            "html_template": template["html_template"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template preview {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template preview")

@router.post("/{template_id}/ai-transform", response_model=AITemplateTransformResponse)
async def ai_transform_slide_with_template(
    template_id: int,
    req: AITemplateTransformRequest,
    timeout_sec: float = Query(45.0, ge=1, le=300, description="AI调用超时时间（秒），默认45s")
):
    """使用AI将传入的单页幻灯片HTML转换为指定全局母版的风格，返回完整HTML。

    约束/目标：
    - 保持1280x720（或模板自带尺寸）画布，保留关键节点（img/canvas/svg/script）
    - 将原内容映射到模板的内容区域/插槽（如 {{ page_content }} 或 data-page-* 容器）
    - 允许 safe_mode 更偏保守地迁移结构
    """
    try:
        # 读取目标模板
        template = await template_service.get_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        html_template = template.get("html_template") or ""
        if not html_template:
            raise HTTPException(status_code=400, detail="Template has no html_template")

        # 构造给AI的提示词
        ai = template_service.ai_provider
        from ..core.config import ai_config as _ai_cfg

        page_title = req.slide_title or ""
        page_number = req.page_number or 1
        total_pages = req.total_pages or 1
        project_info = req.project_context or {}

        system_msg = (
            "你是一名资深的PPT前端工程与视觉设计专家，擅长将现有HTML幻灯片内容迁移到新的母版模板结构中。"
        )

        user_msg = f"""
请将“原始幻灯片HTML”迁移到“目标母版HTML”的结构与样式下，输出严格的完整HTML（包含 <!DOCTYPE html>、<head>、<body>）。

要求：
- 尽量保留原有的重要节点：<img>、<canvas>、<svg>、<script>、图表容器等，保留其事件/属性；
- 将原内容映射到模板的内容区域或插槽（如 data-page-content、{{{{ page_content }}}} 或明显的内容容器）；
- 如模板具有页眉/页脚/页码区域，避免重复放置同类元素；
- 维持页面尺寸比例（优先1280x720或模板自带的固定尺寸）；
- 如果存在内联脚本，请保留，并确保依赖的DOM仍然存在；
- 避免引入外部网络依赖；
- 输出只包含转换后的最终HTML，不要额外解释文字。

上下文：
- 页面标题：{page_title}
- 页码：{page_number}/{total_pages}
- 项目信息：{project_info}
- 安全模式：{req.safe_mode}

目标母版HTML：
```html
{html_template}
```

原始幻灯片HTML：
```html
{req.slide_html}
```
"""

        messages = [
            AIMessage(role=MessageRole.SYSTEM, content=system_msg),
            AIMessage(
                role=MessageRole.USER,
                content=(user_msg + ("\n补充指令：" + req.extra_instructions if req.extra_instructions else "")),
            ),
        ]

        # 调用对话式补全，提取HTML（加超时保护）
        try:
            resp = await asyncio.wait_for(
                ai.chat_completion(
                    messages=messages,
                    max_tokens=_ai_cfg.max_tokens,
                    temperature=0.4,
                ),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            return AITemplateTransformResponse(success=False, error="AI转换超时，请稍后重试或调低批量并发。")
        content = getattr(resp, "content", "") if resp else ""

        # 提取代码块中的HTML
        transformed = template_service._extract_html_from_response(content) if hasattr(template_service, "_extract_html_from_response") else content

        # 基本校验
        if not transformed or (hasattr(template_service, "_validate_html_template") and not template_service._validate_html_template(transformed)):
            # 兜底：若不符合完整结构，直接返回原文，前端可回退
            return AITemplateTransformResponse(success=False, error="AI返回的HTML不完整或校验失败", transformed_html=content)

        return AITemplateTransformResponse(success=True, transformed_html=transformed, notes="AI转换完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI模板转换失败: {e}")
        return AITemplateTransformResponse(success=False, error=str(e))


# Add increment usage endpoint for internal use
@router.post("/{template_id}/increment-usage", response_model=dict)
async def increment_template_usage(template_id: int):
    """Increment template usage count (internal use)"""
    try:
        success = await template_service.increment_template_usage(template_id)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"success": True, "message": "Usage count incremented"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to increment usage for template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to increment usage count")
