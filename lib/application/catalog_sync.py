"""Soft sync of the platform exercise catalog into a trainer catalog.

Match rule
----------
Clone assigns a new ``trainer_exercises.row_id`` and copies media into the
trainer prefix, so the two sides never share an id or an object key.

1. Prefer ``trainer_exercises.source_platform_exercise_id`` (set on clone and
   on apply). A later rename on either side keeps the link.
2. Otherwise, if exactly one unlinked trainer row and exactly one not-yet-linked
   platform row share a normalized name (trimmed, inner whitespace collapsed,
   casefolded), treat them as the same exercise. Ambiguous names are not linked.

Media diff
----------
A slot (``video_url``, ``start_image_url``, ``end_image_url``) is a pending
update when the platform object key is present and differs from the key recorded
at the last copy (``synced_*_key``). Comparing the trainer's current key would
flag every clone, because the copy lives under a different key. A null platform
key does not clear trainer media. Name, description, dosage, and muscles are
not part of the update bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MediaField = Literal["video_url", "start_image_url", "end_image_url"]

MEDIA_SLOTS: tuple[tuple[MediaField, str, str], ...] = (
    ("video_url", "synced_video_key", "video"),
    ("start_image_url", "synced_start_image_key", "start"),
    ("end_image_url", "synced_end_image_key", "end"),
)


@dataclass(frozen=True)
class SyncPlatformRow:
    row_id: str
    exercise_name: str
    description: str | None
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    video_key: str | None
    start_image_key: str | None
    end_image_key: str | None


@dataclass(frozen=True)
class SyncTrainerRow:
    row_id: str
    exercise_name: str
    description: str | None
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    video_key: str | None
    start_image_key: str | None
    end_image_key: str | None
    is_active: bool
    source_platform_exercise_id: str | None
    synced_video_key: str | None
    synced_start_image_key: str | None
    synced_end_image_key: str | None


@dataclass(frozen=True)
class CatalogSyncCard:
    exercise_name: str
    description: str | None
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    video_url: str | None
    start_image_url: str | None
    end_image_url: str | None


@dataclass(frozen=True)
class CatalogSyncAdd:
    platform_exercise_id: str
    exercise_name: str
    description: str | None
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    video_url: str | None
    start_image_url: str | None
    end_image_url: str | None


@dataclass(frozen=True)
class CatalogSyncUpdate:
    platform_exercise_id: str
    trainer_exercise_id: str
    changed_fields: tuple[MediaField, ...]
    trainer: CatalogSyncCard
    platform: CatalogSyncCard


@dataclass(frozen=True)
class CatalogLink:
    platform_exercise_id: str
    trainer_exercise_id: str
    trainer_is_active: bool
    changed_fields: tuple[MediaField, ...]


@dataclass(frozen=True)
class CatalogSyncPlan:
    add: tuple[CatalogSyncAdd, ...]
    update: tuple[CatalogSyncUpdate, ...]
    unchanged_count: int
    links: tuple[CatalogLink, ...]

    @property
    def new_count(self) -> int:
        return len(self.add)

    @property
    def media_update_count(self) -> int:
        return len(self.update)


@dataclass(frozen=True)
class CatalogSyncApplyResult:
    added_ids: tuple[str, ...]
    updated_ids: tuple[str, ...]
    replaced_media_keys: tuple[str, ...]


def normalize_match_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def changed_media_fields(trainer: SyncTrainerRow, platform: SyncPlatformRow) -> tuple[MediaField, ...]:
    synced_by_field = {
        "video_url": trainer.synced_video_key,
        "start_image_url": trainer.synced_start_image_key,
        "end_image_url": trainer.synced_end_image_key,
    }
    platform_by_field = {
        "video_url": platform.video_key,
        "start_image_url": platform.start_image_key,
        "end_image_url": platform.end_image_key,
    }
    changed: list[MediaField] = []
    for field, _synced_column, _slot in MEDIA_SLOTS:
        platform_key = platform_by_field[field]
        if platform_key is not None and platform_key != synced_by_field[field]:
            changed.append(field)
    return tuple(changed)


def match_catalog(
    platform_rows: list[SyncPlatformRow],
    trainer_rows: list[SyncTrainerRow],
) -> CatalogSyncPlan:
    trainer_by_source: dict[str, SyncTrainerRow] = {}
    unlinked: list[SyncTrainerRow] = []
    for row in trainer_rows:
        source_id = row.source_platform_exercise_id
        if not source_id:
            unlinked.append(row)
            continue
        current = trainer_by_source.get(source_id)
        if current is None or (not current.is_active and row.is_active):
            trainer_by_source[source_id] = row

    platform_by_name: dict[str, list[SyncPlatformRow]] = {}
    for row in platform_rows:
        if row.row_id in trainer_by_source:
            continue
        platform_by_name.setdefault(normalize_match_name(row.exercise_name), []).append(row)

    trainer_by_name: dict[str, list[SyncTrainerRow]] = {}
    for row in unlinked:
        trainer_by_name.setdefault(normalize_match_name(row.exercise_name), []).append(row)

    name_matches: dict[str, SyncTrainerRow] = {}
    for name, platforms in platform_by_name.items():
        trainers = trainer_by_name.get(name, [])
        if len(platforms) == 1 and len(trainers) == 1:
            name_matches[platforms[0].row_id] = trainers[0]

    adds: list[CatalogSyncAdd] = []
    updates: list[CatalogSyncUpdate] = []
    links: list[CatalogLink] = []
    unchanged = 0
    ordered = sorted(platform_rows, key=lambda row: (normalize_match_name(row.exercise_name), row.row_id))
    for platform in ordered:
        trainer = trainer_by_source.get(platform.row_id) or name_matches.get(platform.row_id)
        if trainer is None:
            adds.append(
                CatalogSyncAdd(
                    platform_exercise_id=platform.row_id,
                    exercise_name=platform.exercise_name,
                    description=platform.description,
                    primary_muscles=platform.primary_muscles,
                    secondary_muscles=platform.secondary_muscles,
                    video_url=platform.video_key,
                    start_image_url=platform.start_image_key,
                    end_image_url=platform.end_image_key,
                )
            )
            continue
        changed = changed_media_fields(trainer, platform) if trainer.is_active else ()
        links.append(
            CatalogLink(
                platform_exercise_id=platform.row_id,
                trainer_exercise_id=trainer.row_id,
                trainer_is_active=trainer.is_active,
                changed_fields=changed,
            )
        )
        if trainer.is_active and changed:
            updates.append(
                CatalogSyncUpdate(
                    platform_exercise_id=platform.row_id,
                    trainer_exercise_id=trainer.row_id,
                    changed_fields=changed,
                    trainer=_card_from_trainer(trainer),
                    platform=_card_from_platform(platform),
                )
            )
        else:
            unchanged += 1

    return CatalogSyncPlan(
        add=tuple(adds),
        update=tuple(updates),
        unchanged_count=unchanged,
        links=tuple(links),
    )


def _card_from_platform(row: SyncPlatformRow) -> CatalogSyncCard:
    return CatalogSyncCard(
        exercise_name=row.exercise_name,
        description=row.description,
        primary_muscles=row.primary_muscles,
        secondary_muscles=row.secondary_muscles,
        video_url=row.video_key,
        start_image_url=row.start_image_key,
        end_image_url=row.end_image_key,
    )


def _card_from_trainer(row: SyncTrainerRow) -> CatalogSyncCard:
    return CatalogSyncCard(
        exercise_name=row.exercise_name,
        description=row.description,
        primary_muscles=row.primary_muscles,
        secondary_muscles=row.secondary_muscles,
        video_url=row.video_key,
        start_image_url=row.start_image_key,
        end_image_url=row.end_image_key,
    )
