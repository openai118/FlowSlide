from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os

from ..auth.middleware import require_admin
from src.flowslide.services.backup_manager import BackupManager, ensure_schema, get_conn

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

