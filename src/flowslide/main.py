"""
Main FastAPI application entry point
"""

import asyncio
import logging
import os
from typing import Any, Callable, Protocol

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__ as FS_VERSION
from .api.backup_api import router as backup_router
from .api.config_api import router as config_router
from .api.database_api import router as database_router
from .api.deployment_api import router as deployment_router
from .api.flowslide_api import router as flowslide_router
from .api.global_master_template_api import router as template_api_router
from .api.image_api import router as image_router
from .api.openai_compat import router as openai_router
from .api.system_api import router as system_router
from .auth import auth_router, create_auth_middleware
from .database.create_default_template import (
    ensure_default_templates_exist_first_time,
    ensure_default_templates_exist,
)
from .database.database import init_db
from .web import router as web_router

# Configure logging early so it's available during conditional imports
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 检查是否是从重启中启动
restart_marker = os.path.join(os.getcwd(), "temp", ".restart_marker")
if os.path.exists(restart_marker):
    try:
        with open(restart_marker, "r") as f:
            restart_time = f.read().strip()
        os.remove(restart_marker)
        logger.info(f"🔄 检测到应用重启 (重启时间: {restart_time})")
        logger.info("🚀 开始完全重新初始化应用...")
    except Exception as e:
        logger.warning(f"读取重启标记失败: {e}")
else:
    logger.info("🚀 启动 FlowSlide 应用程序...")


# Protocol for metrics collector to satisfy type checkers
class MetricsProtocol(Protocol):
    def track_http_request(self, *args, **kwargs) -> None: ...


# Placeholder type annotations for metrics objects
metrics_collector: MetricsProtocol
metrics_endpoint: Callable[[], Any]

# 条件导入监控模块
try:
    from .monitoring import metrics_collector as _metrics_collector
    from .monitoring import metrics_endpoint as _metrics_endpoint

    metrics_collector = _metrics_collector  # type: ignore[assignment]
    metrics_endpoint = _metrics_endpoint  # type: ignore[assignment]
    MONITORING_ENABLED = True
except ImportError as e:
    logger.warning(f"Monitoring disabled due to missing dependencies: {e}")
    MONITORING_ENABLED = False

    # 创建mock对象
    class MockMetricsCollector:
        def track_http_request(self, *args, **kwargs) -> None:
            pass

    def metrics_endpoint() -> dict:
        return {"message": "Monitoring disabled - missing prometheus_client"}

    metrics_collector = MockMetricsCollector()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable SQLAlchemy verbose logging completely
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)

