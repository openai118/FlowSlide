"""
备份服务 - 集成R2云备份和本地备份功能
"""

import asyncio
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class BackupService:
    """备份服务"""

    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        self.backup_dir = Path("./backups")
        self.backup_dir.mkdir(exist_ok=True)

        # R2配置
        self.r2_config = {
            "access_key": os.getenv("R2_ACCESS_KEY_ID"),
            "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
            "endpoint": os.getenv("R2_ENDPOINT"),
            "bucket": os.getenv("R2_BUCKET_NAME")
        }

        # 备份配置
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        self.webhook_url = os.getenv("BACKUP_WEBHOOK_URL")

    async def create_backup(self, backup_type: str = "full", upload_to_r2: bool = True) -> str:
        """创建备份

        Args:
            backup_type: 备份类型 (full, db_only, config_only)

        Returns:
            备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"flowslide_backup_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)

        try:
            logger.info(f"📦 Creating {backup_type} backup: {backup_name}")

            if backup_type in ["full", "db_only", "data_only"]:
                await self._backup_database(backup_path)

            if backup_type in ["full", "config_only"]:
                await self._backup_config(backup_path)

            if backup_type in ["full", "media_only"]:
                await self._backup_uploads(backup_path)

            # Additional categorized content
            if backup_type in ["full", "templates_only"]:
                await self._backup_templates(backup_path)

            if backup_type in ["full", "reports_only"]:
                await self._backup_reports(backup_path)

            if backup_type in ["full", "scripts_only"]:
                await self._backup_scripts(backup_path)

            # 压缩备份
            archive_path = await self._compress_backup(backup_path)

            # 上传到R2（如果配置了且未禁用）
            if upload_to_r2 and self._is_r2_configured():
                await self._upload_to_r2(archive_path)

            # 清理旧备份
            await self._cleanup_old_backups()

            # 发送通知
            if self.webhook_url:
                await self._send_notification(backup_name, "success")

            logger.info(f"✅ Backup completed: {archive_path}")
            return str(archive_path)

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            if self.webhook_url:
                await self._send_notification(backup_name, "failed", str(e))
            raise

    async def create_external_sql_backup(self) -> str:
        """仅导出外部数据库的 SQL（不上传到 R2）。

        Returns:
            生成的 zip 文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"flowslide_external_sql_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)

        try:
            # strict=True: external SQL-only requires pg_dump to succeed
            await self._backup_external_database(backup_path, None, strict=True)
            archive_path = await self._compress_backup(backup_path)
            # 不上传到 R2
            return str(archive_path)
        except Exception as e:
            logger.error(f"❌ External SQL-only backup failed: {e}")
            raise

    async def _backup_database(self, backup_path: Path):
        """备份数据库"""
        try:
            # 总是优先备份本地SQLite（如果存在）
            db_file = Path("./data/flowslide.db")
            if db_file.exists():
                shutil.copy2(db_file, backup_path / "flowslide.db")
                logger.info("💾 Local SQLite database backup completed")

            # 如配置了外部数据库，则额外备份外部数据库
            try:
                from ..core.simple_config import EXTERNAL_DATABASE_URL
            except Exception:
                EXTERNAL_DATABASE_URL = os.getenv("DATABASE_URL", "")

            if EXTERNAL_DATABASE_URL and EXTERNAL_DATABASE_URL.startswith("postgres"):
                # strict=False: 常规备份中缺少 pg_dump 不应导致整个备份失败
                await self._backup_external_database(backup_path, EXTERNAL_DATABASE_URL, strict=False)

        except Exception as e:
            logger.error(f"❌ Database backup failed: {e}")
            raise

    async def _backup_external_database(self, backup_path: Path, external_url: Optional[str] = None, strict: bool = False):
        """备份外部数据库

        Behavior:
        - Prefer pg_dump for PostgreSQL.
        - If pg_dump is unavailable or fails and strict=True, fallback to Python-native COPY CSV export via psycopg2.
        - When strict=False, quietly skip external export on errors to not block other backup content.
        """
        try:
            # 优先使用传入URL，其次从配置获取
            if not external_url:
                try:
                    from ..core.simple_config import EXTERNAL_DATABASE_URL as CFG_URL
                    external_url = CFG_URL
                except Exception:
                    external_url = os.getenv("DATABASE_URL", "")

            if not external_url:
                msg = "ℹ️ No EXTERNAL_DATABASE_URL configured; skipping external DB backup"
                if strict:
                    raise RuntimeError("EXTERNAL_DATABASE_URL not configured for external SQL backup")
                logger.info(msg)
                return

            if not (external_url.startswith("postgresql://") or external_url.startswith("postgres://")):
                msg = "ℹ️ External DB URL is not PostgreSQL; skipping pg_dump backup"
                if strict:
                    raise RuntimeError("External SQL backup only supports PostgreSQL URLs")
                logger.info(msg)
                return

            # 尝试定位 pg_dump
            pg_dump_path = os.getenv("PG_DUMP_PATH")  # 可显式配置
            # 如果显式设置了路径但文件不存在，则视为未找到
            if pg_dump_path and not os.path.isfile(pg_dump_path):
                pg_dump_path = None
            if not pg_dump_path:
                # 使用系统PATH查找
                pg_dump_path = shutil.which("pg_dump")

            if not pg_dump_path:
                msg = (
                    "pg_dump not found. Please install PostgreSQL client tools and set PG_DUMP_PATH, or add pg_dump to PATH."
                )
                if strict:
                    logger.warning(f"{msg} Attempting Python-native COPY CSV fallback...")
                    try:
                        await self._export_external_postgres_copy(backup_path, external_url)
                        logger.info("✅ External database exported via COPY CSV fallback")
                        return
                    except Exception as fallback_err:
                        raise RuntimeError(f"External export failed and no pg_dump: {fallback_err}")
                logger.warning(f"{msg} Skipping external SQL export for this backup.")
                return

            # 解析URL，尽量避免将密码暴露在命令行（使用环境变量PGPASSWORD）
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(external_url)
            username = parsed.username or "postgres"
            password = parsed.password or ""
            host = parsed.hostname or "localhost"
            port = str(parsed.port or 5432)
            dbname = parsed.path.lstrip("/") or "postgres"
            qs = parse_qs(parsed.query or "")
            sslmode = (qs.get("sslmode", [None])[0]) or ("require" if ("supabase" in (parsed.hostname or "") or "pooler.supabase.com" in external_url) else None)

            # Supabase 提示：pg_dump 需要直连数据库实例，不建议使用 pooler 主机
            if parsed.hostname and "pooler.supabase.com" in parsed.hostname:
                logger.warning("⚠️ Detected Supabase pooler host; pg_dump may fail. Prefer the direct db.<project>.supabase.co host for dumps.")

            # 输出文件
            out_file = backup_path / f"external_{dbname}.sql"

            # 构建命令
            cmd = [
                pg_dump_path,
                "-h", host,
                "-p", port,
                "-U", username,
                "-d", dbname,
                "-F", "p",  # plain SQL
                "--no-owner",
                "--no-privileges",
                "-f", str(out_file),
            ]

            # 环境变量：PGPASSWORD / PGSSLMODE
            env = os.environ.copy()
            if password:
                env["PGPASSWORD"] = password
            if sslmode:
                env["PGSSLMODE"] = sslmode

            logger.info(f"🛸 Running pg_dump for external DB '{dbname}' on {host}:{port} -> {out_file.name}")

            def _run_dump():
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                return result

            result = await asyncio.to_thread(_run_dump)

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                stdout = (result.stdout or "").strip()
                if strict:
                    logger.warning(f"pg_dump failed (code {result.returncode}): {stderr or stdout}. Attempting COPY CSV fallback...")
                    try:
                        await self._export_external_postgres_copy(backup_path, external_url)
                        logger.info("✅ External database exported via COPY CSV fallback")
                        return
                    except Exception as fallback_err:
                        raise RuntimeError(f"pg_dump failed and COPY fallback failed: {fallback_err}")
                logger.warning(f"pg_dump failed (code {result.returncode}), skipping external SQL export: {stderr or stdout}")
                return

            if not out_file.exists() or out_file.stat().st_size == 0:
                if strict:
                    logger.warning("pg_dump produced no output file; attempting COPY CSV fallback...")
                    try:
                        await self._export_external_postgres_copy(backup_path, external_url)
                        logger.info("✅ External database exported via COPY CSV fallback")
                        return
                    except Exception as fallback_err:
                        raise RuntimeError(f"pg_dump produced no output and COPY fallback failed: {fallback_err}")
                logger.warning("pg_dump produced no output file; skipping external SQL export")
                return

            logger.info(f"✅ External PostgreSQL dump completed: {out_file} ({out_file.stat().st_size} bytes)")

        except Exception as e:
            logger.error(f"❌ External database backup failed: {e}")
            # 抛出异常，让调用方决定是否继续
            raise

    async def _export_external_postgres_copy(self, backup_path: Path, external_url: str) -> None:
        """使用 psycopg2 执行 PostgreSQL 的 CSV 导出（数据-only，schema 不包含）。

        生成文件：
        - tables/<schema>.<table>.csv 每个表一份 CSV（UTF-8，带表头）
        - external_copy_manifest.json 元数据（表清单、导出时间、连接主机/库名）
        """
        import json
        from urllib.parse import urlparse, parse_qs
        try:
            import psycopg2
        except Exception as ie:
            raise RuntimeError(f"psycopg2 not available: {ie}")

        parsed = urlparse(external_url)
        username = parsed.username or "postgres"
        password = parsed.password or ""
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        dbname = parsed.path.lstrip("/") or "postgres"
        qs = parse_qs(parsed.query or "")
        sslmode = (qs.get("sslmode", [None])[0]) or None

        conn_kwargs = {
            "user": username,
            "password": password,
            "host": host,
            "port": port,
            "dbname": dbname,
        }
        if sslmode:
            conn_kwargs["sslmode"] = sslmode

        tables_dir = backup_path / "tables"
        tables_dir.mkdir(exist_ok=True)

        def _run_copy():
            with psycopg2.connect(**conn_kwargs) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    # 获取用户表列表（排除系统 schema）
                    cur.execute(
                        """
                        SELECT table_schema, table_name
                        FROM information_schema.tables
                        WHERE table_type='BASE TABLE'
                          AND table_schema NOT IN ('pg_catalog','information_schema')
                        ORDER BY table_schema, table_name
                        """
                    )
                    rows = cur.fetchall()
                    exported = []
                    for schema, table in rows:
                        safe_name = f"{schema}.{table}"
                        out_path = tables_dir / f"{schema}.{table}.csv"
                        sql = f"COPY \"{schema}\".\"{table}\" TO STDOUT WITH CSV HEADER"
                        with open(out_path, "w", encoding="utf-8", newline="") as f:
                            cur.copy_expert(sql, f)
                        exported.append({"schema": schema, "table": table, "file": out_path.name})

            # 写入清单
            manifest = {
                "database": dbname,
                "host": host,
                "port": port,
                "exported_tables": exported,
                "exported_at": datetime.now().isoformat(),
                "format": "csv",
                "note": "Data-only export; schema DDL not included."
            }
            with open(backup_path / "external_copy_manifest.json", "w", encoding="utf-8") as mf:
                json.dump(manifest, mf, ensure_ascii=False, indent=2)

        # Run in thread to avoid blocking loop
        await asyncio.to_thread(_run_copy)

    async def _backup_config(self, backup_path: Path):
        """备份配置文件"""
        config_files = [".env", "pyproject.toml", "uv.toml"]

        for config_file in config_files:
            if Path(config_file).exists():
                shutil.copy2(config_file, backup_path / config_file)

        logger.info("⚙️ Config backup completed")

        # 附加：复制 src/config 下的配置（若存在）
        cfg_dir = Path("./src/config")
        if cfg_dir.exists() and cfg_dir.is_dir():
            dest = backup_path / "src_config"
            shutil.copytree(cfg_dir, dest, dirs_exist_ok=True)
            logger.info("📁 src/config included in config backup")

    async def _backup_uploads(self, backup_path: Path):
        """备份上传文件"""
        uploads_dir = Path("./uploads")
        if uploads_dir.exists():
            shutil.copytree(uploads_dir, backup_path / "uploads", dirs_exist_ok=True)
            logger.info("📁 Uploads backup completed")

    async def _backup_templates(self, backup_path: Path):
        """备份模板示例"""
        t_dir = Path("./template_examples")
        if t_dir.exists():
            shutil.copytree(t_dir, backup_path / "template_examples", dirs_exist_ok=True)
            logger.info("📚 Template examples backup completed")

    async def _backup_reports(self, backup_path: Path):
        """备份研究报告"""
        r_dir = Path("./research_reports")
        if r_dir.exists():
            shutil.copytree(r_dir, backup_path / "research_reports", dirs_exist_ok=True)
            logger.info("📑 Research reports backup completed")

    async def _backup_scripts(self, backup_path: Path):
        """备份脚本"""
        s_dir = Path("./scripts")
        if s_dir.exists():
            shutil.copytree(s_dir, backup_path / "scripts", dirs_exist_ok=True)
            logger.info("🔧 Scripts backup completed")

    async def _compress_backup(self, backup_path: Path) -> Path:
        """压缩备份文件"""
        import zipfile

        archive_path = backup_path.with_suffix('.zip')

        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in backup_path.rglob('*'):
                if file_path.is_file():
                    zipf.write(file_path, file_path.relative_to(backup_path.parent))

        # 删除原始备份目录
        shutil.rmtree(backup_path)

        logger.info(f"🗜️ Backup compressed: {archive_path}")
        return archive_path

    async def _upload_to_r2(self, backup_path: Path):
        """上传备份到R2"""
        if not self._is_r2_configured():
            logger.info("ℹ️ R2 not configured, skipping cloud backup")
            return

        try:
            logger.info(f"☁️ Starting R2 upload: {backup_path.name}")

            # 创建S3客户端，配置为R2
            from botocore.config import Config
            config = Config(
                region_name='auto',
                retries={'max_attempts': 3, 'mode': 'standard'},
                read_timeout=30,
                connect_timeout=15,
                signature_version='s3v4'
            )

            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.r2_config['access_key'],
                aws_secret_access_key=self.r2_config['secret_key'],
                endpoint_url=self.r2_config['endpoint'],
                config=config
            )

            # 生成按类别的前缀与日期目录
            backup_date = datetime.now().strftime("%Y-%m-%d")
            # 期望文件名格式：flowslide_backup_{type}_YYYYMMDD_HHMMSS.zip
            name = backup_path.name
            type_segment = "misc"
            try:
                # flowslide_backup_ + rest
                rest = name[len("flowslide_backup_"):]
                type_segment = rest.split("_")[0] or "misc"
            except Exception:
                type_segment = "misc"

            # 将 db_only 归类到 database 前缀；其他走 categories/{type}
            if type_segment == "db_only":
                s3_key = f"backups/database/{backup_date}/{backup_path.name}"
            else:
                s3_key = f"backups/categories/{type_segment}/{backup_date}/{backup_path.name}"

            # 上传文件
            logger.info(f"Uploading to R2: {self.r2_config['bucket']}/{s3_key}")

            # 使用asyncio.to_thread在后台线程中运行同步的boto3操作
            await asyncio.to_thread(
                s3_client.upload_file,
                str(backup_path),
                self.r2_config['bucket'],
                s3_key
            )

            logger.info(f"✅ R2 upload completed successfully: {backup_path.name}")

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"❌ R2 upload failed (AWS Error {error_code}): {error_msg}")
            raise Exception(f"R2 upload failed: {error_msg}")
        except Exception as e:
            logger.error(f"❌ R2 upload failed: {e}")
            # 不抛出异常，因为本地备份已经成功

    def _is_r2_configured(self) -> bool:
        """检查R2是否配置"""
        return all(self.r2_config.values())

    async def _cleanup_old_backups(self):
        """清理旧备份"""
        try:
            cutoff_date = datetime.now().timestamp() - (self.retention_days * 24 * 60 * 60)

            for backup_file in self.backup_dir.glob("*.zip"):
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()
                    logger.info(f"🗑️ Cleaned up old backup: {backup_file.name}")

        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")

    async def _send_notification(self, backup_name: str, status: str, error: Optional[str] = None):
        """发送备份通知"""
        if not self.webhook_url:
            return

        try:
            import aiohttp

            message = {
                "backup_name": backup_name,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "error": error
            }

            async with aiohttp.ClientSession() as session:
                await session.post(self.webhook_url, json=message)

        except Exception as e:
            logger.error(f"❌ Notification failed: {e}")

    async def sync_to_r2(self, backup_path: Optional[Path] = None) -> Dict[str, Any]:
        """同步备份到R2云存储

        Args:
            backup_path: 指定的备份文件路径，如果为None则使用最新的备份

        Returns:
            同步结果信息
        """
        if not self._is_r2_configured():
            raise Exception("R2云存储未配置")

        try:
            # 如果没有指定备份路径，使用最新的备份
            if backup_path is None:
                backups = await list_backups()
                if not backups:
                    raise Exception("没有找到备份文件进行同步")
                backup_path = Path(backups[0]["path"])

            # 确保备份文件存在
            if not backup_path.exists():
                raise FileNotFoundError(f"备份文件不存在: {backup_path}")

            logger.info(f"☁️ Starting R2 sync: {backup_path.name}")

            # 上传到R2
            await self._upload_to_r2(backup_path)

            sync_info = {
                "filename": backup_path.name,
                "size": backup_path.stat().st_size,
                "timestamp": datetime.now().isoformat(),
                # created_at is the file mtime (when the backup file was created)
                "created_at": datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(),
                "success": True
            }

            logger.info(f"✅ R2 sync completed: {backup_path.name}")
            return sync_info

        except Exception as e:
            logger.error(f"❌ R2 sync failed: {e}")
            raise

    def list_backups(self) -> list:
        """列出所有备份"""
        backups = []
        for backup_file in self.backup_dir.glob("*.zip"):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(backup_file)
            })

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    async def restore_backup(self, backup_name: str) -> bool:
        """恢复备份"""
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")

        try:
            logger.info(f"🔄 Restoring backup: {backup_name}")

            # 创建临时恢复目录
            restore_temp_dir = self.backup_dir / f"restore_temp_{int(time.time())}"
            restore_temp_dir.mkdir(exist_ok=True)

            def extract_and_restore():
                import zipfile
                import shutil
                from pathlib import Path

                try:
                    # 解压备份文件
                    logger.info(f"📦 Extracting backup: {backup_name}")
                    with zipfile.ZipFile(str(backup_path), 'r') as zip_ref:
                        zip_ref.extractall(str(restore_temp_dir))

                    # 查找数据库文件（递归查找）
                    db_files = list(restore_temp_dir.rglob("*.db"))
                    if not db_files:
                        raise Exception("备份文件中没有找到数据库文件")

                    db_file = db_files[0]
                    logger.info(f"🗄️ Found database file: {db_file.name} at {db_file}")

                    # 备份当前数据库
                    current_db_path = Path("./data/flowslide.db")
                    if current_db_path.exists():
                        backup_current = current_db_path.with_suffix('.db.backup')
                        shutil.copy2(str(current_db_path), str(backup_current))
                        logger.info(f"💾 Backed up current database to: {backup_current}")

                    # 恢复数据库文件
                    shutil.copy2(str(db_file), str(current_db_path))
                    logger.info(f"✅ Database restored from: {db_file.name}")

                    # 恢复上传文件（如果存在）
                    uploads_dirs = list(restore_temp_dir.rglob("uploads"))
                    if uploads_dirs:
                        uploads_dir = uploads_dirs[0]
                        if uploads_dir.exists() and uploads_dir.is_dir():
                            target_uploads = Path("./uploads")
                            if target_uploads.exists():
                                shutil.rmtree(str(target_uploads))
                            shutil.copytree(str(uploads_dir), str(target_uploads))
                            logger.info("📁 Uploads directory restored")

                    # 恢复配置文件（如果存在）
                    config_files = list(restore_temp_dir.rglob("*.json")) + list(restore_temp_dir.rglob("*.yaml")) + list(restore_temp_dir.rglob("*.yml"))
                    for config_file in config_files:
                        if "flowslide" in config_file.name.lower():
                            target_config = Path(".") / config_file.name
                            shutil.copy2(str(config_file), str(target_config))
                            logger.info(f"⚙️ Config file restored: {config_file.name}")

                    logger.info("✅ Backup restored successfully")
                    return True

                except Exception as e:
                    logger.error(f"❌ Restore operation failed: {e}")
                    # 尝试恢复原始数据库
                    current_db_path = Path("./data/flowslide.db")
                    backup_current = current_db_path.with_suffix('.db.backup')
                    if backup_current.exists():
                        shutil.copy2(str(backup_current), str(current_db_path))
                        logger.info("🔄 Original database restored from backup")
                    raise
                finally:
                    # 清理临时文件
                    if restore_temp_dir.exists():
                        shutil.rmtree(str(restore_temp_dir))
                        logger.info("🧹 Temporary restore files cleaned up")

            # 在线程池中运行恢复操作
            await asyncio.to_thread(extract_and_restore)
            return True

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False

    async def restore_from_r2(self) -> Dict[str, Any]:
        """从R2恢复最新的备份，如果R2不可用则使用本地备份"""
        try:
            logger.info("🔄 Starting R2 restore...")

            # 首先尝试R2恢复
            try:
                return await self._restore_from_r2_cloud()
            except Exception as r2_error:
                logger.warning(f"⚠️ R2恢复失败: {r2_error}")
                logger.info("🔄 尝试使用本地备份恢复...")

                # 回退到本地备份
                return await self._restore_from_local_backup()

        except Exception as e:
            logger.error(f"❌ 所有恢复方法都失败: {e}")
            raise

    async def _restore_from_r2_cloud(self) -> Dict[str, Any]:
        """从R2云存储恢复"""
        # 检查R2配置
        if not self._is_r2_configured():
            error_msg = "R2云存储未配置。请检查以下环境变量：R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET_NAME"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        # 验证配置值
        missing_configs = []
        if not self.r2_config.get('access_key'):
            missing_configs.append('R2_ACCESS_KEY_ID')
        if not self.r2_config.get('secret_key'):
            missing_configs.append('R2_SECRET_ACCESS_KEY')
        if not self.r2_config.get('endpoint'):
            missing_configs.append('R2_ENDPOINT')
        if not self.r2_config.get('bucket'):
            missing_configs.append('R2_BUCKET_NAME')

        if missing_configs:
            error_msg = f"R2配置不完整，缺少: {', '.join(missing_configs)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        logger.info(f"✅ R2配置验证通过 - Bucket: {self.r2_config['bucket']}")

        # 创建S3客户端，配置为R2
        try:
            from botocore.config import Config
            config = Config(
                region_name='auto',
                retries={'max_attempts': 3, 'mode': 'standard'},
                read_timeout=30,
                connect_timeout=15,
                signature_version='s3v4'
            )

            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.r2_config['access_key'],
                aws_secret_access_key=self.r2_config['secret_key'],
                endpoint_url=self.r2_config['endpoint'],
                config=config
            )
            logger.info("✅ S3客户端创建成功")
        except Exception as e:
            error_msg = f"创建R2客户端失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        # 列出R2中的备份文件
        try:
            logger.info("📋 正在列出R2中的备份文件...")
            logger.info(f"🔍 搜索存储桶: {self.r2_config['bucket']}, 前缀: backups/")

            response = s3_client.list_objects_v2(
                Bucket=self.r2_config['bucket'],
                Prefix='backups/'
            )
            logger.info(f"✅ 成功连接到R2存储桶: {self.r2_config['bucket']}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"❌ 无法访问R2存储桶 (AWS Error {error_code}): {error_msg}")
            logger.error(f"🔍 调试信息: 存储桶={self.r2_config['bucket']}, 端点={self.r2_config['endpoint']}")
            raise Exception(f"无法访问R2存储桶: {error_msg}")
        except Exception as e:
            error_msg = f"连接R2失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"🔍 调试信息: 类型={type(e).__name__}, 消息={str(e)}")
            raise Exception(error_msg)

        if 'Contents' not in response or not response['Contents']:
            error_msg = f"在R2存储桶 '{self.r2_config['bucket']}' 中没有找到备份文件。请确保已上传备份文件。"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        # 找到最新的备份文件
        latest_backup = max(response['Contents'], key=lambda x: x['LastModified'])
        backup_key = latest_backup['Key']
        backup_size = latest_backup['Size']
        backup_date = latest_backup['LastModified']

        logger.info(f"📥 找到最新备份: {backup_key}")
        logger.info(f"   📅 修改时间: {backup_date}")
        logger.info(f"   📏 文件大小: {backup_size} bytes")

        # 确保备份目录存在
        try:
            self.backup_dir.mkdir(exist_ok=True)
            logger.info(f"✅ 备份目录准备就绪: {self.backup_dir}")
        except Exception as e:
            error_msg = f"创建备份目录失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        local_backup_path = self.backup_dir / Path(backup_key).name

        # 下载备份文件
        try:
            logger.info(f"📥 正在下载备份文件到: {local_backup_path}")
            await asyncio.to_thread(
                s3_client.download_file,
                self.r2_config['bucket'],
                backup_key,
                str(local_backup_path)
            )
            logger.info("✅ 文件下载完成")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"❌ 下载失败 (AWS Error {error_code}): {error_msg}")
            raise Exception(f"从R2下载备份失败: {error_msg}")
        except Exception as e:
            error_msg = f"下载备份文件时发生错误: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        # 验证下载的文件
        if not local_backup_path.exists():
            error_msg = f"下载完成后文件不存在: {local_backup_path}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        downloaded_size = local_backup_path.stat().st_size
        if downloaded_size != backup_size:
            error_msg = f"文件下载不完整。期望: {backup_size} bytes, 实际: {downloaded_size} bytes"
            logger.error(f"❌ {error_msg}")
            # 删除不完整的文件
            local_backup_path.unlink(missing_ok=True)
            raise Exception(error_msg)

        logger.info(f"✅ 备份文件验证通过: {local_backup_path} ({downloaded_size} bytes)")

        # 恢复备份
        try:
            logger.info("🔄 正在恢复备份...")
            success = await self.restore_backup(local_backup_path.name)

            if success:
                restore_info = {
                    "filename": local_backup_path.name,
                    "size": downloaded_size,
                    "timestamp": datetime.now().isoformat(),
                    "source": "r2",
                    "r2_key": backup_key,
                    "r2_bucket": self.r2_config['bucket'],
                    "backup_date": backup_date.isoformat(),
                    "success": True
                }
                logger.info(f"✅ R2恢复完成: {local_backup_path.name}")
                return restore_info
            else:
                error_msg = "备份恢复过程返回失败状态"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)

        except Exception as e:
            error_msg = f"恢复备份时发生错误: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

    async def _restore_from_local_backup(self) -> Dict[str, Any]:
        """从本地备份恢复"""
        try:
            logger.info("🔄 使用本地备份进行恢复...")

            # 查找可用的本地备份
            if not self.backup_dir.exists():
                raise Exception("备份目录不存在")

            backup_files = list(self.backup_dir.glob("*.zip"))
            if not backup_files:
                raise Exception("没有找到本地备份文件")

            # 使用最新的备份
            latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
            logger.info(f"📁 使用本地备份: {latest_backup.name}")

            # 恢复备份
            success = await self.restore_backup(latest_backup.name)

            if success:
                restore_info = {
                    "filename": latest_backup.name,
                    "size": latest_backup.stat().st_size,
                    "timestamp": datetime.now().isoformat(),
                    "source": "local",
                    "success": True
                }
                logger.info(f"✅ 本地备份恢复完成: {latest_backup.name}")
                return restore_info
            else:
                raise Exception("本地备份恢复失败")

        except Exception as e:
            logger.error(f"❌ 本地备份恢复失败: {e}")
            raise


