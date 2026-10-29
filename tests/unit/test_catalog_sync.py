from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from application.catalog_sync import (
    SyncPlatformRow,
    SyncTrainerRow,
    match_catalog,
    normalize_match_name,
)


def _platform(
    row_id: str,
    name: str,
    *,
    description: str | None = None,
    video: str | None = None,
    start: str | None = None,
    end: str | None = None,
    primary: tuple[str, ...] = (),
) -> SyncPlatformRow:
    return SyncPlatformRow(
        row_id=row_id,
        exercise_name=name,
        description=description,
        primary_muscles=primary,
        secondary_muscles=(),
        video_key=video,
        start_image_key=start,
        end_image_key=end,
    )


def _trainer(
    row_id: str,
    name: str,
    *,
    source: str | None = None,
    description: str | None = None,
    video: str | None = None,
    start: str | None = None,
    end: str | None = None,
    synced_video: str | None = None,
    synced_start: str | None = None,
    synced_end: str | None = None,
    is_active: bool = True,
    primary: tuple[str, ...] = (),
) -> SyncTrainerRow:
    return SyncTrainerRow(
        row_id=row_id,
        exercise_name=name,
        description=description,
        primary_muscles=primary,
        secondary_muscles=(),
        video_key=video,
        start_image_key=start,
        end_image_key=end,
        is_active=is_active,
        source_platform_exercise_id=source,
        synced_video_key=synced_video,
        synced_start_image_key=synced_start,
        synced_end_image_key=synced_end,
    )


def test_new_platform_exercise_is_add_and_identical_copy_is_unchanged() -> None:
    platform = [
        _platform("p-new", "New Move", start="photos/platform/p-new/start/a.jpg", primary=("chest",)),
        _platform("p-same", "Press", start="photos/platform/p-same/start/a.jpg", description="system"),
    ]
    trainer = [
        _trainer(
            "t-same",
            "Press",
            source="p-same",
            description="trainer cue",
            start="photos/trainer/t-same/start/copy.jpg",
            synced_start="photos/platform/p-same/start/a.jpg",
            primary=("chest",),
        )
    ]
    plan = match_catalog(platform, trainer)
    assert [item.platform_exercise_id for item in plan.add] == ["p-new"]
    assert plan.add[0].primary_muscles == ("chest",)
    assert plan.add[0].start_image_url == "photos/platform/p-new/start/a.jpg"
    assert plan.update == ()
    assert plan.unchanged_count == 1
    assert plan.new_count + plan.media_update_count + plan.unchanged_count == len(platform)


def test_media_diff_uses_last_synced_key_not_the_trainer_copy() -> None:
    platform = [
        _platform(
            "p1",
            "Squat",
            start="photos/platform/p1/start/b.jpg",
            end="photos/platform/p1/end/b.jpg",
            video="videos/platform/p1/b.mp4",
            description="renamed on platform",
        )
    ]
    trainer = [
        _trainer(
            "t1",
            "My Squat",
            source="p1",
            description="keep me",
            start="photos/trainer/t1/start/copy.jpg",
            synced_start="photos/platform/p1/start/a.jpg",
            synced_end=None,
            synced_video="videos/platform/p1/a.mp4",
        )
    ]
    plan = match_catalog(platform, trainer)
    assert plan.add == ()
    assert len(plan.update) == 1
    item = plan.update[0]
    assert item.changed_fields == ("video_url", "start_image_url", "end_image_url")
    assert item.trainer.exercise_name == "My Squat"
    assert item.trainer.description == "keep me"
    assert item.platform.exercise_name == "Squat"
    assert item.platform.start_image_url == "photos/platform/p1/start/b.jpg"
    assert plan.unchanged_count == 0


def test_description_only_change_stays_unchanged() -> None:
    platform = [_platform("p1", "Squat", description="new text", start="photos/platform/p1/a.jpg")]
    trainer = [
        _trainer(
            "t1",
            "Squat",
            source="p1",
            description="old text",
            start="photos/trainer/t1/copy.jpg",
            synced_start="photos/platform/p1/a.jpg",
        )
    ]
    plan = match_catalog(platform, trainer)
    assert plan.update == ()
    assert plan.add == ()
    assert plan.unchanged_count == 1


def test_null_platform_media_does_not_count_as_an_update() -> None:
    platform = [_platform("p1", "Squat")]
    trainer = [
        _trainer(
            "t1",
            "Squat",
            source="p1",
            start="photos/trainer/t1/own.jpg",
            synced_start="photos/platform/p1/old.jpg",
        )
    ]
    plan = match_catalog(platform, trainer)
    assert plan.update == ()
    assert plan.unchanged_count == 1


