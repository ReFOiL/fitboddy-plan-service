from application.muscle_catalog import MUSCLE_SLUGS, MUSCLE_ZONE_BY_SLUG, derive_workout_category


def test_every_seed_muscle_has_zone() -> None:
    assert set(MUSCLE_ZONE_BY_SLUG) == MUSCLE_SLUGS


def test_derive_workout_category_rules() -> None:
    assert derive_workout_category([]) == "full_body"
    assert derive_workout_category(["chest", "biceps"]) == "upper"
    assert derive_workout_category(["quadriceps", "glutes"]) == "lower"
    assert derive_workout_category(["abs", "obliques"]) == "core"
    assert derive_workout_category(["chest", "abs"]) == "upper"
    assert derive_workout_category(["hamstrings", "core"]) == "lower"
    assert derive_workout_category(["chest", "quadriceps"]) == "full_body"
    assert derive_workout_category(["chest", "abs", "glutes"]) == "full_body"
