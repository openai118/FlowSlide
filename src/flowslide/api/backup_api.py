from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import tempfile

from ..auth.middleware import require_admin, require_auth
from ..services.backup_manager import BackupManager, ensure_schema, get_conn
# Backup service (zip-based) helpers for R2 and local zip backups
from ..services.backup_service import (
    backup_service,
    create_backup as svc_create_backup,
    list_backups as svc_list_local_backups,
    list_r2_files as svc_list_r2_files,
    delete_r2_file as svc_delete_r2_file,
    restore_r2_key as svc_restore_r2_key,
    restore_backup as svc_restore_local_backup,
    create_external_sql_backup as svc_create_external_sql,
)
try:
    import boto3  # for direct R2 download streaming when needed
    from botocore.config import Config as BotoConfig
except Exception:  # pragma: no cover - optional at runtime
    boto3 = None
    BotoConfig = None

router = APIRouter()
ensure_schema()


@router.get('/api/backup/ping')
def ping():
    """Health endpoint for the backup router."""
    return {"ok": True}


class BackupCreateRequest(BaseModel):
    type: str  # e.g. 'db', 'artifact', 'media', 'cache'
    name: Optional[str] = None
    project_id: Optional[str] = None


class BackupRecord(BaseModel):
    id: str
    name: str
    type: str
    size: Optional[int]
    checksum: Optional[str]
    created_at: Optional[float]
    storage_key: Optional[str]