# 创建全局备份服务实例
backup_service = BackupService()


async def create_backup(backup_type: str = "full", upload_to_r2: bool = True) -> str:
    """创建备份"""
    return await backup_service.create_backup(backup_type, upload_to_r2)


async def list_backups() -> list:
    """列出备份"""
    return backup_service.list_backups()

async def create_external_sql_backup() -> str:
    """Module-level helper: 仅导出外部数据库 SQL 到本地备份。"""
    return await backup_service.create_external_sql_backup()


async def list_r2_files(prefix: Optional[str] = None) -> list:
    """Module-level helper: 列出R2中指定前缀下的对象（返回 key/name, size, last_modified）

    Args:
        prefix: 仅列出该前缀下的对象；默认列出 backups/
    """
    # use global backup_service instance
    if not backup_service._is_r2_configured():
        return []

    try:
        from botocore.config import Config
        config = Config(region_name='auto')
        s3_client = boto3.client(
            's3',
            aws_access_key_id=backup_service.r2_config['access_key'],
            aws_secret_access_key=backup_service.r2_config['secret_key'],
            endpoint_url=backup_service.r2_config['endpoint'],
            config=config
        )
        effective_prefix = prefix or 'backups/'
        response = s3_client.list_objects_v2(
            Bucket=backup_service.r2_config['bucket'],
            Prefix=effective_prefix
        )
        items = []
        if 'Contents' in response and response['Contents']:
            for obj in response['Contents']:
                items.append({
                    'key': obj.get('Key'),
                    'size': obj.get('Size'),
                    'last_modified': obj.get('LastModified').isoformat() if obj.get('LastModified') else None
                })
        items.sort(key=lambda x: x.get('last_modified') or '', reverse=True)
        return items
    except Exception as e:
        logger.warning(f"list_r2_files failed: {e}")
        return []