def test_rename_keeps_source_link_and_name_fallback_is_unambiguous_only() -> None:
    assert normalize_match_name("  Приседания   со штангой ") == "приседания со штангой"
    platform = [
        _platform("p1", "Приседания со штангой"),
        _platform("p2", "Тяга"),
        _platform("p3", "Жим"),
    ]
    trainer = [
        _trainer("t1", "Мои приседания", source="p1"),
        _trainer("t-legacy", "  тяга "),
        _trainer("t-custom-a", "Жим"),
        _trainer("t-custom-b", "жим"),
    ]
    plan = match_catalog(platform, trainer)
    assert [item.platform_exercise_id for item in plan.add] == ["p3"]
    linked = {link.platform_exercise_id: link.trainer_exercise_id for link in plan.links}
    assert linked == {"p1": "t1", "p2": "t-legacy"}
    assert plan.unchanged_count == 2


def test_sync_link_migration_backfills_unique_names_and_downgrades(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "sync-link.db"
    url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0021_plan_notes_times")

    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO platform_exercises (row_id, exercise_name, start_image_url, video_url) "
                "VALUES (:row_id, :name, :start, :video)"
            ),
            [
                {
                    "row_id": "plat-squat",
                    "name": "Приседания со штангой",
                    "start": "photos/platform/plat-squat/start/a.jpg",
                    "video": None,
                },
                {
                    "row_id": "plat-press",
                    "name": "Жим",
                    "start": "photos/platform/plat-press/start/a.jpg",
                    "video": "videos/platform/plat-press/a.mp4",
                },
                {
                    "row_id": "plat-row-a",
                    "name": "Тяга",
                    "start": None,
                    "video": None,
                },
                {
                    "row_id": "plat-row-b",
                    "name": "тяга",
                    "start": None,
                    "video": None,
                },
            ],
        )
        connection.execute(
            text(
                "INSERT INTO trainer_exercises (row_id, trainer_user_id, exercise_name, start_image_url, video_url) "
                "VALUES (:row_id, :trainer, :name, :start, :video)"
            ),
            [
                {
                    "row_id": "tr-squat",
                    "trainer": "trainer-a",
                    "name": "  приседания   со штангой ",
                    "start": "photos/trainer-a/tr-squat/start/copy.jpg",
                    "video": None,
                },
                {
                    "row_id": "tr-press",
                    "trainer": "trainer-a",
                    "name": "Жим",
                    "start": None,
                    "video": None,
                },
                {
                    "row_id": "tr-row",
                    "trainer": "trainer-a",
                    "name": "Тяга",
                    "start": None,
                    "video": None,
                },
                {
                    "row_id": "tr-other",
                    "trainer": "trainer-b",
                    "name": "Жим",
                    "start": "photos/trainer-b/tr-other/start/copy.jpg",
                    "video": "videos/trainer-b/tr-other/copy.mp4",
                },
            ],
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        rows = {
            row.row_id: row
            for row in connection.execute(
                text(
                    "SELECT row_id, source_platform_exercise_id, synced_start_image_key, synced_video_key "
                    "FROM trainer_exercises"
                )
            )
        }
    columns = {column["name"] for column in inspect(engine).get_columns("trainer_exercises")}
    engine.dispose()
    assert {
        "source_platform_exercise_id",
        "synced_video_key",
        "synced_start_image_key",
        "synced_end_image_key",
    } <= columns
    assert rows["tr-squat"].source_platform_exercise_id == "plat-squat"
    assert rows["tr-squat"].synced_start_image_key == "photos/platform/plat-squat/start/a.jpg"
    assert rows["tr-press"].source_platform_exercise_id == "plat-press"
    assert rows["tr-press"].synced_start_image_key is None
    assert rows["tr-press"].synced_video_key is None
    assert rows["tr-row"].source_platform_exercise_id is None
    assert rows["tr-other"].source_platform_exercise_id == "plat-press"
    assert rows["tr-other"].synced_video_key == "videos/platform/plat-press/a.mp4"

    command.downgrade(config, "0021_plan_notes_times")
    engine = create_engine(url)
    columns = {column["name"] for column in inspect(engine).get_columns("trainer_exercises")}
    engine.dispose()
    assert "source_platform_exercise_id" not in columns

    command.upgrade(config, "head")


def test_archived_trainer_row_is_not_offered_as_add_or_media_update() -> None:
    platform = [_platform("p1", "Squat", start="photos/platform/p1/new.jpg")]
    trainer = [
        _trainer(
            "t1",
            "Squat",
            source="p1",
            is_active=False,
            synced_start="photos/platform/p1/old.jpg",
        )
    ]
    plan = match_catalog(platform, trainer)
    assert plan.add == ()
    assert plan.update == ()
    assert plan.unchanged_count == 1
    assert plan.links[0].trainer_is_active is False
