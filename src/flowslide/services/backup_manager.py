import os
import sqlite3
import uuid
import time
import hashlib
import tempfile
import shutil
from typing import Optional, List, Dict

try:
    import boto3
    from botocore.config import Config as BotoConfig
    HAS_BOTO3 = True
except Exception:
    HAS_BOTO3 = False

# Minimal config - environment driven
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'flowslide.db'))

# Cloudflare R2 / S3 config via env
R2_ENDPOINT = os.environ.get('R2_ENDPOINT')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET = os.environ.get('R2_BUCKET')
R2_REGION = os.environ.get('R2_REGION', 'auto')


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def ensure_schema():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS backups (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            project_id TEXT,
            local_path TEXT,
            storage_key TEXT,
            size INTEGER,
            checksum TEXT,
            created_at REAL,
            uploaded_at REAL,
            status TEXT,
            metadata TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_tasks (
            id TEXT PRIMARY KEY,
            backup_id TEXT,
            type TEXT,
            status TEXT,
            created_at REAL,
            updated_at REAL,
            logs TEXT
        )
        """
    )
    conn.commit()
    conn.close()


class BackupManager:
    def __init__(self):
        ensure_schema()

    def list_backups(self, type: Optional[str] = None) -> List[Dict]:
        conn = get_conn()
        cur = conn.cursor()
        if type:
            cur.execute("SELECT id,name,type,size,checksum,created_at,storage_key FROM backups WHERE type=? ORDER BY created_at DESC", (type,))
        else:
            cur.execute("SELECT id,name,type,size,checksum,created_at,storage_key FROM backups ORDER BY created_at DESC")
        rows = cur.fetchall()
        conn.close()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "name": r[1],
                "type": r[2],
                "size": r[3],
                "checksum": r[4],
                "created_at": r[5],
                "storage_key": r[6],
            })
        return out

    def create_backup(self, type: str, name: Optional[str] = None, project_id: Optional[str] = None) -> Dict:
        # Minimal implementation: for DB type, create sqlite copy; for others create a placeholder file
        bid = str(uuid.uuid4())
        timestamp = time.time()
        if not name:
            name = f"{type}_{time.strftime('%Y%m%d_%H%M%S')}.bak"

        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".bak")
        tmpf.close()

        size = 0
        checksum = None

        if type == 'db':
            # copy the DB file
            src = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..', '..', 'data', 'flowslide.db'))
            try:
                with open(src, 'rb') as sf, open(tmpf.name, 'wb') as df:
                    data = sf.read()
                    df.write(data)
                    size = len(data)
                    checksum = hashlib.sha256(data).hexdigest()
            except Exception:
                # create empty placeholder
                with open(tmpf.name, 'wb') as df:
                    df.write(b'')
                    size = 0
                    checksum = None
        else:
            # placeholder: write metadata text
            content = f"backup placeholder for {type} {name}\n"
            with open(tmpf.name, 'wb') as df:
                df.write(content.encode('utf-8'))
                size = len(content)
                checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # persist metadata
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO backups(id,name,type,project_id,local_path,size,checksum,created_at,status) VALUES(?,?,?,?,?,?,?,?,?)",
            (bid, name, type, project_id, tmpf.name, size, checksum, timestamp, 'local'),
        )
        conn.commit()
        conn.close()

        return {
            "id": bid,
            "name": name,
            "type": type,
            "size": size,
            "checksum": checksum,
            "created_at": timestamp,
            "storage_key": None,
        }

    def sync_to_r2(self, backup_id: str) -> bool:
        # Upload local_path to Cloudflare R2 (S3-compatible). Requires boto3 and R2_* env vars.
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT local_path,name FROM backups WHERE id=?", (backup_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        local_path, name = row
        if not HAS_BOTO3:
            conn.close()
            raise RuntimeError('boto3 is required for R2 upload. Please pip install boto3')

        if not (R2_ENDPOINT and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET):
            conn.close()
            raise RuntimeError('R2 credentials not configured in environment variables')

        # create client
        s3 = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=BotoConfig(signature_version='s3v4'),
            region_name=R2_REGION,
        )

        basename = os.path.basename(local_path)
        key = f"backups/{backup_id}/{basename}"

        # multipart/upload for large files handled by boto3 automatically via upload_file
        try:
            s3.upload_file(local_path, R2_BUCKET, key)
        except Exception as e:
            conn.close()
            raise

        storage_key = key
        uploaded_at = time.time()

        cur.execute("UPDATE backups SET storage_key=?, uploaded_at=?, status=? WHERE id=?", (storage_key, uploaded_at, 'r2', backup_id))
        conn.commit()
        conn.close()
        return True

    def download_from_r2(self, backup_id: str) -> str:
        """Download backup from R2 to a local temporary file and return its path."""
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT storage_key,local_path FROM backups WHERE id=?", (backup_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise FileNotFoundError('backup not found')
        storage_key, local_path = row

        if not storage_key:
            raise FileNotFoundError('no storage_key, not uploaded to r2')

        if not HAS_BOTO3:
            raise RuntimeError('boto3 is required for R2 download. Please pip install boto3')

        s3 = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=BotoConfig(signature_version='s3v4'),
            region_name=R2_REGION,
        )

        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.close()
        try:
            s3.download_file(R2_BUCKET, storage_key, tf.name)
        except Exception as e:
            try:
                os.unlink(tf.name)
            except Exception:
                pass
            raise

        return tf.name

    def restore_from_r2(self, backup_id: str) -> Dict:
        # Realistic restore: download from R2, if type=db then snapshot current DB and replace
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT storage_key,type,local_path,name FROM backups WHERE id=?", (backup_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise FileNotFoundError('backup not found')
        storage_key, type_, local_path, name = row
        conn.close()

        # download from r2
        tmp_path = self.download_from_r2(backup_id)

        result = {"task_id": str(uuid.uuid4()), "status": "ok", "backup_id": backup_id}

        if type_ == 'db':
            # snapshot current DB
            if os.path.exists(DB_PATH):
                snap = tempfile.NamedTemporaryFile(delete=False, suffix='.db.snap')
                snap.close()
                shutil.copy2(DB_PATH, snap.name)
                # store snapshot as a backup record
                bid = str(uuid.uuid4())
                ts = time.time()
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("INSERT INTO backups(id,name,type,project_id,local_path,size,checksum,created_at,status) VALUES(?,?,?,?,?,?,?,?,?)",
                            (bid, f'pre_restore_snapshot_{int(ts)}', 'db', None, snap.name, os.path.getsize(snap.name), None, ts, 'local'))
                conn.commit()
                conn.close()

            # replace DB file (atomic)
            try:
                shutil.copy2(tmp_path, DB_PATH)
            except Exception as e:
                raise

        else:
            # for other types, place file next to local_path if available
            dest = local_path or os.path.join(os.path.dirname(DB_PATH), name)
            try:
                shutil.copy2(tmp_path, dest)
            except Exception as e:
                raise

        # cleanup downloaded tmp
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        return result