# Create FastAPI app
app = FastAPI(
    title="FlowSlide API",
    description="AI-powered PPT generation platform with OpenAI-compatible API",
    version=FS_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


# 安全响应头中间件（添加 X-Content-Type-Options 等）
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    # 最重要：防止 MIME 嗅探
    if "X-Content-Type-Options" not in response.headers:
        response.headers["X-Content-Type-Options"] = "nosniff"
    # 点击劫持防护（不影响当前站内 iframe 使用）
    if "X-Frame-Options" not in response.headers:
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # 引用策略，尽量少暴露来源
    if "Referrer-Policy" not in response.headers:
        response.headers["Referrer-Policy"] = "no-referrer"
    # COOP/COEP，提升隔离（放宽COEP以允许外部资源如CDN）
    if "Cross-Origin-Opener-Policy" not in response.headers:
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if "Cross-Origin-Embedder-Policy" not in response.headers:
        # 使用 unsafe-none 允许加载外部资源（如Tailwind CSS CDN）
        response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    # 权限策略，按需最小化
    if "Permissions-Policy" not in response.headers:
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        logger.info("🚀 Starting application initialization...")

        from .database.database import initialize_database, update_session_makers

        logger.info("📊 Initializing database manager...")
        # 初始化数据库管理器
        db_mgr = initialize_database()
        logger.info(f"Database manager initialized: {db_mgr.database_type}")

        logger.info("🔄 Updating session makers...")
        # 更新session makers
        update_session_makers()

        # 确保数据目录存在
        if db_mgr.database_type == "sqlite":
            import urllib.parse
            from .core.simple_config import LOCAL_DATABASE_URL

            parsed = urllib.parse.urlparse(LOCAL_DATABASE_URL)
            if parsed.scheme == "sqlite":
                db_file_path = parsed.path.lstrip("/")
                os.makedirs(os.path.dirname(db_file_path), exist_ok=True)
                logger.info(f"✅ Data directory ready: {os.path.dirname(db_file_path)}")

        # 检查是否是首次运行
        db_file_path = "./data/flowslide.db" if db_mgr.database_type == "sqlite" else None
        db_exists = db_file_path and os.path.exists(db_file_path)

        logger.info(f"Initializing database... Type: {db_mgr.database_type}")
        await init_db()
        logger.info("Database initialized successfully")

        # Optionally start generation worker to process queued generation tasks
        try:
            from .services.worker_runner import main as _worker_main

            start_worker = os.getenv("START_GENERATION_WORKER", "true").lower() in (
                "true",
                "1",
                "yes",
                "on",
            )
            if start_worker:
                worker_task = asyncio.create_task(_worker_main())
                try:
                    app.state.generation_worker_task = worker_task
                except Exception:
                    setattr(app.state, "generation_worker_task", worker_task)
                logger.info("✅ Generation worker background task started")
        except Exception as e:
            logger.warning(f"Generation worker not started: {e}")

        # 如果配置了外部数据库，启动数据同步
        if db_mgr.sync_enabled:
            from .services.data_sync_service import start_data_sync
            # Start the background data sync task and keep a handle for graceful shutdown
            data_sync_task = asyncio.create_task(start_data_sync())
            # store on app.state so shutdown handler can find and stop it
            try:
                app.state.data_sync_task = data_sync_task
            except Exception:
                # fallback: attach attribute directly
                setattr(app.state, 'data_sync_task', data_sync_task)
            logger.info("✅ Data sync background task started")

        # 注册模式切换回调以实现热重载
        try:
            from .core.deployment_mode_manager import mode_manager
            from .services.service_instances import reload_services

            async def mode_change_reload_callback(new_mode, switch_context):
                """模式切换时的服务重载回调"""
                try:
                    logger.info(f"🔄 Mode switched to {new_mode}, reloading services...")
                    reload_services()
                    logger.info("✅ Services reloaded after mode switch")
                except Exception as e:
                    logger.error(f"❌ Service reload after mode switch failed: {e}")

            mode_manager.add_mode_change_callback(mode_change_reload_callback)
            logger.info("✅ Mode change reload callback registered")
        except Exception as e:
            logger.warning(f"Failed to register mode change callback: {e}")

        # 如果配置了R2，启动定期备份
        if os.getenv("R2_ACCESS_KEY_ID"):
            from .services.backup_service import create_backup
            # start scheduled backup and keep handle for shutdown
            backup_task = asyncio.create_task(schedule_backup(create_backup))
            try:
                app.state.backup_task = backup_task
            except Exception:
                setattr(app.state, 'backup_task', backup_task)
            logger.info("✅ Scheduled backup task started")

        # Import templates on first-time SQLite setup, otherwise ensure templates exist (for external DB or existing DB)
        if not db_exists and db_mgr.database_type == "sqlite":
            logger.info("First time setup detected - importing templates from examples (force)...")
            template_ids = await ensure_default_templates_exist_first_time()
            logger.info(
                f"Template initialization completed. {len(template_ids)} templates available."
            )
        else:
            # Ensure at least one template exists; will no-op if already present
            logger.info("Ensuring global master templates exist (no-force import if empty)...")
            ensured_ids = await ensure_default_templates_exist()
            if ensured_ids:
                logger.info(
                    f"Ensured {len(ensured_ids)} global master templates are available."
                )
            else:
                logger.info("Global master templates already present; no import needed")

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


async def schedule_backup(backup_func):
    """定期备份调度"""
    import asyncio

    # 首次运行延迟10分钟
    await asyncio.sleep(600)

    while True:
        try:
            # 每24小时备份一次
            await asyncio.sleep(24 * 60 * 60)
            await backup_func("full")
        except Exception as e:
            logger.error(f"Scheduled backup error: {e}")
            await asyncio.sleep(60 * 60)  # 出错后等待1小时重试


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connections on shutdown"""
    try:
        logger.info("Shutting down application...")

        # Attempt graceful shutdown of data sync background task
        try:
            from .services.data_sync_service import stop_data_sync

            data_sync_task = getattr(app.state, 'data_sync_task', None)
            if data_sync_task is not None:
                logger.info("Stopping data sync service...")
                # signal the service to stop
                await stop_data_sync()
                # wait briefly for the task to finish
                try:
                    await asyncio.wait_for(data_sync_task, timeout=5.0)
                    logger.info("✅ Data sync task stopped")
                except asyncio.TimeoutError:
                    logger.warning("Data sync task did not stop within timeout; cancelling")
                    data_sync_task.cancel()
        except Exception as e:
            logger.debug(f"No data sync task to stop or stop failed: {e}")

        # Attempt graceful shutdown of backup task
        try:
            backup_task = getattr(app.state, 'backup_task', None)
            if backup_task is not None:
                logger.info("Stopping scheduled backup task...")
                try:
                    await asyncio.wait_for(backup_task, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.info("Cancelling scheduled backup task")
                    backup_task.cancel()
        except Exception as e:
            logger.debug(f"No backup task to stop or cancel failed: {e}")

        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Add CORS middleware
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restrict origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add authentication middleware
auth_middleware = create_auth_middleware()
app.middleware("http")(auth_middleware)

# Include routers
app.include_router(auth_router, prefix="", tags=["Authentication"])
app.include_router(backup_router, tags=["Backup Management"])
app.include_router(config_router, prefix="", tags=["Configuration Management"])
app.include_router(database_router, prefix="", tags=["Database Management"])
app.include_router(deployment_router, prefix="/api/deployment", tags=["Deployment Mode Management"])
app.include_router(image_router, prefix="", tags=["Image Service"])
app.include_router(system_router, tags=["System Monitoring"])

app.include_router(openai_router, prefix="/v1", tags=["OpenAI Compatible"])
app.include_router(flowslide_router, prefix="/api", tags=["FlowSlide API"])
app.include_router(template_api_router, tags=["Global Master Templates"])
app.include_router(database_router, tags=["Database Management"])
app.include_router(web_router, prefix="", tags=["Web Interface"])

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "web", "static")


# Custom route for JS files to ensure correct MIME type
@app.get("/static/js/{file_path:path}")
async def serve_js_file(file_path: str):
    """Serve JavaScript files with correct MIME type"""
    js_file_path = os.path.join(static_dir, "js", file_path)
    if os.path.exists(js_file_path):
        return FileResponse(js_file_path, media_type="application/javascript")
    else:
        raise HTTPException(status_code=404, detail="JS file not found")


app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Add favicon route


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = os.path.join(static_dir, "images", "favicon.svg")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    else:
        # Return a simple 1x1 transparent PNG if favicon doesn't exist
        raise HTTPException(status_code=404, detail="Favicon not found")


# Mount temp directory for image cache with caching headers
temp_dir = os.path.join(os.getcwd(), "temp")
if os.path.exists(temp_dir):
    app.mount("/temp", StaticFiles(directory=temp_dir), name="temp")
    logger.info(f"Mounted temp directory: {temp_dir}")
else:
    logger.warning(f"Temp directory not found: {temp_dir}")

# Add request monitoring middleware (if monitoring is enabled)
if MONITORING_ENABLED:

    @app.middleware("http")
    async def monitor_requests(request, call_next):
        import time

        start_time = time.time()

        response = await call_next(request)

        # Track request metrics
        duration = time.time() - start_time
        metrics_collector.track_http_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration=duration,
        )

        return response


# Add caching middleware for static files
@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)

    # Add cache headers for static files
    if request.url.path.startswith(("/static/", "/temp/")):
        # Cache static files for 1 hour
        response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers["ETag"] = f'"{hash(request.url.path)}"'

    return response


@app.get("/")
async def root_redirect():
    """Root endpoint - redirect to /home to avoid duplicate landing page"""
    return RedirectResponse(url="/home", status_code=302)


@app.get("/api/version")
async def api_version():
    """Return current server version for UI to consume"""
    return {"version": FS_VERSION}


@app.get("/version.txt", response_class=PlainTextResponse)
async def version_txt():
    """Plain text version (useful for CDN/clients)"""
    return FS_VERSION


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "FlowSlide API"}


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return metrics_endpoint()


if __name__ == "__main__":
    # Prefer passing the app object to avoid import path issues
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True, log_level="info")
