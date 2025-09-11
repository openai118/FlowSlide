"""
FlowSlide specific API endpoints
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from ..core.config import ai_config
from ..services.deep_research_service import DEEPResearchService
from ..services.file_processor import FileProcessor
from ..services.research_report_generator import ResearchReportGenerator
from ..services.service_instances import get_ppt_service
from .models import (
    FileOutlineGenerationRequest,
    FileOutlineGenerationResponse,
    FileUploadResponse,
    PPTGenerationRequest,
    PPTOutline,
    PPTProject,
    PPTScenario,
    ProjectListResponse,
    
    TemplateSelectionRequest,
    TemplateSelectionResponse,
    TodoBoard,
)
router = APIRouter()
logger = logging.getLogger(__name__)
file_processor = FileProcessor()
# Use getter to avoid circular import resolution issues
def _ppt_service():
    return get_ppt_service()
# Research services (lazy initialization)
_research_service = None
_report_generator = None
_enhanced_research_service = None
_enhanced_report_generator = None


def get_research_service():
    """Get research service instance (lazy initialization)"""
    global _research_service
    if _research_service is None:
        try:
            _research_service = DEEPResearchService()
            logger.info("Research service initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize research service: {e}")
    return _research_service


def reload_research_service():
    """Reload research service to pick up new configuration"""
    global _research_service
    logger.info("Reloading research service...")

    if _research_service is not None:
        try:
            _research_service.reload_config()
            logger.info("Research service configuration reloaded successfully")

            # Verify the service is still available after reload
            if not _research_service.is_available():
                logger.warning(
                    "Research service is not available after reload, will recreate on next access"
                )
                _research_service = None

        except Exception as e:
            logger.warning(f"Failed to reload research service config: {e}")
            # If reload fails, recreate the service
            _research_service = None
    else:
        # If service doesn't exist, force recreation on next access
        logger.info("Research service will be recreated on next access with new configuration")


def get_report_generator():
    """Get report generator instance (lazy initialization)"""
    global _report_generator
    if _report_generator is None:
        try:
            _report_generator = ResearchReportGenerator()
            logger.info("Report generator initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize report generator: {e}")
    return _report_generator


def get_enhanced_research_service():
    """Get enhanced research service instance (lazy initialization)"""
    global _enhanced_research_service
    if _enhanced_research_service is None:
        try:
            from ..services.research.enhanced_research_service import EnhancedResearchService

            _enhanced_research_service = EnhancedResearchService()
            logger.info("Enhanced research service initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize enhanced research service: {e}")
    return _enhanced_research_service


def get_enhanced_report_generator():
    """Get enhanced report generator instance (lazy initialization)"""
    global _enhanced_report_generator
    if _enhanced_report_generator is None:
        try:
            from ..services.research.enhanced_report_generator import EnhancedReportGenerator

            _enhanced_report_generator = EnhancedReportGenerator()
            logger.info("Enhanced report generator initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize enhanced report generator: {e}")
    return _enhanced_report_generator


# Local helper: safe join of base_url and parts (mirrors web.routes.build_api_url)
def build_api_url(base_url: str, *parts: str, ensure_v1: bool = False) -> str:
    if not base_url:
        return "/" + "/".join(p.strip("/") for p in parts)
    base = base_url.rstrip("/")
    if ensure_v1 and not base.endswith("/v1"):
        base = base + "/v1"
    suffix = "/".join(p.strip("/") for p in parts if p)
    return f"{base}/{suffix}" if suffix else base


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FlowSlide API",
        "version": "0.1.0",
        "ai_provider": ai_config.default_ai_provider,
        "available_providers": ai_config.get_available_providers(),
    }


@router.get("/ai/providers")
async def get_ai_providers():
    """Get available AI providers"""
    # Get all providers (built-in only)
    all_providers = ai_config.get_available_providers()

    return {
        "default_provider": ai_config.default_ai_provider,
        "available_providers": all_providers,
        "provider_status": {
            provider: ai_config.is_provider_available(provider) for provider in all_providers
        },
    }


@router.post("/ai/providers/{provider_name}/test")
async def test_ai_provider(provider_name: str, request: Request):
    """Test a specific AI provider - uses frontend provided config if available"""
    try:
        import aiohttp

        # Try to get configuration from request body (if provided by frontend)
        body = None
        try:
            body = await request.json()
        except Exception:
            body = None  # No JSON body, use backend config

    # Special handling for OpenAI provider with frontend config
        if provider_name == "openai" and body:
            base_url = body.get("base_url")
            api_key = body.get("api_key")
            model = body.get("model", "gpt-4o")

            if base_url and api_key:
                # Use frontend provided config for OpenAI
                logger.info(f"Testing OpenAI with frontend config: {base_url}")

                # Build chat URL safely (ensure /v1)
                chat_url = build_api_url(base_url, "chat/completions", ensure_v1=True)

                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }

                    payload = {
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": "Say 'Hello, I am working!' in exactly 5 words.",
                            }
                        ],
                        "max_tokens": 20,
                        "temperature": 0,
                    }

                    async with session.post(
                        chat_url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                "provider": provider_name,
                                "status": "success",
                                "model": model,
                                "response_preview": data["choices"][0]["message"]["content"],
                                "usage": data.get("usage", {}),
                            }
                        else:
                            error_text = await response.text()
                            raise HTTPException(
                                status_code=response.status,
                                detail=f"API error: {error_text}",
                            )

        # Special handling for Ollama: perform direct HTTP checks and return 200 JSON on errors
        if provider_name == "ollama":
            data = body if isinstance(body, dict) else {}
            base_url = (data.get("base_url") or "http://localhost:11434").rstrip("/")
            model = (data.get("model") or "llama2").strip()
            api_key = (data.get("api_key") or "").strip() or None

            # Build URLs
            def _join(base: str, *parts: str) -> str:
                base = base.rstrip("/")
                suffix = "/".join(p.strip("/") for p in parts if p)
                return f"{base}/{suffix}" if suffix else base

            tags_url = _join(base_url, "api", "tags")
            gen_url = _join(base_url, "api", "generate")

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
                headers["X-Api-Key"] = api_key

            # 1) Ping service
            try:
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(tags_url, headers=headers or None, timeout=10) as ping:
                            ping_text = await ping.text()
                            if ping.status != 200:
                                return JSONResponse({
                                    "success": False,
                                    "status": "error",
                                    "provider": "ollama",
                                    "error": f"无法连接到 Ollama ({ping.status})",
                                    "detail": ping_text[:500],
                                }, status_code=200)

                            # Optional: validate model presence if parsable
                            try:
                                import json as _json
                                tags_json = _json.loads(ping_text)
                                if isinstance(tags_json, dict) and model:
                                    names = [m.get("name") or m.get("model") for m in tags_json.get("models", [])]
                                    if names and model not in names:
                                        return JSONResponse({
                                            "success": False,
                                            "status": "error",
                                            "provider": "ollama",
                                            "error": f"模型未找到: {model}",
                                            "detail": f"已安装模型: {', '.join([n for n in names if n])}",
                                        }, status_code=200)
                            except Exception:
                                pass
                    except Exception:
                        return JSONResponse({
                            "success": False,
                            "status": "error",
                            "provider": "ollama",
                            "error": "Ollama 服务未运行或无法连接",
                            "detail": f"请确保服务可通过 {base_url} 访问，并已拉取模型 {model}",
                        }, status_code=200)

                    # 2) Try a tiny generate
                    payload = {
                        "model": model,
                        "prompt": 'Say "Hello, I am working!" in exactly 5 words.',
                        "stream": False,
                        "options": {"num_predict": 20, "temperature": 0},
                    }

                    try:
                        async with session.post(gen_url, json=payload, headers=headers or None, timeout=30) as resp:
                            text = await resp.text()
                            if resp.status == 200:
                                try:
                                    import json as _json
                                    resp_json = _json.loads(text)
                                except Exception:
                                    resp_json = None
                                response_preview = None
                                if isinstance(resp_json, dict):
                                    response_preview = resp_json.get("response") or resp_json.get("output")
                                if not response_preview:
                                    response_preview = text[:500]
                                return JSONResponse({
                                    "success": True,
                                    "status": "success",
                                    "provider": "ollama",
                                    "model": model,
                                    "response_preview": response_preview,
                                }, status_code=200)
                            else:
                                return JSONResponse({
                                    "success": False,
                                    "status": "error",
                                    "provider": "ollama",
                                    "error": f"HTTP {resp.status}",
                                    "detail": text[:500],
                                }, status_code=200)
                    except Exception as gen_err:
                        return JSONResponse({
                            "success": False,
                            "status": "error",
                            "provider": "ollama",
                            "error": "生成请求异常",
                            "detail": str(gen_err)[:500],
                        }, status_code=200)

            except Exception as outer_err:
                # Any unexpected error: still return 200 JSON
                return JSONResponse({
                    "success": False,
                    "status": "error",
                    "provider": "ollama",
                    "error": "测试时发生异常",
                    "detail": str(outer_err)[:500],
                }, status_code=200)

        # Fallback to backend config for other providers or when no frontend config
        from ..ai import AIMessage, AIProviderFactory, MessageRole

        if not ai_config.is_provider_available(provider_name):
            raise HTTPException(
                status_code=400, detail=f"Provider {provider_name} is not available"
            )

        # Create provider instance with backend config
        provider = AIProviderFactory.create_provider(provider_name)

        # Test with a simple message
        test_message = AIMessage(
            role=MessageRole.USER,
            content="Hello, please respond with a brief greeting.",
        )

        response = await provider.chat_completion([test_message])

        return {
            "provider": provider_name,
            "status": "success",
            "model": response.model,
            "response_preview": (
                response.content[:100] + "..." if len(response.content) > 100 else response.content
            ),
            "usage": response.usage,
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log full exception and return structured JSON so frontend won't receive HTTP 500
        logger.exception(f"Provider test failed: {str(e)}")
        return JSONResponse(
            {
                "provider": provider_name,
                "status": "error",
                "success": False,
                "error": "Provider test failed",
                "detail": str(e)[:1000],
            },
            status_code=200,
        )


@router.get("/scenarios", response_model=List[PPTScenario])
async def get_scenarios():
    """Get available PPT scenarios - Updated to match requires.md specifications"""
    return [
        PPTScenario(
            id="general",
            name="通用",
            description="适用于各种通用场景的PPT模板，提供专业的商务风格",
            icon="📋",
            template_config={
                "style": "professional",
                "color_scheme": "blue",
                "font_family": "Arial, sans-serif",
            },
        ),
        PPTScenario(
            id="tourism",
            name="旅游观光",
            description="旅游线路策划、景点介绍、行程规划等旅游相关内容",
            icon="🌍",
            template_config={
                "style": "vibrant",
                "color_scheme": "green",
                "font_family": "Georgia, serif",
            },
        ),
        PPTScenario(
            id="education",
            name="儿童科普",
            description="教育培训、科普知识、儿童友好的设计风格",
            icon="🎓",
            template_config={
                "style": "playful",
                "color_scheme": "rainbow",
                "font_family": "Comic Sans MS, cursive",
            },
        ),
        PPTScenario(
            id="analysis",
            name="深入分析",
            description="数据分析、研究报告、学术论文等专业分析内容",
            icon="📊",
            template_config={
                "style": "analytical",
                "color_scheme": "dark",
                "font_family": "Helvetica, sans-serif",
            },
        ),
        PPTScenario(
            id="history",
            name="历史文化",
            description="历史事件、文化传承、人文艺术等主题",
            icon="🏛️",
            template_config={
                "style": "classical",
                "color_scheme": "brown",
                "font_family": "Times New Roman, serif",
            },
        ),
        PPTScenario(
            id="technology",
            name="科技技术",
            description="技术介绍、产品发布、创新展示等科技内容",
            icon="💻",
            template_config={
                "style": "modern",
                "color_scheme": "purple",
                "font_family": "Roboto, sans-serif",
            },
        ),
        PPTScenario(
            id="business",
            name="方案汇报",
            description="商业计划、项目汇报、企业展示等商务场景",
            icon="💼",
            template_config={
                "style": "corporate",
                "color_scheme": "navy",
                "font_family": "Arial, sans-serif",
            },
        ),
    ]


# Legacy PPT generation endpoint removed - now using project-based workflow
# Use POST /projects to create a new project instead


# Legacy single-file upload endpoint removed (use /upload with response_model below)


# Legacy task management endpoints removed - now using project-based workflow
# Use /projects endpoints for project management instead


@router.post("/outline/generate")
async def generate_outline(request: PPTGenerationRequest):
    """Generate PPT outline only"""
    try:
        outline = await _ppt_service().generate_outline(request)
        return {"outline": outline, "status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating outline: {str(e)}")


# New Project Management Endpoints


@router.post("/projects", response_model=PPTProject)
async def create_project(request: PPTGenerationRequest):
    """Create a new PPT project with TODO workflow"""
    try:
        project = await _ppt_service().create_project_with_workflow(request)
        return project

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(page: int = 1, page_size: int = 10, status: Optional[str] = None):
    """List projects with pagination"""
    try:
        return await _ppt_service().project_manager.list_projects(page, page_size, status)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing projects: {str(e)}")


@router.get("/projects/{project_id}", response_model=PPTProject)
async def get_project(project_id: str):
    """Get project details"""
    try:
        project = await _ppt_service().project_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting project: {str(e)}")


@router.get("/projects/{project_id}/todo", response_model=TodoBoard)
async def get_project_todo_board(project_id: str):
    """Get TODO board for a project"""
    try:
        todo_board = await _ppt_service().get_project_todo_board(project_id)
        if not todo_board:
            raise HTTPException(status_code=404, detail="TODO board not found")
        return todo_board

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting TODO board: {str(e)}")


@router.put("/projects/{project_id}/stages/{stage_id}")
async def update_project_stage(project_id: str, stage_id: str, request: Request):
    """Update project stage status"""
    try:
        # Parse JSON body
        body = await request.json()
        status = body.get("status")
        progress = body.get("progress")

        if not status:
            raise HTTPException(status_code=422, detail="Status is required")

        success = await _ppt_service().update_project_stage(project_id, stage_id, status, progress)
        if not success:
            raise HTTPException(status_code=404, detail="Project or stage not found")
        return {"status": "success", "message": "Stage updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating stage: {str(e)}")


@router.post("/projects/{project_id}/continue-from-stage")
async def continue_from_stage(project_id: str, request: Request):
    """Continue project workflow from a specific stage"""
    try:
        # Parse JSON body
        body = await request.json()
        stage_id = body.get("stage_id")

        if not stage_id:
            raise HTTPException(status_code=422, detail="Stage ID is required")

        # Get project
        project = await _ppt_service().project_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Reset stages from the specified stage onwards
        success = await _ppt_service().reset_stages_from(project_id, stage_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to reset stages")

        # Start workflow from the specified stage
        await _ppt_service().start_workflow_from_stage(project_id, stage_id)

        return {
            "status": "success",
            "message": f"Workflow restarted from stage: {stage_id}",
            "project_id": project_id,
            "stage_id": stage_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error continuing from stage: {str(e)}")


@router.post("/projects/{project_id}/slides/{slide_index}/lock")
async def lock_slide(project_id: str, slide_index: int):
    """Lock a slide to prevent regeneration"""
    try:
        success = await _ppt_service().lock_slide(project_id, slide_index)
        if not success:
            raise HTTPException(status_code=404, detail="Slide not found")
        return {"status": "success", "message": "Slide locked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error locking slide: {str(e)}")


@router.post("/projects/{project_id}/slides/{slide_index}/unlock")
async def unlock_slide(project_id: str, slide_index: int):
    """Unlock a slide to allow regeneration"""
    try:
        success = await _ppt_service().unlock_slide(project_id, slide_index)
        if not success:
            raise HTTPException(status_code=404, detail="Slide not found")
        return {"status": "success", "message": "Slide unlocked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unlocking slide: {str(e)}")


@router.get("/projects/{project_id}/versions")
async def get_project_versions(project_id: str):
    """Get all versions of a project"""
    try:
        versions = await _ppt_service().project_manager.get_project_versions(project_id)
        return {"versions": versions, "status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting project versions: {str(e)}")


@router.post("/projects/{project_id}/versions")
async def create_project_version(project_id: str, request: Request):
    """Create a new project version (backup snapshot)"""
    try:
        body = await request.json()
        version_data = body.get("version_data") or body
        # Use project manager to save version
        result = await _ppt_service().project_manager.save_project_version(project_id, version_data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create project version")
        return {"status": "success", "message": "Version created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating project version: {str(e)}")


@router.post("/projects/{project_id}/versions/{version}/restore")
async def restore_project_version(project_id: str, version: int):
    """Restore project to a specific version"""
    try:
        mgr = _ppt_service().project_manager
        restore_fn = getattr(mgr, "restore_project_version", None)
        if not callable(restore_fn):
            raise HTTPException(status_code=500, detail="Project manager does not support restore_project_version")
        import asyncio

        result = restore_fn(project_id, version)
        # support sync or async implementations
        if asyncio.iscoroutine(result):
            success = await result
        else:
            success = result
        if not success:
            raise HTTPException(status_code=404, detail="Project or version not found")
        return {"status": "success", "message": "Project restored successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring project version: {str(e)}")


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project"""
    try:
        success = await _ppt_service().project_manager.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "success", "message": "Project deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting project: {str(e)}")


