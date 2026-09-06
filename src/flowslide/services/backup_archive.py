"""Validated, transaction-consistent database snapshots and bounded ZIP extraction.

Backups copy password hashes unchanged. Restores never re-hash passwords, import
deployment credentials, switch database modes, or silently fall back to SQLite.
"""

import base64
import hashlib
import json
import stat
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path, PurePosixPath
from uuid import UUID

from sqlalchemy import MetaData, and_, delete, func, inspect, select, text
from sqlalchemy.sql.sqltypes import Date, DateTime, LargeBinary, Numeric, Time, Uuid

FORMAT = "flowslide-database-v1"
SNAPSHOT_NAME = "database_snapshot.json"
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_FILES = 10000
LIGHT_TABLES = frozenset(
    {
        "projects", "todo_boards", "todo_stages", "project_versions",
        "slide_data", "ppt_templates", "global_master_templates",
    }
)


def safe_extract(archive, destination: Path) -> None:
    """Validate every member before extracting anything (including Windows paths)."""
    destination = destination.resolve()
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_FILES or sum(m.file_size for m in members) > MAX_ARCHIVE_BYTES:
        raise ValueError("备份压缩包超过安全大小或文件数量限制")
    seen = set()
    for member in members:
        normalized = member.filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        mode = member.external_attr >> 16
        if (
            not normalized
            or path.is_absolute()
            or ".." in path.parts
            or any(":" in part for part in path.parts)
            or stat.S_ISLNK(mode)
            or member.flag_bits & 1
        ):
            raise ValueError("备份包含不安全的路径、链接或加密条目")
        target = (destination / Path(*path.parts)).resolve()
        if not target.is_relative_to(destination) or target == destination:
            raise ValueError("备份条目超出恢复目录")
        key = str(target).casefold()
        if key in seen:
            raise ValueError("备份包含重复或大小写冲突的路径")
        seen.add(key)
    archive.extractall(destination)


