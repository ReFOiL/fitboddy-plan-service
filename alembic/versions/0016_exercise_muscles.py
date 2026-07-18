"""muscles dictionary and exercise muscle links

Revision ID: 0016_muscles
Revises: 0015_gen_policy
Create Date: 2026-07-19 00:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_muscles"
down_revision = "0015_gen_policy"
branch_labels = None
depends_on = None

# Keep in sync with application.muscle_catalog.MUSCLE_SEED
_MUSCLE_SEED: list[tuple[str, str, int, str, str]] = [
    ("neck", "Шея", 10, "front", "neck"),
    ("traps_upper", "Трапеции (верх)", 20, "front", "traps_upper"),
    ("chest_upper", "Грудь (верх)", 30, "front", "chest"),
    ("chest", "Грудь", 40, "front", "chest"),
    ("chest_lower", "Грудь (низ)", 50, "front", "chest"),
    ("serratus", "Передняя зубчатая", 60, "front", "serratus"),
    ("anterior_deltoid", "Передняя дельта", 70, "front", "shoulders_front"),
    ("lateral_deltoid", "Средняя дельта", 80, "front", "shoulders_front"),
    ("biceps", "Бицепс", 90, "front", "biceps"),
    ("brachialis", "Плечевая мышца", 100, "front", "biceps"),
    ("forearms", "Предплечья", 110, "front", "forearms"),
    ("abs", "Пресс", 120, "front", "abs"),
    ("obliques", "Косые мышцы живота", 130, "front", "obliques"),
    ("hip_flexors", "Сгибатели бедра", 140, "front", "hip_flexors"),
    ("quadriceps", "Квадрицепсы", 150, "front", "quadriceps"),
    ("adductors", "Приводящие бедра", 160, "front", "adductors"),
    ("tibialis", "Передняя большеберцовая", 170, "front", "tibialis"),
    ("traps", "Трапеции", 200, "back", "traps"),
    ("traps_mid", "Трапеции (середина)", 210, "back", "traps"),
    ("rear_deltoid", "Задняя дельта", 220, "back", "shoulders_back"),
    ("rhomboids", "Ромбовидные", 230, "back", "rhomboids"),
    ("lats", "Широчайшие", 240, "back", "lats"),
    ("teres", "Круглая мышца спины", 250, "back", "lats"),
    ("lower_back", "Разгибатели спины", 260, "back", "lower_back"),
    ("triceps", "Трицепс", 270, "back", "triceps"),
    ("glutes", "Ягодицы", 280, "back", "glutes"),
    ("hamstrings", "Бицепс бедра", 290, "back", "hamstrings"),
    ("calves", "Икры", 300, "back", "calves"),
    ("soleus", "Камбаловидная", 310, "back", "calves"),
    ("rotator_cuff", "Вращательная манжета", 320, "back", "shoulders_back"),
    ("pectoralis_minor", "Малая грудная", 330, "front", "chest"),
    ("core", "Кор (стабилизаторы)", 340, "front", "abs"),
    ("abductors", "Отводящие бедра", 350, "front", "quadriceps"),
    ("gastrocnemius", "Икроножная", 360, "back", "calves"),
    ("wrist_flexors", "Сгибатели запястья", 370, "front", "forearms"),
    ("wrist_extensors", "Разгибатели запястья", 380, "back", "forearms"),
    ("levator_scapulae", "Мышца, поднимающая лопатку", 390, "back", "traps"),
    ("infraspinatus", "Подостная", 400, "back", "shoulders_back"),
    ("subscapularis", "Подлопаточная", 410, "front", "shoulders_front"),
    ("brachioradialis", "Плечелучевая", 420, "front", "forearms"),
]


def upgrade() -> None:
    op.create_table(
        "muscles",
        sa.Column("slug", sa.String(length=64), primary_key=True),
        sa.Column("name_ru", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("body_view", sa.String(length=8), nullable=False),
        sa.Column("region_key", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "platform_exercise_muscles",
        sa.Column("platform_exercise_id", sa.String(length=36), nullable=False),
        sa.Column("muscle_slug", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["platform_exercise_id"], ["platform_exercises.row_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["muscle_slug"], ["muscles.slug"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("platform_exercise_id", "muscle_slug"),
    )
    op.create_index(
        "ix_platform_exercise_muscles_exercise",
        "platform_exercise_muscles",
        ["platform_exercise_id"],
    )
    op.create_table(
        "trainer_exercise_muscles",
        sa.Column("trainer_exercise_id", sa.String(length=36), nullable=False),
        sa.Column("muscle_slug", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["trainer_exercise_id"], ["trainer_exercises.row_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["muscle_slug"], ["muscles.slug"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trainer_exercise_id", "muscle_slug"),
    )
    op.create_index(
        "ix_trainer_exercise_muscles_exercise",
        "trainer_exercise_muscles",
        ["trainer_exercise_id"],
    )

    muscles = sa.table(
        "muscles",
        sa.column("slug", sa.String),
        sa.column("name_ru", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("body_view", sa.String),
        sa.column("region_key", sa.String),
    )
    op.bulk_insert(
        muscles,
        [
            {
                "slug": slug,
                "name_ru": name_ru,
                "sort_order": sort_order,
                "body_view": body_view,
                "region_key": region_key,
            }
            for slug, name_ru, sort_order, body_view, region_key in _MUSCLE_SEED
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_trainer_exercise_muscles_exercise", table_name="trainer_exercise_muscles")
    op.drop_table("trainer_exercise_muscles")
    op.drop_index("ix_platform_exercise_muscles_exercise", table_name="platform_exercise_muscles")
    op.drop_table("platform_exercise_muscles")
    op.drop_table("muscles")