@router.post("/projects/{project_id}/archive")
async def archive_project(project_id: str):
    """Archive a project"""
    try:
        success = await _ppt_service().project_manager.archive_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "success", "message": "Project archived successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error archiving project: {str(e)}")


@router.post("/projects/{project_id}/tasks/generate")
async def enqueue_generation_task(project_id: str, request: Request):
    """Enqueue a generation task for a project (returns task_id)"""
    try:
        body = await request.json()
        task_type = body.get("task_type") or body.get("type") or "ppt_generation"
        payload = body.get("payload") or {}

        # Use DatabaseProjectManager to obtain a DatabaseService with session
        from ..services.db_project_manager import DatabaseProjectManager
        from ..database.repositories import GenerationTaskRepository

        dbm = DatabaseProjectManager()
        db_service = await dbm._get_db_service()
        try:
            session = db_service.session
            task_repo = GenerationTaskRepository(session)
            task_id = await task_repo.enqueue(project_id, task_type, payload)
            return {"status": "success", "task_id": task_id}
        finally:
            try:
                await db_service.session.close()
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enqueue generation task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue generation task: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Return status and progress for a generation task"""
    try:
        from ..services.db_project_manager import DatabaseProjectManager
        from ..database.repositories import GenerationTaskRepository

        dbm = DatabaseProjectManager()
        db_service = await dbm._get_db_service()
        try:
            repo = GenerationTaskRepository(db_service.session)
            task = await repo.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return {"status": "success", "task": task}
        finally:
            try:
                await db_service.session.close()
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# File Upload Endpoints


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload and process document file"""
    try:
        # Validate file
        if file.filename is None or file.size is None:
            raise HTTPException(status_code=400, detail="Uploaded file is missing filename or size")
        is_valid, message = file_processor.validate_file(file.filename, file.size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

        # Save uploaded file temporarily
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Process the file
            result = await file_processor.process_file(temp_file_path, file.filename)
            return result

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("/upload/formats")
async def get_supported_formats():
    """Get supported file formats"""
    try:
        formats = file_processor.get_supported_formats()
        return {
            "supported_formats": formats,
            "max_size_mb": 100,
            "description": "支持的文件格式和上传限制",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting formats: {str(e)}")


@router.post("/upload/create-project", response_model=PPTProject)
async def create_project_from_upload(
    file: UploadFile = File(...),
    topic: Optional[str] = Form(None),
    scenario: Optional[str] = Form(None),
    requirements: Optional[str] = Form(None),
    language: str = Form("zh"),
):
    """Upload file and create project directly"""
    try:
        # Validate and process file
        if file.filename is None or file.size is None:
            raise HTTPException(status_code=400, detail="Uploaded file is missing filename or size")
        is_valid, message = file_processor.validate_file(file.filename, file.size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

        # Save and process file
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Process file
            file_result = await file_processor.process_file(temp_file_path, file.filename)

            # Create PPT request from content
            # Ensure topic is a string for the underlying API
            ppt_data = await file_processor.create_ppt_from_content(
                file_result.processed_content, topic or ""
            )

            # Override with user inputs if provided
            if topic:
                ppt_data["topic"] = topic
            if scenario:
                ppt_data["scenario"] = scenario
            if requirements:
                ppt_data["requirements"] = requirements

            # Create project request
            project_request = PPTGenerationRequest(**ppt_data)

            # Create project with workflow
            project = await _ppt_service().create_project_with_workflow(project_request)

            return project

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating project from upload: {str(e)}")


@router.post("/upload/analyze")
async def analyze_uploaded_content(file: UploadFile = File(...)):
    """Analyze uploaded file and suggest PPT structure"""
    try:
        # Validate file
        if file.filename is None or file.size is None:
            raise HTTPException(status_code=400, detail="Uploaded file is missing filename or size")
        is_valid, message = file_processor.validate_file(file.filename, file.size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

        # Save and process file
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Process file
            file_result = await file_processor.process_file(temp_file_path, file.filename)

            # Create suggested PPT structure
            ppt_suggestion = await file_processor.create_ppt_from_content(
                file_result.processed_content
            )

            return {
                "file_info": file_result,
                "ppt_suggestion": ppt_suggestion,
                "status": "success",
            }

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing file: {str(e)}")


@router.post("/slides/generate")
async def generate_slides(outline: PPTOutline, scenario: str = "general"):
    """Generate slides from outline"""
    try:
        # Instead of executing generation synchronously, enqueue a persistent task
        from ..services.db_project_manager import DatabaseProjectManager
        from ..database.repositories import GenerationTaskRepository

        dbm = DatabaseProjectManager()
        db_service = await dbm._get_db_service()
        try:
            session = db_service.session
            task_repo = GenerationTaskRepository(session)
            try:
                payload = {"outline": outline.dict(), "scenario": scenario}
            except Exception:
                payload = {"outline": outline, "scenario": scenario}

            task_id = await task_repo.enqueue(None, "slides_from_outline", payload)
            return {"status": "enqueued", "task_id": task_id}
        finally:
            try:
                await db_service.session.close()
            except Exception:
                pass

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enqueuing slide generation: {str(e)}")


@router.post("/files/generate-outline", response_model=FileOutlineGenerationResponse)
async def generate_outline_from_file(request: FileOutlineGenerationRequest):
    """使用summeryanyfile从文件生成Slide大纲"""
    try:
        # 调用增强的PPT服务来生成大纲
        result = await _ppt_service().generate_outline_from_file(request)
        return result

    except Exception as e:
        logger.error(f"Error generating outline from file: {e}")
        return FileOutlineGenerationResponse(
            success=False, error=str(e), message=f"从文件生成大纲失败: {str(e)}"
        )


@router.post("/files/upload-and-generate-outline")
async def upload_file_and_generate_outline(
    file: UploadFile = File(...),
    topic: Optional[str] = Form(None),
    scenario: str = Form("general"),
    page_count_mode: str = Form("ai_decide"),
    min_pages: int = Form(8),
    max_pages: int = Form(15),
    fixed_pages: int = Form(10),
    ppt_style: str = Form("general"),
    custom_style_prompt: Optional[str] = Form(None),
    file_processing_mode: str = Form("markitdown"),
    content_analysis_depth: str = Form("standard"),
    focus_content: Optional[str] = Form(None),
    tech_highlights: Optional[str] = Form(None),
    target_audience: Optional[str] = Form(None),
):
    """上传文件并直接生成Slide大纲"""
    try:
        # Validate file
        if file.filename is None or file.size is None:
            raise HTTPException(status_code=400, detail="Uploaded file is missing filename or size")
        is_valid, message = file_processor.validate_file(file.filename, file.size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

        # 保存临时文件
        import os
        import tempfile

        suffix = os.path.splitext(file.filename or "")[1] or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # 解析多选字段
            focus_content_list = focus_content.split(",") if focus_content else []
            tech_highlights_list = tech_highlights.split(",") if tech_highlights else []

            # 创建请求对象
            outline_request = FileOutlineGenerationRequest(
                file_path=temp_file_path,
                filename=file.filename,
                topic=topic,
                scenario=scenario,
                language="zh",
                requirements="",  # API调用暂时没有requirements参数
                page_count_mode=page_count_mode,
                min_pages=min_pages,
                max_pages=max_pages,
                fixed_pages=fixed_pages,
                ppt_style=ppt_style,
                custom_style_prompt=custom_style_prompt,
                file_processing_mode=file_processing_mode,
                content_analysis_depth=content_analysis_depth,
                target_audience=target_audience,
            )

            # 生成大纲
            result = await _ppt_service().generate_outline_from_file(outline_request)
            return result

        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file and generating outline: {e}")
        return FileOutlineGenerationResponse(
            success=False, error=str(e), message=f"文件上传和大纲生成失败: {str(e)}"
        )


@router.post("/projects/{project_id}/select-template", response_model=TemplateSelectionResponse)
async def select_global_template_for_project(project_id: str, request: TemplateSelectionRequest):
    """为项目选择全局母版模板"""
    try:
        # 验证项目ID匹配
        if request.project_id != project_id:
            raise HTTPException(status_code=400, detail="Project ID mismatch")

        # 选择模板
        result = await _ppt_service().select_global_template_for_project(
            project_id, request.selected_template_id
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return TemplateSelectionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to select template: {str(e)}")


@router.get("/projects/{project_id}/selected-template")
async def get_selected_global_template(project_id: str):
    """获取项目选择的全局母版模板"""
    try:
        template = await _ppt_service().get_selected_global_template(project_id)

        if not template:
            return {"selected_template": None, "message": "No template selected"}

        return {"selected_template": template}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get selected template: {str(e)}")


# 文件缓存管理端点
@router.get("/cache/stats")
async def get_file_cache_stats():
    """获取文件缓存统计信息"""
    try:
        stats = _ppt_service().get_cache_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/cleanup")
async def cleanup_file_cache():
    """清理过期的文件缓存条目"""
    try:
        _ppt_service().cleanup_cache()
        return {"success": True, "message": "文件缓存清理完成"}
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# DEEP Research Endpoints


@router.get("/research/status")
async def get_research_status():
    """Get research service status"""
    try:
        research_service = get_research_service()
        if not research_service:
            return {
                "available": False,
                "message": "Research service not initialized",
                "tavily_configured": bool(ai_config.tavily_api_key),
            }

        status = research_service.get_status()
        return {
            "available": research_service.is_available(),
            "status": status,
            "tavily_configured": bool(ai_config.tavily_api_key),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting research status: {str(e)}")


@router.post("/research/conduct")
async def conduct_research(topic: str, language: str = "zh"):
    """Conduct DEEP research on a topic"""
    try:
        research_service = get_research_service()
        if not research_service or not research_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="Research service not available. Please check Tavily API configuration.",
            )

        # Conduct research
        research_report = await research_service.conduct_deep_research(topic, language)

        # Save report if generator is available
        report_path = None
        report_generator = get_report_generator()
        if report_generator:
            try:
                report_path = report_generator.save_report_to_file(research_report)
            except Exception as save_error:
                logger.warning(f"Failed to save research report: {save_error}")

        return {
            "success": True,
            "report": {
                "topic": research_report.topic,
                "language": research_report.language,
                "executive_summary": research_report.executive_summary,
                "key_findings": research_report.key_findings,
                "recommendations": research_report.recommendations,
                "total_duration": research_report.total_duration,
                "sources_count": len(research_report.sources),
                "steps_count": len(research_report.steps),
            },
            "report_path": report_path,
            "message": "Research completed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error conducting research: {e}")
        raise HTTPException(status_code=500, detail=f"Research failed: {str(e)}")


@router.get("/research/reports")
async def list_research_reports():
    """List all saved research reports"""
    try:
        report_generator = get_report_generator()
        if not report_generator:
            raise HTTPException(status_code=503, detail="Report generator not available")

        reports = report_generator.list_saved_reports()
        return {
            "success": True,
            "reports": reports,
            "total_count": len(reports),
            "reports_directory": report_generator.get_reports_directory(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing reports: {str(e)}")


@router.delete("/research/reports/{filename}")
async def delete_research_report(filename: str):
    """Delete a research report"""
    try:
        report_generator = get_report_generator()
        if not report_generator:
            raise HTTPException(status_code=503, detail="Report generator not available")

        success = report_generator.delete_report(filename)
        if not success:
            raise HTTPException(status_code=404, detail="Report not found")

        return {"success": True, "message": f"Report {filename} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting report: {str(e)}")


@router.get("/research/reports/directory")
async def get_reports_directory():
    """Get the reports directory path"""
    try:
        report_generator = get_report_generator()
        if not report_generator:
            raise HTTPException(status_code=503, detail="Report generator not available")

        directory = report_generator.get_reports_directory()
        return {
            "success": True,
            "directory": directory,
            "message": "Reports are saved in this directory",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting directory: {str(e)}")


# Enhanced Research API Endpoints


@router.post("/research/enhanced/conduct")
async def conduct_enhanced_research(topic: str, language: str = "zh"):
    """Conduct enhanced research using multiple providers and deep content analysis"""
    try:
        enhanced_service = get_enhanced_research_service()
        if not enhanced_service or not enhanced_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="Enhanced research service not available. Please check provider configurations.",
            )

        # Conduct enhanced research
        enhanced_report = await enhanced_service.conduct_enhanced_research(topic, language)

        # Save enhanced report
        report_path = None
        enhanced_generator = get_enhanced_report_generator()
        if enhanced_generator:
            try:
                report_path = enhanced_generator.save_report_to_file(enhanced_report)
            except Exception as save_error:
                logger.warning(f"Failed to save enhanced research report: {save_error}")

        return {
            "success": True,
            "message": "Enhanced research completed successfully",
            "report": {
                "topic": enhanced_report.topic,
                "language": enhanced_report.language,
                "executive_summary": enhanced_report.executive_summary,
                "key_findings": enhanced_report.key_findings,
                "recommendations": enhanced_report.recommendations,
                "sources": enhanced_report.sources,
                "created_at": enhanced_report.created_at.isoformat(),
                "total_duration": enhanced_report.total_duration,
                "steps_count": len(enhanced_report.steps),
                "provider_stats": enhanced_report.provider_stats,
                "content_analysis": enhanced_report.content_analysis,
            },
            "report_path": report_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced research failed: {e}")
        raise HTTPException(status_code=500, detail=f"Enhanced research failed: {str(e)}")


@router.get("/research/enhanced/status")
async def get_enhanced_research_status():
    """Get enhanced research service status and configuration"""
    try:
        enhanced_service = get_enhanced_research_service()
        if not enhanced_service:
            return {
                "available": False,
                "message": "Enhanced research service not initialized",
            }

        status = enhanced_service.get_status()
        return {"success": True, "status": status}

    except Exception as e:
        logger.error(f"Error getting enhanced research status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting enhanced research status: {str(e)}"
        )


@router.get("/research/enhanced/providers")
async def get_available_research_providers():
    """Get list of available research providers"""
    try:
        enhanced_service = get_enhanced_research_service()
        providers = {"tavily": False, "searxng": False, "content_extraction": False}

        if enhanced_service:
            available_providers = enhanced_service.get_available_providers()
            for provider in available_providers:
                if provider in providers:
                    providers[provider] = True

            # Check content extraction
            from ..core.config import ai_config

            providers["content_extraction"] = ai_config.research_enable_content_extraction

        return {
            "success": True,
            "providers": providers,
            "enhanced_service_available": enhanced_service is not None
            and enhanced_service.is_available(),
        }

    except Exception as e:
        logger.error(f"Error getting research providers: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting research providers: {str(e)}")