def _json_value(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    raise TypeError(f"Unsupported backup value: {type(value).__name__}")


def _restore_value(column, value):
    if value is None:
        return None
    kind = column.type
    if isinstance(kind, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(kind, Date):
        return date.fromisoformat(value)
    if isinstance(kind, Time):
        return time.fromisoformat(value)
    if isinstance(kind, LargeBinary):
        return base64.b64decode(value, validate=True)
    if isinstance(kind, Numeric):
        return Decimal(str(value))
    if isinstance(kind, Uuid) and kind.as_uuid:
        return UUID(value)
    return value


def write_snapshot(engine, destination: Path, *, light: bool = False) -> dict:
    """Snapshot only the active schema in one read transaction, including its users."""
    options = {"isolation_level": "REPEATABLE READ"} if engine.dialect.name in {"postgresql", "mysql"} else {}
    with engine.connect().execution_options(**options) as conn, conn.begin():
        if engine.dialect.name == "sqlite":
            # sqlite3's legacy transaction mode does not BEGIN for SELECT.
            conn.exec_driver_sql("BEGIN")
        elif engine.dialect.name == "postgresql":
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        schema = inspect(conn).default_schema_name
        metadata = MetaData()
        metadata.reflect(bind=conn, schema=schema, views=False)
        tables = [
            table for table in metadata.sorted_tables
            if table.schema == schema and not table.name.startswith("sqlite_")
            and (not light or table.name in LIGHT_TABLES)
        ]
        payload = {
            "format": FORMAT,
            "backend": engine.dialect.name,
            "schema": schema,
            "kind": "light" if light else "full",
            "created_at": datetime.now().astimezone().isoformat(),
            "tables": {},
            "owners": {},
        }
        for table in tables:
            payload["tables"][table.name] = {
                "columns": [column.name for column in table.columns],
                "rows": [list(row) for row in conn.execute(select(table))],
            }
        users = metadata.tables.get(f"{schema}.users")
        if light and users is not None and {"id", "username"} <= set(users.c.keys()):
            payload["owners"] = {
                str(row.id): row.username
                for row in conn.execute(select(users.c.id, users.c.username))
            }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, default=_json_value), encoding="utf-8"
    )
    if destination.stat().st_size > MAX_ARCHIVE_BYTES:
        destination.unlink()
        raise ValueError("数据库快照超过备份大小限制，请使用原生数据库备份工具")
    manifest = {
        "format": FORMAT,
        "backend": payload["backend"],
        "schema": payload["schema"],
        "kind": payload["kind"],
        "tables": list(payload["tables"]),
        "includes_accounts": "users" in payload["tables"],
        "restores_deployment_environment": False,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
    (destination.parent / "backup_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def read_snapshot(source: Path) -> dict:
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("数据库快照超过大小限制")
    data = source.read_bytes()
    manifest_path = source.parent / "backup_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != hashlib.sha256(data).hexdigest():
            raise ValueError("数据库快照校验和不匹配，未执行恢复")
    payload = json.loads(data)
    if payload.get("format") != FORMAT or payload.get("kind") not in {"full", "light"}:
        raise ValueError("不支持的数据库快照格式")
    if not isinstance(payload.get("tables"), dict) or not payload["tables"]:
        raise ValueError("备份中没有可恢复的数据表")
    if payload["kind"] == "light" and not set(payload["tables"]) <= LIGHT_TABLES:
        raise ValueError("轻量备份不允许包含账号、会话或系统配置表")
    return payload


def restore_snapshot(engine, source: Path, *, confirm_accounts: bool = False) -> dict:
    """Atomically restore the selected store; a full account restore requires consent."""
    payload = read_snapshot(source)
    restoring_accounts = "users" in payload["tables"]
    if restoring_accounts and not confirm_accounts:
        raise ValueError("完整备份包含账号密码；确认回滚账号后请传入 confirm_accounts=true")
    if payload["backend"] != engine.dialect.name:
        raise ValueError("备份数据库类型与当前权威数据库不同，禁止自动跨库覆盖")
    light = payload["kind"] == "light"
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '120s'")
        schema = inspect(conn).default_schema_name
        if payload.get("schema") != schema:
            raise ValueError("备份 schema 与当前数据库 schema 不一致")
        metadata = MetaData()
        metadata.reflect(bind=conn, schema=schema, views=False)
        available = {table.name: table for table in metadata.tables.values() if table.schema == schema}
        missing = set(payload["tables"]) - available.keys()
        if missing:
            raise ValueError("目标数据库缺少备份中的表，请先完成数据库迁移")
        owners = {}
        if light and payload.get("owners"):
            users = available.get("users")
            if users is None:
                raise ValueError("目标数据库缺少用户表，无法核对项目归属")
            owners = dict(conn.execute(select(users.c.username, users.c.id)).all())
        prepared = {}
        for name, data in payload["tables"].items():
            table = available[name]
            columns, rows = data.get("columns"), data.get("rows")
            if (
                not isinstance(columns, list) or len(set(columns)) != len(columns)
                or not set(columns) <= set(table.c.keys()) or not isinstance(rows, list)
            ):
                raise ValueError("快照的表字段格式无效")
            prepared[name] = []
            for values in rows:
                if not isinstance(values, list) or len(values) != len(columns):
                    raise ValueError("快照的数据行格式无效")
                row = {key: _restore_value(table.c[key], value) for key, value in zip(columns, values)}
                if light:
                    for column in table.columns:
                        if column.name not in row or row[column.name] is None:
                            continue
                        if any(fk.column.table.name == "users" for fk in column.foreign_keys):
                            username = payload.get("owners", {}).get(str(row[column.name]))
                            if username not in owners:
                                raise ValueError("轻量备份的项目所有者不存在；请先创建对应账号或选择完整恢复")
                            row[column.name] = owners[username]
                prepared[name].append(row)
        ordered = [
            table for table in metadata.sorted_tables
            if table.schema == schema and table.name in prepared
        ]
        if restoring_accounts and "user_sessions" in available:
            # Never resurrect cookies stored in an old backup.
            conn.execute(delete(available["user_sessions"]))
            prepared["user_sessions"] = []
        if not light:
            for table in reversed(ordered):
                conn.execute(delete(table))
        for table in ordered:
            for row in prepared[table.name]:
                if not light:
                    conn.execute(table.insert().values(**row))
                    continue
                keys = list(table.primary_key.columns)
                if not keys or any(column.name not in row for column in keys):
                    raise ValueError("轻量备份缺少主键，无法安全合并")
                condition = and_(*(column == row[column.name] for column in keys))
                existing = conn.execute(select(table).where(condition)).mappings().first()
                if existing:
                    for identity in ("project_id", "owner_id", "template_name"):
                        if identity in row and existing.get(identity) != row[identity]:
                            raise ValueError("轻量恢复发现记录归属或 ID 冲突，已回滚")
                    conn.execute(table.update().where(condition).values(**row))
                else:
                    conn.execute(table.insert().values(**row))
        if engine.dialect.name == "postgresql":
            # COPY/explicit IDs do not advance PostgreSQL sequences.
            quote = conn.dialect.identifier_preparer.quote
            for table in ordered:
                for column in table.primary_key.columns:
                    if column.autoincrement is False or "INT" not in str(column.type).upper():
                        continue
                    sequence = conn.execute(
                        text("SELECT pg_get_serial_sequence(:table, :column)"),
                        {"table": f"{quote(schema)}.{quote(table.name)}", "column": column.name},
                    ).scalar()
                    if sequence:
                        maximum = conn.execute(select(func.max(column))).scalar()
                        conn.execute(
                            text("SELECT setval(CAST(:sequence AS regclass), :value, :called)"),
                            {"sequence": sequence, "value": max(maximum or 1, 1), "called": maximum is not None},
                        )
    return {"tables_restored": len(ordered), "accounts_restored": restoring_accounts, "sessions_invalidated": restoring_accounts}