async def delete_r2_file(key: str) -> bool:
    """Module-level helper: 从R2删除指定对象（key）"""
    if not backup_service._is_r2_configured():
        raise Exception("R2未配置")

    try:
        from botocore.config import Config
        config = Config(region_name='auto')
        s3_client = boto3.client(
            's3',
            aws_access_key_id=backup_service.r2_config['access_key'],
            aws_secret_access_key=backup_service.r2_config['secret_key'],
            endpoint_url=backup_service.r2_config['endpoint'],
            config=config
        )

        await asyncio.to_thread(s3_client.delete_object, Bucket=backup_service.r2_config['bucket'], Key=key)
        logger.info(f"✅ R2 object deleted: {key}")
        return True
    except Exception as e:
        logger.error(f"❌ delete_r2_file failed: {e}")
        return False


async def restore_r2_key(key: str) -> Dict[str, Any]:
    """Module-level helper: 从R2下载指定 key 并恢复该备份（将文件下载到 backup_dir 并调用 restore_backup）"""
    if not backup_service._is_r2_configured():
        raise Exception("R2未配置")

    try:
        from botocore.config import Config
        config = Config(region_name='auto')
        s3_client = boto3.client(
            's3',
            aws_access_key_id=backup_service.r2_config['access_key'],
            aws_secret_access_key=backup_service.r2_config['secret_key'],
            endpoint_url=backup_service.r2_config['endpoint'],
            config=config
        )

        backup_service.backup_dir.mkdir(exist_ok=True)
        local_backup_path = backup_service.backup_dir / Path(key).name

        await asyncio.to_thread(
            s3_client.download_file,
            backup_service.r2_config['bucket'],
            key,
            str(local_backup_path)
        )

        if not local_backup_path.exists():
            raise Exception("下载后的文件不存在")

        success = await backup_service.restore_backup(local_backup_path.name)
        if not success:
            raise Exception("恢复失败")

        return {
            'filename': local_backup_path.name,
            'size': local_backup_path.stat().st_size,
            'timestamp': datetime.now().isoformat(),
            'source': 'r2',
            'r2_key': key,
            'r2_bucket': backup_service.r2_config['bucket'],
            'success': True
        }
    except Exception as e:
        logger.error(f"❌ restore_r2_key failed: {e}")
        raise


async def restore_backup(backup_name: str) -> bool:
    """恢复备份"""
    return await backup_service.restore_backup(backup_name)
