from application.generation.policy import GenerationPolicyConfig


def test_session_bounds_defaults_match_legacy_hardcoded() -> None:
    policy = GenerationPolicyConfig()
    assert policy.session_bounds_for(level="beginner", goal="maintenance", is_first_plan=True) == (3, 5)
    assert policy.session_bounds_for(level="intermediate", goal="maintenance", is_first_plan=True) == (4, 6)
    assert policy.session_bounds_for(level="advanced", goal="maintenance", is_first_plan=True) == (4, 7)
    assert policy.session_bounds_for(level="beginner", goal="rehabilitation", is_first_plan=True) == (3, 4)
    assert policy.session_bounds_for(level="beginner", goal="maintenance", is_first_plan=False) == (4, 7)


def test_session_bounds_from_policy_override() -> None:
    policy = GenerationPolicyConfig.from_dict(
        {
            "exercises_per_session": {
                "default": {"min": 2, "max": 3},
                "beginner": {"min": 5, "max": 5},
            }
        }
    )
    assert policy.session_bounds_for(level="beginner", goal="maintenance", is_first_plan=True) == (5, 5)
    assert policy.session_bounds_for(level="beginner", goal="maintenance", is_first_plan=False) == (2, 3)


def test_to_dict_exposes_exercises_per_session_defaults() -> None:
    payload = GenerationPolicyConfig().to_dict()
    assert "exercises_per_session" in payload
    assert payload["exercises_per_session"]["default"] == {"min": 4, "max": 7}
    assert payload["exercises_per_session"]["beginner"] == {"min": 3, "max": 5}
