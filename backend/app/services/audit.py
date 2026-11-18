from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    entity_type: str,
    entity_id: str | int,
    action: str,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            detail_json=json.dumps(detail or {}, ensure_ascii=False),
        )
    )