@router.get('/api/backups', response_model=List[BackupRecord])
def list_backups(type: Optional[str] = None, admin=Depends(require_admin)):
    mgr = BackupManager()
    try:
        rows = mgr.list_backups(type=type)
        return [BackupRecord(**r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/api/backups/create', response_model=BackupRecord)
def create_backup(req: BackupCreateRequest, background_tasks: BackgroundTasks, admin=Depends(require_admin)):
    mgr = BackupManager()
    try:
        rec = mgr.create_backup(req.type, name=req.name, project_id=req.project_id)
        # Enqueue upload to R2 (non-blocking)
        background_tasks.add_task(mgr.sync_to_r2, rec['id'])
        return BackupRecord(**rec)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/api/backups/{backup_id}/sync-to-r2')
def sync_to_r2(backup_id: str, admin=Depends(require_admin)):
    mgr = BackupManager()
    try:
        ok = mgr.sync_to_r2(backup_id)
        return JSONResponse(content={'success': ok})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/api/backups/{backup_id}/restore')
def restore(backup_id: str, admin=Depends(require_admin)):
    mgr = BackupManager()
    try:
        task = mgr.restore_from_r2(backup_id)
        return JSONResponse(content={'task': task})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/api/backups/{backup_id}/download')
def download_backup(backup_id: str, admin=Depends(require_admin)):
    mgr = BackupManager()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT local_path,storage_key FROM backups WHERE id=?', (backup_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail='backup not found')
        local_path, storage_key = row

        if storage_key and (not local_path or not os.path.exists(local_path)):
            # download from r2 to local temp
            local_path = mgr.download_from_r2(backup_id)

        if not local_path or not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail='local backup file not available')

        return FileResponse(path=local_path, filename=os.path.basename(local_path), media_type='application/octet-stream')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- New: Zip-based backup service endpoints (local + R2) ----

class LocalBackupCreate(BaseModel):
    backup_type: str = "full"  # full | db_only | config_only


@router.get("/api/backup/status")
def backup_status():
    """Return whether R2 is configured and list counts."""
    try:
        local_list = []
        try:
            # svc_list_local_backups is async; resolve it from this sync route
            local_list = awaitable_to_result(svc_list_local_backups)
        except Exception:
            local_list = []
        r2_cfg = backup_service._is_r2_configured()
        r2_latest = None
        if r2_cfg:
            try:
                r2_list = []
                # list may raise if no credentials
                r2_list = awaitable_to_result(svc_list_r2_files)
                r2_latest = r2_list[0] if r2_list else None
            except Exception:
                r2_latest = None
        return {
            "r2_configured": bool(r2_cfg),
            "local_count": len(local_list or []),
            "r2_latest": r2_latest,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backup/history")
async def backup_history(limit: int = Query(10, ge=1, le=100)):
    """Return recent local backups in a normalized shape for the UI.

    Output: { success, backups: [{ filename, size, created_at }] }
    """
    try:
        items = await svc_list_local_backups()  # type: ignore[misc]
        # items come sorted (desc) by created; enforce limit
        items = (items or [])[:limit]
        normalized = []
        for it in items:
            normalized.append({
                "filename": it.get("name") or it.get("filename") or "",
                "size": it.get("size"),
                "created_at": it.get("created") or it.get("created_at"),
            })
        return {"success": True, "backups": normalized}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/backup/local/list")
async def list_local_backups():
    try:
        return await svc_list_local_backups()  # type: ignore[misc]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/backup/local/create")
async def create_local_backup(req: LocalBackupCreate, user=Depends(require_auth)):
    try:
        path = await svc_create_backup(req.backup_type)  # type: ignore[misc]
        return {"success": True, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- External DB specific backups (independent from R2) ----

EXTERNAL_DB_BACKUP_TYPES = [
    "db_only",            # SQLite + optional external pg_dump inside zip
    "external_sql_only",  # Only external pg_dump SQL inside zip
]


@router.get("/api/backup/external/types")
def external_backup_types():
    return {"success": True, "types": EXTERNAL_DB_BACKUP_TYPES}


class ExternalBackupCreate(BaseModel):
    backup_type: str = "db_only"  # db_only | external_sql_only


@router.post("/api/backup/external/create")
async def create_external_backup(req: ExternalBackupCreate, user=Depends(require_auth)):
    try:
        btype = (req.backup_type or "").strip()
        if btype not in EXTERNAL_DB_BACKUP_TYPES:
            return {"success": False, "error": f"Unsupported external backup_type: {btype}"}
        if btype == "external_sql_only":
            path = await svc_create_external_sql()  # type: ignore[misc]
        else:
            # db_only but do NOT upload to R2 by default here
            path = await svc_create_backup("db_only", upload_to_r2=False)  # type: ignore[misc]
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/backup/local/restore")
async def restore_local(backup_name: str, user=Depends(require_auth)):
    try:
        ok = await svc_restore_local_backup(backup_name)  # type: ignore[misc]
        return {"success": bool(ok)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backup/local/download")
def download_local(backup_name: str = Query(..., description=".zip file name under backups/")):
    try:
        path = os.path.join("backups", backup_name)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(path=path, filename=backup_name, media_type="application/zip")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/backup/local")
def delete_local_backup(backup_name: str, user=Depends(require_auth)):
    try:
        path = os.path.join("backups", backup_name)
        if os.path.exists(path):
            os.remove(path)
            return {"success": True}
        raise HTTPException(status_code=404, detail="file not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backup/r2/list")
async def list_r2(type: Optional[str] = Query(None, description="Filter by backup type contained in filename"), prefix: Optional[str] = Query(None, description="S3 key prefix to list (e.g., backups/database/ or backups/categories/<type>/)")):
    try:
        items = await svc_list_r2_files(prefix)  # type: ignore[misc]
        if type:
            # filenames are like flowslide_backup_{type}_YYYYMMDD_HHMMSS.zip
            key_sub = f"_{type}_"
            items = [it for it in items if key_sub in (it.get('key') or '')]
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/backup/r2/sync")
async def sync_latest_to_r2(backup_name: Optional[str] = None, user=Depends(require_auth)):
    """If backup_name provided, sync that specific file; else sync the latest local backup."""
    try:
        # Pre-check R2 configuration to avoid hard 500s
        if not backup_service._is_r2_configured():
            return {"success": False, "error": "R2 not configured. Please set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET_NAME."}
        # Reuse service method which accepts optional path: we pick path by name if provided
        from pathlib import Path
        target_path = None
        if backup_name:
            p = os.path.join("backups", backup_name)
            if not os.path.exists(p):
                return {"success": False, "error": "Local backup not found"}
            target_path = Path(p)
        info = await backup_service.sync_to_r2(target_path)  # type: ignore[misc]
        # Normalize success payload for UI
        info["success"] = True
        return info
    except HTTPException:
        raise
    except Exception as e:
        # Return graceful error for UI consumption
        return {"success": False, "error": str(e)}


# ---- New: Category-based create+sync to R2 (no pre-existing local zip required) ----

SUPPORTED_TYPES = [
    "full",
    "db_only",
    "config_only",
    "media_only",
    "templates_only",
    "reports_only",
    "scripts_only",
    "data_only",
]


class SyncTypeRequest(BaseModel):
    backup_type: str


@router.get("/api/backup/categories")
def list_categories():
    return {"success": True, "categories": SUPPORTED_TYPES}


@router.post("/api/backup/r2/sync-type")
async def sync_type_to_r2(req: SyncTypeRequest, user=Depends(require_auth)):
    try:
        if not backup_service._is_r2_configured():
            return {"success": False, "error": "R2 not configured. Please set R2_* envs."}
        btype = (req.backup_type or '').strip()
        if btype not in SUPPORTED_TYPES:
            return {"success": False, "error": f"Unsupported backup_type: {btype}"}

        # Create categorized backup on the fly
        path = await backup_service.create_backup(btype)  # type: ignore[misc]
        from pathlib import Path
        info = await backup_service.sync_to_r2(Path(path))  # type: ignore[misc]
        info["success"] = True
        info["backup_type"] = btype
        return info
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/backup/r2/restore")
async def restore_from_r2(key: str, user=Depends(require_auth)):
    try:
        return await svc_restore_r2_key(key)  # type: ignore[misc]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/backup/r2/object")
async def delete_r2_object(key: str, user=Depends(require_auth)):
    try:
        ok = await svc_delete_r2_file(key)  # type: ignore[misc]
        return {"success": bool(ok)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backup/r2/download")
async def download_r2_object(key: str):
    """Download a single object from R2 and stream it back as a file download."""
    if not backup_service._is_r2_configured():
        raise HTTPException(status_code=400, detail="R2 not configured")
    if boto3 is None:
        raise HTTPException(status_code=500, detail="boto3 not available on server")
    try:
        cfg = backup_service.r2_config
        s3 = boto3.client(
            "s3",
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            endpoint_url=cfg["endpoint"],
            config=BotoConfig(region_name="auto"),
        )
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        await _to_thread(s3.download_file, cfg["bucket"], key, tmp.name)
        filename = os.path.basename(key)
        return FileResponse(path=tmp.name, filename=filename, media_type="application/zip")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Backup config and cleanup (to satisfy UI) ----

class BackupConfig(BaseModel):
    auto_backup_enabled: bool = False
    backup_interval: int = 24  # hours
    max_backups: int = 10
    retention_days: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))


def _config_path() -> str:
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", "backup_config.json")


@router.get("/api/backup/config")
def get_backup_config():
    try:
        import json
        path = _config_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return {"success": True, "config": cfg}
        # default
        cfg = BackupConfig().model_dump()
        return {"success": True, "config": cfg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/backup/config")
def save_backup_config(cfg: BackupConfig, user=Depends(require_auth)):
    try:
        import json
        path = _config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg.model_dump(), f, ensure_ascii=False, indent=2)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/backup/cleanup")
def cleanup_old_backups(user=Depends(require_auth)):
    try:
        from datetime import datetime, timedelta
        backups_dir = os.path.join("backups")
        if not os.path.isdir(backups_dir):
            return {"success": True, "deleted_count": 0}

        # Load retention days from saved config or env
        retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        try:
            import json
            path = _config_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                retention_days = int(saved.get("retention_days", retention_days))
        except Exception:
            pass

        cutoff = datetime.now() - timedelta(days=retention_days)
        deleted = 0
        for name in os.listdir(backups_dir):
            if not name.endswith('.zip'):
                continue
            p = os.path.join(backups_dir, name)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(p))
                if mtime < cutoff:
                    os.remove(p)
                    deleted += 1
            except Exception:
                continue
        return {"success": True, "deleted_count": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- small utilities ----
def awaitable_to_result(coro_func):
    """Run an async function and return result if called from sync context.

    backup_status route is sync; this helper runs simple async funcs.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        # If already in an event loop, schedule and wait
        fut = loop.create_task(coro_func())
        # Not ideal to block, but used only for lightweight calls in admin route
        # The caller shouldn't be in an event loop here normally.
        # So fall back to run_until_complete when needed.
        # We'll try to access result with run_until_complete if no running loop.
        raise RuntimeError("running loop")
    except RuntimeError:
        # No running loop (or we forced path) -> create a new loop to run
        return _run_sync(coro_func)


def _run_sync(coro_func):
    import asyncio
    return asyncio.run(coro_func())


async def _to_thread(func, *args, **kwargs):
    import asyncio
    return await asyncio.to_thread(func, *args, **kwargs)
