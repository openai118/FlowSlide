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

    def refresh_r2_config(self) -> None:
        """Refresh R2 configuration from current environment (.env + process).

        Ensures runtime changes made via the UI are recognized without restart.
        """
        try:
            load_dotenv(override=True)
        except Exception:
            # best-effort reload
            pass
        self.r2_config.update({
            "access_key": os.getenv("R2_ACCESS_KEY_ID"),
            "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
            "endpoint": os.getenv("R2_ENDPOINT"),
            "bucket": os.getenv("R2_BUCKET_NAME"),
        })

    async def create_backup(self, backup_type: str = "full", upload_to_r2: bool = True) -> str:
        """创建备份

        Args:
            backup_type: 备份类型 (full, db_only, config_only, media_only, templates_only, reports_only, scripts_only, light)

        Returns:
            备份文件路径
        """
        # 扩展支持轻量数据同步备份：仅包含 users / projects / ppt_templates / global_master_templates 以及配置文件 JSON 快照
        # 该轻量包不复制数据库文件和uploads，便于快速在另一实例进行部分合并恢复
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

            # 特殊：light 走定制JSON打包逻辑（忽略上面可能创建的空目录内容）
            if backup_type == "light":
                archive_path = await self._create_light_backup_archive(backup_path)
            else:
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

    async def create_light_ephemeral_archive(self) -> Path:
        """创建不落地(backups目录)的轻量备份压缩包, 仅返回临时 zip 路径。

        用于“同步到R2”按钮：生成后直接上传并删除，不计入本地备份列表。
        """
        from tempfile import TemporaryDirectory
        import json, sqlite3, zipfile
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"flowslide_backup_light_{ts}.zip"
        tmp_dir_ctx = TemporaryDirectory()
        base = Path(tmp_dir_ctx.name) / "light_build"
        data_dir = base / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        db_file = Path("./data/flowslide.db")
        if db_file.exists():
            try:
                conn = sqlite3.connect(str(db_file))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                def dump(q, name):
                    try:
                        cur.execute(q)
                        rows = [dict(r) for r in cur.fetchall()]
                        (data_dir / name).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
                    except Exception as ie:
                        logger.warning(f"light ephemeral dump {name} failed: {ie}")
                dump("SELECT id, username, email, is_active, is_admin, created_at, updated_at, last_login, password_hash FROM users", "users.json")
                dump("SELECT id, project_id, title, scenario, topic, requirements, status, owner_id, outline, slides_html, slides_data, confirmed_requirements, project_metadata, version, created_at, updated_at FROM projects", "projects.json")
                dump("SELECT id, project_id, template_type, template_name, description, html_template, applicable_scenarios, style_config, usage_count, created_at, updated_at FROM ppt_templates", "ppt_templates.json")
                dump("SELECT id, template_name, description, html_template, preview_image, style_config, tags, is_default, is_active, usage_count, created_by, created_at, updated_at FROM global_master_templates", "global_master_templates.json")
            except Exception as e:
                logger.warning(f"⚠️ light ephemeral read db failed: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        else:
            logger.warning("⚠️ flowslide.db 不存在，light 临时包不含数据表")

        # 配置文件简要收集
        config_payload = {"root_files": {}, "src_config": {}}
        for name in [".env", "pyproject.toml", "uv.toml"]:
            p = Path(name)
            if p.exists():
                try:
                    txt = p.read_text(encoding='utf-8', errors='ignore')
                    if name == '.env':
                        try:
                            txt = self._filter_env_content(txt)
                        except Exception as _fe:
                            logger.warning(f"轻量临时包 .env 过滤失败: {_fe}")
                    config_payload["root_files"][name] = txt
                except Exception:
                    pass
        cfg_dir = Path("./src/config")
        if cfg_dir.exists():
            for fp in cfg_dir.rglob('*'):
                if fp.is_file() and fp.suffix.lower() in ('.json', '.yaml', '.yml', '.toml'):
                    rel = str(fp.relative_to(cfg_dir))
                    try:
                        config_payload["src_config"][rel] = fp.read_text(encoding='utf-8', errors='ignore')
                    except Exception:
                        pass
        (data_dir / 'config_files.json').write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding='utf-8')

        manifest = {
            "type": "light",
            "schema_version": 1,
            "generated_at": datetime.now().isoformat(),
            "description": "Lightweight selective dataset (users/projects/templates/config)",
            "tables": ["users", "projects", "ppt_templates", "global_master_templates"],
        }
        (base / 'light_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

        zip_path = Path(tmp_dir_ctx.name) / archive_name
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in base.rglob('*'):
                if p.is_file():
                    zf.write(p, p.relative_to(base.parent))
        logger.info(f"🪶 Created ephemeral light archive: {zip_path}")
        # 返回 (zip_path, tmp_dir_ctx) 由调用方持有 tmp_dir_ctx 防止提前清理
        return (zip_path, tmp_dir_ctx)

    async def upload_light_ephemeral(self, archive_path: Path) -> Dict[str, Any]:
        """上传 light 临时包到 R2，只保留 latest 与 backup 两个对象。"""
        if not self._is_r2_configured():
            raise Exception("R2未配置")
        from botocore.config import Config
        cfg = Config(region_name='auto', retries={'max_attempts':3,'mode':'standard'})
        s3 = boto3.client(
            's3',
            aws_access_key_id=self.r2_config['access_key'],
            aws_secret_access_key=self.r2_config['secret_key'],
            endpoint_url=self.r2_config['endpoint'],
            config=cfg
        )
        bucket = self.r2_config['bucket']
        prefix = 'backups/light/'
        latest_key = prefix + 'flowslide_light_latest.zip'
        backup_key = prefix + 'flowslide_light_backup.zip'

        async def _exists(k: str) -> bool:
            try:
                await asyncio.to_thread(s3.head_object, Bucket=bucket, Key=k)
                return True
            except Exception:
                return False

        # 删除旧 backup
        try:
            await asyncio.to_thread(s3.delete_object, Bucket=bucket, Key=backup_key)
        except Exception:
            pass

        # latest -> backup
        if await _exists(latest_key):
            try:
                await asyncio.to_thread(
                    s3.copy_object,
                    Bucket=bucket,
                    CopySource={'Bucket': bucket, 'Key': latest_key},
                    Key=backup_key
                )
                await asyncio.to_thread(s3.delete_object, Bucket=bucket, Key=latest_key)
            except Exception as e:
                logger.warning(f"复制 latest->backup 失败: {e}")

        # 上传新 latest
        await asyncio.to_thread(s3.upload_file, str(archive_path), bucket, latest_key)

        # 清理其它同前缀对象
        try:
            resp = await asyncio.to_thread(s3.list_objects_v2, Bucket=bucket, Prefix=prefix)
            allowed = {latest_key, backup_key}
            for obj in resp.get('Contents', []) if resp else []:
                k = obj.get('Key')
                if k and k not in allowed:
                    try:
                        await asyncio.to_thread(s3.delete_object, Bucket=bucket, Key=k)
                    except Exception:
                        pass
        except Exception:
            pass

        info = {
            'filename': 'flowslide_light_latest.zip',
            'size': archive_path.stat().st_size if archive_path.exists() else None,
            'timestamp': datetime.now().isoformat(),
            'r2_key_latest': latest_key,
            'r2_key_backup': backup_key,
            'success': True
        }
        logger.info("✅ Light archive uploaded with rotation (latest + backup kept)")
        return info

    async def _create_light_backup_archive(self, backup_path: Path) -> Path:
        """创建轻量级备份压缩包 (仅结构化业务数据 JSON)。

        内容结构：
        - light_manifest.json : 元数据与版本
        - data/users.json
        - data/projects.json
        - data/ppt_templates.json
        - data/global_master_templates.json
        - data/config_files.json  (如果外部同步表存在并有内容 / 或本地 src/config & 根部配置文件)
        
        注意：不包含 uploads / research_reports / 脚本 / 整个数据库文件，以便用于快速“合并式”恢复或迁移。
        """
        import json, sqlite3, zipfile
        data_dir = backup_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # 读取本地 SQLite 数据库 (如果存在)。若未来需要支持直接查询外部DB，可扩展为根据配置选择来源。
        db_file = Path("./data/flowslide.db")
        if not db_file.exists():
            logger.warning("⚠️ 本地 flowslide.db 不存在，light 备份将只包含配置文件")
        else:
            try:
                conn = sqlite3.connect(str(db_file))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                def dump_table(query: str, out_name: str):
                    cur.execute(query)
                    rows = [dict(r) for r in cur.fetchall()]
                    with open(data_dir / out_name, 'w', encoding='utf-8') as f:
                        json.dump(rows, f, ensure_ascii=False, indent=2)
                    logger.info(f"🗂️ light backup wrote {out_name} ({len(rows)} rows)")

                # users (最小字段集合即可，保持列名一致以便未来合并，排除密码hash? -> 保留hash 才能无缝登陆)
                dump_table("SELECT id, username, email, is_active, is_admin, created_at, updated_at, last_login, password_hash FROM users", "users.json")
                # projects (核心内容: project_id 及关键字段，slides_html/slides_data 保留)
                dump_table("SELECT id, project_id, title, scenario, topic, requirements, status, owner_id, outline, slides_html, slides_data, confirmed_requirements, project_metadata, version, created_at, updated_at FROM projects", "projects.json")
                # ppt_templates
                dump_table("SELECT id, project_id, template_type, template_name, description, html_template, applicable_scenarios, style_config, usage_count, created_at, updated_at FROM ppt_templates", "ppt_templates.json")
                # global_master_templates
                dump_table("SELECT id, template_name, description, html_template, preview_image, style_config, tags, is_default, is_active, usage_count, created_by, created_at, updated_at FROM global_master_templates", "global_master_templates.json")
            except Exception as e:
                logger.warning(f"⚠️ 读取 SQLite 生成 light 数据失败: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        # 配置文件收集 (本地文件)。简化处理：打包 src/config 下的 json/yaml 以及根目录 *.toml / .env
        config_payload = {
            "root_files": {},
            "src_config": {},
        }
        try:
            # 根目录
            for name in [".env", "pyproject.toml", "uv.toml"]:
                p = Path(name)
                if p.exists():
                    try:
                        config_payload["root_files"][name] = p.read_text(encoding='utf-8', errors='ignore')
                    except Exception:
                        pass
            # src/config
            cfg_dir = Path("./src/config")
            if cfg_dir.exists():
                for fp in cfg_dir.rglob('*'):
                    if fp.is_file() and fp.suffix.lower() in ('.json', '.yaml', '.yml', '.toml'):
                        rel = str(fp.relative_to(cfg_dir))
                        try:
                            config_payload["src_config"][rel] = fp.read_text(encoding='utf-8', errors='ignore')
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"⚠️ 收集配置文件失败: {e}")

        with open(data_dir / 'config_files.json', 'w', encoding='utf-8') as f:
            json.dump(config_payload, f, ensure_ascii=False, indent=2)

        manifest = {
            "type": "light",
            "schema_version": 1,
            "generated_at": datetime.now().isoformat(),
            "description": "Lightweight selective dataset (users/projects/templates/config)",
            "tables": ["users", "projects", "ppt_templates", "global_master_templates"],
        }
        with open(backup_path / 'light_manifest.json', 'w', encoding='utf-8') as mf:
            json.dump(manifest, mf, ensure_ascii=False, indent=2)

        # 生成 zip: 只打包 light_manifest.json 与 data 目录
        archive_path = backup_path.with_suffix('.zip')
        import zipfile
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for path in backup_path.rglob('*'):
                if path.is_file():
                    zf.write(path, path.relative_to(backup_path.parent))
        shutil.rmtree(backup_path)
        logger.info(f"🗜️ Light backup compressed: {archive_path}")
        return archive_path

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
            p = Path(config_file)
            if not p.exists():
                continue
            try:
                if p.name == '.env':
                    # 直接明文复制 .env
                    shutil.copy2(p, backup_path / p.name)
                else:
                    shutil.copy2(p, backup_path / p.name)
            except Exception as ce:
                logger.warning(f"跳过配置文件 {config_file}: {ce}")

        # 若 .env 为空文件，额外生成一个运行时环境快照，避免用户误以为丢失
        try:
            env_file = backup_path / '.env'
            if (not env_file.exists()) or env_file.stat().st_size == 0:
                snapshot_path = backup_path / 'env_runtime_snapshot.txt'
                import os as _os
                lines = []
                for k,v in sorted(_os.environ.items()):
                    if any(s in k for s in ("KEY","SECRET","TOKEN","PASSWORD")):
                        # 只保留 key 名称，不暴露敏感值
                        lines.append(f"{k}=***redacted***")
                    else:
                        lines.append(f"{k}={v}")
                snapshot_path.write_text("\n".join(lines), encoding='utf-8')
                logger.info("🧾 Generated env_runtime_snapshot.txt (sanitized)")
        except Exception as se:
            logger.warning(f"生成环境快照失败: {se}")

        logger.info("⚙️ Config backup completed")

        # 附加：复制 src/config 下的配置（若存在）
        cfg_dir = Path("./src/config")
        if cfg_dir.exists() and cfg_dir.is_dir():
            dest = backup_path / "src_config"
            shutil.copytree(cfg_dir, dest, dirs_exist_ok=True)
            logger.info("📁 src/config included in config backup")

    # ================== 环境变量白名单 & 过滤工具 ==================
    # 保留空函数以防外部调用引用，直接返回原文本
    def _filter_env_content(self, text: str) -> str:
        return text

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
        """检查R2是否配置（每次调用都会刷新环境变量）"""
        self.refresh_r2_config()
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

            def extract_and_restore(backup_name_inner: str = backup_name):
                import zipfile
                import shutil
                from pathlib import Path

                try:
                    # 解压备份文件
                    logger.info(f"📦 Extracting backup: {backup_name_inner}")
                    with zipfile.ZipFile(str(backup_path), 'r') as zip_ref:
                        zip_ref.extractall(str(restore_temp_dir))

                    # 检测是否为轻量备份（存在 light_manifest.json）
                    light_manifest = list(restore_temp_dir.rglob("light_manifest.json"))
                    is_light = bool(light_manifest)
                    if is_light:
                        logger.info("🪶 Detected light backup manifest; executing merge restore logic (不会整体替换数据库文件)")
                    
                    db_files = list(restore_temp_dir.rglob("*.db")) if not is_light else []
                    if not is_light:
                        if not db_files:
                            raise Exception("备份文件中没有找到数据库文件")
                        db_file = db_files[0]
                        logger.info(f"🗄️ Found database file: {db_file.name} at {db_file}")
                    else:
                        db_file = None

                    current_db_path = Path("./data/flowslide.db")
                    if not is_light:
                        # 备份当前数据库
                        if current_db_path.exists():
                            backup_current = current_db_path.with_suffix('.db.backup')
                            shutil.copy2(str(current_db_path), str(backup_current))
                            logger.info(f"💾 Backed up current database to: {backup_current}")
                        # 恢复数据库文件
                        if db_file is not None:
                            shutil.copy2(str(db_file), str(current_db_path))
                            try:
                                db_display = getattr(db_file, 'name', str(db_file))
                            except Exception:
                                db_display = str(db_file)
                            logger.info(f"✅ Database restored from: {db_display}")
                    else:
                        # 轻量合并恢复
                        self._merge_light_backup_into_sqlite(restore_temp_dir, current_db_path)
                        logger.info("✅ Light backup merged into existing database")

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

                    # 新增: 恢复 .env （若备份中存在）
                    try:
                        env_candidates = list(restore_temp_dir.rglob('.env'))
                        if env_candidates:
                            env_src = env_candidates[0]
                            env_target = Path('.env')
                            if env_target.exists():
                                # 先做备份
                                backup_name = f".env.before_restore_{int(time.time())}"
                                shutil.copy2(str(env_target), backup_name)
                                logger.info(f"🛡️ Existing .env backed up as {backup_name}")
                            # 若备份中的 .env 含有 redacted 说明是白名单过滤版本 -> 合并策略
                            try:
                                new_text = env_src.read_text(encoding='utf-8', errors='ignore')
                            except Exception:
                                new_text = ''
                            force_full = os.getenv('FORCE_ENV_FULL_OVERWRITE', 'true').lower() == 'true'
                            if not force_full:
                                logger.info("🔧 FORCE_ENV_FULL_OVERWRITE=false: 启用安全合并模式 (.env)")
                            if ('***redacted***' in new_text and env_target.exists() and not force_full):
                                try:
                                    existing_text = env_target.read_text(encoding='utf-8', errors='ignore') if env_target.exists() else ''
                                except Exception:
                                    existing_text = ''
                                # 解析为 map
                                def parse(text:str):
                                    m = {}
                                    for line in text.splitlines():
                                        if line.strip() and not line.strip().startswith('#') and '=' in line:
                                            k,v = line.split('=',1)
                                            m[k.strip()] = v
                                    return m
                                existing_map = parse(existing_text)
                                incoming_map = parse(new_text)
                                wl = set(self._get_env_whitelist()) if hasattr(self, '_get_env_whitelist') else set()
                                merged = existing_map.copy()
                                for k,v in incoming_map.items():
                                    if k in wl:
                                        if v != '***redacted***':
                                            merged[k] = v
                                        # 如果是 redacted 保留原值（若不存在则不写入）
                                # 序列化，保持原有顺序（先白名单排序，后其余）
                                ordered_keys = [k for k in wl if k in merged] + [k for k in merged.keys() if k not in wl]
                                lines = [f"{k}={merged[k]}" for k in ordered_keys]
                                env_target.write_text('\n'.join(lines), encoding='utf-8')
                                logger.info("🔐 .env restored with merge (preserved local sensitive keys)")
                            else:
                                # 直接覆盖（完整未过滤版本）
                                shutil.copy2(str(env_src), str(env_target))
                                logger.info("🔐 .env restored from backup archive (direct copy)")
                    except Exception as env_e:
                        logger.warning(f"⚠️ .env restore skipped: {env_e}")

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

    # ================== 动态 .env 覆盖模式管理 ==================
    def get_env_mode(self) -> Dict[str, Any]:
        """返回当前 .env 恢复模式信息。"""
        force = os.getenv('FORCE_ENV_FULL_OVERWRITE', 'true').lower() == 'true'
        mode = 'full_overwrite' if force else 'merge_whitelist'
        wl = []
        try:
            wl = self._get_env_whitelist()  # type: ignore[attr-defined]
        except Exception:
            wl = []
        return {
            'force_full': force,
            'mode': mode,
            'whitelist_count': len(wl),
            'whitelist': wl,
        }

    def set_env_mode(self, force_full: bool) -> Dict[str, Any]:
        """设置并持久化 .env 恢复模式。

        持久化策略：更新当前进程环境变量 + 修改/追加 .env 中的 FORCE_ENV_FULL_OVERWRITE= 值。
        """
        os.environ['FORCE_ENV_FULL_OVERWRITE'] = 'true' if force_full else 'false'
        env_path = Path('.env')
        try:
            if env_path.exists():
                try:
                    lines = env_path.read_text(encoding='utf-8', errors='ignore').splitlines()
                except Exception:
                    lines = []
                found = False
                for i,l in enumerate(lines):
                    if l.strip().startswith('FORCE_ENV_FULL_OVERWRITE='):
                        lines[i] = f"FORCE_ENV_FULL_OVERWRITE={'true' if force_full else 'false'}"
                        found = True
                        break
                if not found:
                    lines.append(f"FORCE_ENV_FULL_OVERWRITE={'true' if force_full else 'false'}")
                env_path.write_text('\n'.join(lines)+('\n' if lines else ''), encoding='utf-8')
            else:
                env_path.write_text(f"FORCE_ENV_FULL_OVERWRITE={'true' if force_full else 'false'}\n", encoding='utf-8')
        except Exception as e:
            logger.warning(f"更新 .env 文件中的 FORCE_ENV_FULL_OVERWRITE 失败: {e}")
        return self.get_env_mode()

    def _merge_light_backup_into_sqlite(self, extracted_root: Path, sqlite_path: Path) -> None:
        """将轻量备份(JSON数据)合并写入现有SQLite数据库。

        策略：对于 users / projects / ppt_templates / global_master_templates
        - 若本地不存在 id -> 插入
        - 若存在 id -> 比较 updated_at 字段（无则使用 created_at），较新的覆盖指定字段
        - 不删除本地已有但备份缺失的记录（保持幂等增量）

        配置文件：写入到临时目录 / 不直接覆盖 .env (安全考虑)；pyproject.toml 等如果不存在则生成。
        """
        import json, sqlite3
        data_dir = extracted_root / 'data'
        if not data_dir.exists():
            logger.warning("light backup data dir missing; skip merge")
            return
        if not sqlite_path.exists():
            logger.warning("SQLite database not found; cannot merge light backup")
            return
        conn = sqlite3.connect(str(sqlite_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        def load_json(name: str):
            p = data_dir / name
            if not p.exists():
                return []
            try:
                return json.loads(p.read_text(encoding='utf-8'))
            except Exception as e:
                logger.warning(f"Failed loading {name}: {e}")
                return []

        try:
            users = load_json('users.json')
            projects = load_json('projects.json')
            ppt_templates = load_json('ppt_templates.json')
            global_templates = load_json('global_master_templates.json')
            # 读取配置文件聚合（包含 .env 内容）
            config_payload = None
            cfg_path = data_dir / 'config_files.json'
            if cfg_path.exists():
                try:
                    import json as _json
                    config_payload = _json.loads(cfg_path.read_text(encoding='utf-8'))
                except Exception as _e_cfg:
                    logger.warning(f"读取 config_files.json 失败: {_e_cfg}")

            def upsert(table: str, row: dict, key_field: str = 'id', timestamp_fields=("updated_at","created_at")):
                # 获取本地记录
                key = row.get(key_field)
                if key is None:
                    return
                cur.execute(f"SELECT * FROM {table} WHERE {key_field}=?", (key,))
                existing = cur.fetchone()
                def ts(r):
                    for f in timestamp_fields:
                        v = r.get(f) if isinstance(r, dict) else (r[f] if r and f in r.keys() else None)
                        if v is not None:
                            return float(v)
                    return 0.0
                if not existing:
                    # 插入
                    cols = list(row.keys())
                    placeholders = ','.join(['?']*len(cols))
                    cur.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", tuple(row[c] for c in cols))
                else:
                    local_ts = ts({k: existing[k] for k in existing.keys()})
                    remote_ts = ts(row)
                    if remote_ts > local_ts:
                        # 覆盖更新（不改变缺失字段）
                        cols = [c for c in row.keys() if c != key_field]
                        set_clause = ','.join([f"{c}=?" for c in cols])
                        cur.execute(f"UPDATE {table} SET {set_clause} WHERE {key_field}=?", tuple(row[c] for c in cols)+(key,))

            for u in users:
                upsert('users', u)
            for p in projects:
                upsert('projects', p)
            for t in ppt_templates:
                upsert('ppt_templates', t)
            for gt in global_templates:
                upsert('global_master_templates', gt)

            conn.commit()
            logger.info("Light backup data merged into SQLite (users/projects/templates)")
            # 合并恢复 .env（如果轻量包里包含 root_files -> .env）
            try:
                if config_payload and isinstance(config_payload, dict):
                    root_files = config_payload.get('root_files') or {}
                    env_content = root_files.get('.env')
                    if env_content is not None:
                        target = Path('.env')
                        if target.exists():
                            bak = f".env.before_light_merge_{int(time.time())}"
                            try:
                                target.write_text(target.read_text(encoding='utf-8'), encoding='utf-8')  # touch to ensure readable
                            except Exception:
                                pass
                            shutil.copy2(str(target), bak)
                            logger.info(f"🛡️ Existing .env backed up as {bak}")
                        try:
                            # 仅合并白名单变量，非白名单保持本地值（若远程为 ***redacted*** 直接忽略）
                            wl = set(self._get_env_whitelist()) if hasattr(self, '_get_env_whitelist') else set()
                            existing_map = {}
                            if target.exists():
                                for line in target.read_text(encoding='utf-8', errors='ignore').splitlines():
                                    if line.strip() and not line.strip().startswith('#') and '=' in line:
                                        k,v = line.split('=',1)
                                        existing_map[k.strip()] = v
                            merged = []
                            for line in env_content.splitlines():
                                if line.strip().startswith('#') or '=' not in line:
                                    merged.append(line)
                                    continue
                                k,v = line.split('=',1)
                                ks = k.strip()
                                if ks in wl:
                                    if v == '***redacted***':
                                        # 保持现有，若没有则跳过
                                        if ks in existing_map:
                                            merged.append(f"{ks}={existing_map[ks]}")
                                    else:
                                        merged.append(f"{ks}={v}")
                                else:
                                    # 非白名单保持原有
                                    if ks in existing_map:
                                        merged.append(f"{ks}={existing_map[ks]}")
                            # 添加剩余未写入的本地非白名单变量
                            for k,v in existing_map.items():
                                if not any(l.startswith(f"{k}=") for l in merged):
                                    merged.append(f"{k}={v}")
                            target.write_text('\n'.join(merged), encoding='utf-8')
                            logger.info("🔐 .env restored with whitelist merge (light)")
                        except Exception as w_e:
                            logger.warning(f"⚠️ 写入 .env (whitelist merge) 失败: {w_e}")
            except Exception as e_env_merge:
                logger.warning(f"⚠️ 轻量恢复 .env 处理异常: {e_env_merge}")
        except Exception as e:
            logger.error(f"Merge light backup failed: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

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

        # 仅考虑 zip 文件
        objects = [o for o in response['Contents'] if o.get('Key','').endswith('.zip')]
        if not objects:
            raise Exception("R2中没有可用的 .zip 备份文件")

        # 优先使用 light 轻量备份（文件名包含 _light_）
        light_objs = [o for o in objects if '_light_' in o.get('Key','')]
        selected_pool = light_objs if light_objs else objects
        if light_objs:
            logger.info(f"🪶 检测到 {len(light_objs)} 个 light 备份，优先选择其中最新的进行恢复")
        latest_backup = max(selected_pool, key=lambda x: x['LastModified'])
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
        prefix = prefix or 'backups/'
        import boto3
        s3 = boto3.client(
            's3',
            endpoint_url=os.getenv('R2_ENDPOINT'),
            aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
        )
        bucket = os.getenv('R2_BUCKET_NAME')
        if not bucket:
            return []
        paginator = s3.get_paginator('list_objects_v2')
        result = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []) or []:
                result.append({
                    'key': obj.get('Key'),
                    'size': obj.get('Size'),
                    'last_modified': obj.get('LastModified').isoformat() if obj.get('LastModified') else None
                })
        return result
    except Exception as e:
        logger.warning(f"列出 R2 文件失败: {e}")
        return []

async def fetch_latest_r2_users_snapshot() -> Optional[list]:
    """下载 R2 中最新的（优先 light）备份并返回 users.json 列表。

    返回：
        users 列表(dict) 或 None （未找到 / 失败）
    仅用于启动自动恢复用户。不会执行全量恢复，简单解析 users.json。
    """
    if not backup_service._is_r2_configured():
        return None
    try:
        files = await list_r2_files('backups/')
        if not files:
            return None
        # 过滤出 zip
        zips = [f for f in files if f.get('key','').endswith('.zip')]
        if not zips:
            return None
        # light 优先：按是否包含 'light' 标记优先排序，再按时间
        def rank(f):
            key = f.get('key','').lower()
            is_light = 'light' in key
            ts = f.get('last_modified') or ''
            return (0 if is_light else 1, 0 - len(ts), ts)
        # 先按 last_modified 已是降序，这里直接遍历挑第一个 light，否则第一个
        candidate = None
        for f in zips:
            if 'light' in f.get('key','').lower():
                candidate = f; break
        if candidate is None:
            candidate = zips[0]
        from botocore.config import Config
        config = Config(region_name='auto')
        s3_client = boto3.client(
            's3',
            aws_access_key_id=backup_service.r2_config['access_key'],
            aws_secret_access_key=backup_service.r2_config['secret_key'],
            endpoint_url=backup_service.r2_config['endpoint'],
            config=config
        )
        import tempfile, zipfile, json
        with tempfile.TemporaryDirectory() as td:
            local_zip = os.path.join(td, 'backup.zip')
            await asyncio.to_thread(s3_client.download_file, backup_service.r2_config['bucket'], candidate['key'], local_zip)
            with zipfile.ZipFile(local_zip,'r') as zf:
                # users.json 可能在 data/ 目录
                for name in zf.namelist():
                    if name.endswith('data/users.json') or name.endswith('/users.json') or name == 'users.json':
                        try:
                            with zf.open(name) as f:
                                data = f.read().decode('utf-8')
                                return json.loads(data)
                        except Exception as ue:
                            logger.warning(f"解析 users.json 失败: {ue}")
                            return None
        return None
    except Exception as e:
        logger.warning(f"fetch_latest_r2_users_snapshot failed: {e}")
        return None

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
