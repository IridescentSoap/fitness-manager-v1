from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.core.timeutil import app_tz, iso_z
from app.models import SystemKv
from app.services.audit import write_audit

logger = logging.getLogger(__name__)
BACKUP_NAME = re.compile(r"^fitness-\d{8}-\d{6}(?:-\d+)?\.db$")
CONFIRM_PHRASE = "RESTORE"


def _dbapi_connection(db: Session):
    sa_conn = db.connection()
    raw = sa_conn.connection
    driver = getattr(raw, "driver_connection", None)
    return driver or raw


def _sqlite_backup(db: Session, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    source = _dbapi_connection(db)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()


def _integrity(path: Path) -> str:
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else "fail"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_version(db: Session) -> str:
    try:
        value = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        return "unknown"
    return str(value or "unknown")


def _write_meta(db: Session, dest: Path) -> dict:
    settings = get_settings()
    meta = {
        "filename": dest.name,
        "created_at": iso_z(utcnow()),
        "sha256": _sha256(dest),
        "integrity_check": _integrity(dest),
        "schema_version": _schema_version(db),
        "app_version": settings.app_version,
    }
    dest.with_suffix(".db.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def _stamp() -> str:
    return datetime.now(app_tz()).strftime("%Y%m%d-%H%M%S")


def prune_backups() -> None:
    settings = get_settings()
    cutoff = datetime.now(app_tz()) - timedelta(days=settings.backup_retention_days)
    if not settings.backup_dir.exists():
        return
    for path in settings.backup_dir.glob("fitness-*.db"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=app_tz())
        if modified < cutoff:
            path.unlink(missing_ok=True)
            path.with_suffix(".db.json").unlink(missing_ok=True)


def _unique_backup_path() -> Path:
    settings = get_settings()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    base = _stamp()
    candidate = settings.backup_dir / f"fitness-{base}.db"
    counter = 2
    while candidate.exists():
        candidate = settings.backup_dir / f"fitness-{base}-{counter}.db"
        counter += 1
    return candidate


def create_backup(db: Session, *, actor_user_id: int | None, reason: str = "manual") -> dict:
    settings = get_settings()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    dest = _unique_backup_path()
    _sqlite_backup(db, dest)
    integrity = _integrity(dest)
    if integrity != "ok":
        dest.unlink(missing_ok=True)
        raise AppError(500, "BACKUP_FAILED", "备份完整性检查失败")
    meta = _write_meta(db, dest)
    meta["reason"] = reason
    db.merge(
        SystemKv(key="last_backup_at", value_json=json.dumps(meta["created_at"]), updated_at=utcnow())
    )
    write_audit(
        db,
        actor_user_id=actor_user_id,
        entity_type="backup",
        entity_id=dest.name,
        action="BACKUP",
        detail={"reason": reason},
    )
    db.commit()
    prune_backups()
    return meta


def list_backups() -> dict:
    settings = get_settings()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(settings.backup_dir.glob("fitness-*.db"), reverse=True):
        meta_path = path.with_suffix(".db.json")
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        items.append(
            {
                "id": path.name,
                "filename": path.name,
                "created_at": meta.get("created_at"),
                "sha256": meta.get("sha256"),
                "integrity_check": meta.get("integrity_check"),
                "schema_version": meta.get("schema_version"),
                "app_version": meta.get("app_version"),
                "size_bytes": path.stat().st_size,
            }
        )
    return {"items": items}


def last_backup_at(db: Session) -> str | None:
    row = db.get(SystemKv, "last_backup_at")
    if row is not None:
        try:
            return json.loads(row.value_json)
        except json.JSONDecodeError:
            return None
    items = list_backups()["items"]
    if items:
        return items[0].get("created_at")
    return None


def _resolve_backup(backup_id: str) -> tuple[Path, dict]:
    if not BACKUP_NAME.match(backup_id):
        raise AppError(404, "NOT_FOUND", "备份不存在")
    path = get_settings().backup_dir / backup_id
    if not path.is_file():
        raise AppError(404, "NOT_FOUND", "备份不存在")
    meta_path = path.with_suffix(".db.json")
    if not meta_path.is_file():
        raise AppError(422, "VALIDATION_ERROR", "备份缺少元数据")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    digest = _sha256(path)
    if digest != meta.get("sha256"):
        raise AppError(422, "VALIDATION_ERROR", "备份校验和不匹配")
    if _integrity(path) != "ok":
        raise AppError(422, "VALIDATION_ERROR", "备份完整性检查失败")
    return path, meta


def reopen_database() -> None:
    from app.core import database as database_module
    from sqlalchemy.orm import sessionmaker

    database_module.engine.dispose()
    new_engine = database_module._create_engine()
    database_module.engine = new_engine
    database_module.SessionLocal = sessionmaker(
        bind=new_engine, autoflush=False, autocommit=False, future=True
    )


def _release_locks() -> None:
    import gc

    from app.core import database as database_module

    try:
        with database_module.engine.connect() as connection:
            connection.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            connection.commit()
    except Exception:
        logger.exception("checkpoint before file swap failed")
    database_module.engine.dispose()
    gc.collect()


def _move_aside(path: Path, stamp: str) -> None:
    import gc
    import time

    if not path.exists():
        return
    target = path.with_name(f"{path.name}.old-{stamp}")
    for _ in range(20):
        try:
            path.replace(target)
            return
        except PermissionError:
            gc.collect()
            time.sleep(0.05)
    raise AppError(500, "RESTORE_FAILED", f"数据库文件仍被占用: {path.name}")


def _swap_database(backup_file: Path) -> None:
    settings = get_settings()
    db_file = (settings.app_data_dir / "fitness.db").resolve()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    _release_locks()
    stamp = _stamp()
    # Move the live DB and WAL/SHM completely aside so Windows cannot keep serving them.
    for path in (db_file, Path(str(db_file) + "-wal"), Path(str(db_file) + "-shm")):
        _move_aside(path, stamp)
    shutil.copy2(backup_file, db_file)
    reopen_database()


def restore_backup(db: Session, *, actor_user_id: int, backup_id: str, confirm: str) -> dict:
    if confirm != CONFIRM_PHRASE:
        raise AppError(422, "VALIDATION_ERROR", "恢复确认短语不正确")
    source, meta = _resolve_backup(backup_id)
    settings = get_settings()
    pre_standard = settings.backup_dir / f"pre-restore-{_stamp()}.db"
    if pre_standard.resolve() == source.resolve():
        pre_standard = settings.backup_dir / f"pre-restore-{_stamp()}-2.db"
    _sqlite_backup(db, pre_standard)
    if _integrity(pre_standard) != "ok":
        pre_standard.unlink(missing_ok=True)
        raise AppError(500, "BACKUP_FAILED", "恢复前备份失败")
    _write_meta(db, pre_standard)
    db.commit()
    db.close()
    try:
        _swap_database(source)
    except Exception as exc:
        logger.exception("restore failed")
        try:
            _swap_database(pre_standard)
        except Exception:
            logger.exception("rollback restore failed")
        raise AppError(500, "RESTORE_FAILED", "恢复失败，已尝试回滚") from exc

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        write_audit(
            session,
            actor_user_id=actor_user_id,
            entity_type="backup",
            entity_id=backup_id,
            action="RESTORE",
            detail={"pre_restore": pre_standard.name, "schema_version": meta.get("schema_version")},
        )
        session.commit()
    return {"restored": backup_id, "pre_restore": pre_standard.name}


def maybe_daily_backup(db: Session) -> None:
    settings = get_settings()
    if settings.app_env == "development":
        return
    today = datetime.now(app_tz()).date().isoformat()
    row = db.get(SystemKv, "last_auto_backup_date")
    if row is not None and row.value_json.strip('"') == today:
        return
    try:
        create_backup(db, actor_user_id=None, reason="auto")
        db.merge(SystemKv(key="last_auto_backup_date", value_json=json.dumps(today), updated_at=utcnow()))
        db.commit()
    except Exception:
        logger.exception("daily backup skipped")
        db.rollback()
