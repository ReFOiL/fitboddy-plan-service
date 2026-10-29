"""link trainer exercises to the platform catalog for soft sync

Revision ID: 0022_trainer_sync_link
Revises: 0021_plan_notes_times
Create Date: 2026-10-29 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_trainer_sync_link"
down_revision = "0021_plan_notes_times"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(sa.Column("source_platform_exercise_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("synced_video_key", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("synced_start_image_key", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("synced_end_image_key", sa.String(length=500), nullable=True))
        batch_op.create_foreign_key(
            "fk_trainer_exercises_source_platform",
            "platform_exercises",
            ["source_platform_exercise_id"],
            ["row_id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "uq_trainer_exercises_source_platform",
        "trainer_exercises",
        ["trainer_user_id", "source_platform_exercise_id"],
        unique=True,
        sqlite_where=sa.text("source_platform_exercise_id IS NOT NULL"),
        postgresql_where=sa.text("source_platform_exercise_id IS NOT NULL"),
    )
    _backfill_links()


def downgrade() -> None:
    op.drop_index("uq_trainer_exercises_source_platform", table_name="trainer_exercises")
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_constraint("fk_trainer_exercises_source_platform", type_="foreignkey")
        batch_op.drop_column("synced_end_image_key")
        batch_op.drop_column("synced_start_image_key")
        batch_op.drop_column("synced_video_key")
        batch_op.drop_column("source_platform_exercise_id")


def _match_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def _synced_key(trainer_value: str | None, platform_value: str | None) -> str | None:
    # A trainer file already on the row is treated as the current platform copy.
    # A missing trainer file with platform media stays unsynced so preview can offer it.
    if trainer_value or not platform_value:
        return platform_value
    return None


def _backfill_links() -> None:
    bind = op.get_bind()
    platform = sa.table(
        "platform_exercises",
        sa.column("row_id", sa.String),
        sa.column("exercise_name", sa.String),
        sa.column("video_url", sa.String),
        sa.column("start_image_url", sa.String),
        sa.column("end_image_url", sa.String),
    )
    trainer = sa.table(
        "trainer_exercises",
        sa.column("row_id", sa.String),
        sa.column("trainer_user_id", sa.String),
        sa.column("exercise_name", sa.String),
        sa.column("video_url", sa.String),
        sa.column("start_image_url", sa.String),
        sa.column("end_image_url", sa.String),
        sa.column("source_platform_exercise_id", sa.String),
        sa.column("synced_video_key", sa.String),
        sa.column("synced_start_image_key", sa.String),
        sa.column("synced_end_image_key", sa.String),
    )
    platform_rows = list(bind.execute(sa.select(platform)).mappings())
    trainer_rows = list(bind.execute(sa.select(trainer)).mappings())
    by_trainer: dict[str, list] = {}
    for row in trainer_rows:
        if row["source_platform_exercise_id"]:
            continue
        by_trainer.setdefault(row["trainer_user_id"], []).append(row)

    platform_by_name: dict[str, list] = {}
    for row in platform_rows:
        platform_by_name.setdefault(_match_name(row["exercise_name"]), []).append(row)

    for group in by_trainer.values():
        trainer_by_name: dict[str, list] = {}
        for row in group:
            trainer_by_name.setdefault(_match_name(row["exercise_name"]), []).append(row)
        for name, trainers in trainer_by_name.items():
            platforms = platform_by_name.get(name, [])
            if len(trainers) != 1 or len(platforms) != 1:
                continue
            platform_row = platforms[0]
            trainer_row = trainers[0]
            bind.execute(
                sa.update(trainer)
                .where(trainer.c.row_id == trainer_row["row_id"])
                .values(
                    source_platform_exercise_id=platform_row["row_id"],
                    synced_video_key=_synced_key(trainer_row["video_url"], platform_row["video_url"]),
                    synced_start_image_key=_synced_key(
                        trainer_row["start_image_url"],
                        platform_row["start_image_url"],
                    ),
                    synced_end_image_key=_synced_key(trainer_row["end_image_url"], platform_row["end_image_url"]),
                )
            )
