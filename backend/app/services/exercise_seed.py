from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise

SYSTEM_EXERCISES: list[tuple[str, str, str]] = [
    ("杠铃卧推", "STRENGTH", "胸部力量训练"),
    ("哑铃飞鸟", "STRENGTH", "胸部孤立训练"),
    ("引体向上", "STRENGTH", "背部自重训练"),
    ("杠铃划船", "STRENGTH", "背部力量训练"),
    ("深蹲", "STRENGTH", "下肢复合训练"),
    ("硬拉", "STRENGTH", "后链复合训练"),
    ("肩上推举", "STRENGTH", "肩部力量训练"),
    ("二头弯举", "STRENGTH", "手臂训练"),
    ("三头下压", "STRENGTH", "手臂训练"),
    ("平板支撑", "STRENGTH", "核心稳定"),
    ("跑步", "CARDIO", "有氧耐力"),
    ("骑行", "CARDIO", "有氧耐力"),
    ("跳绳", "CARDIO", "有氧间歇"),
    ("划船机", "CARDIO", "全身有氧"),
    ("游泳", "CARDIO", "低冲击有氧"),
    ("静态拉伸", "STRETCH", "放松拉伸"),
    ("动态热身拉伸", "STRETCH", "训练前激活"),
    ("泡沫轴放松", "STRETCH", "筋膜放松"),
]


def seed_system_exercises(db: Session) -> int:
    """Idempotent seed of system preset exercises. Returns inserted count."""
    existing = {
        name
        for (name,) in db.execute(
            select(Exercise.name).where(Exercise.owner_user_id.is_(None))
        ).all()
    }
    inserted = 0
    for name, category, description in SYSTEM_EXERCISES:
        if name in existing:
            continue
        db.add(
            Exercise(
                owner_user_id=None,
                name=name,
                category=category,
                description=description,
                is_active=True,
            )
        )
        inserted += 1
    return inserted
