from pathlib import Path

import yaml


EXPECTED_HTFT_THRESHOLDS = {
    "win_win": 32.5,
    "win_draw": 17.5,
    "win_lose": 22.5,
    "draw_win": 22.5,
    "draw_draw": 17.5,
    "draw_lose": 22.5,
    "lose_win": 22.5,
    "lose_draw": 17.5,
    "lose_lose": 32.5,
}


def _rules_by_id() -> dict[str, dict]:
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {
        rule["id"]: rule
        for rule in config["recommendations"]["rules"]
    }


def test_htft_thresholds_are_symmetric_and_enabled():
    rules = _rules_by_id()

    for rule_id, expected_threshold in EXPECTED_HTFT_THRESHOLDS.items():
        rule = rules[rule_id]
        condition = rule["conditions"][0]

        assert rule["enabled"] is True
        assert condition["threshold_home"] == expected_threshold
        assert condition["threshold_away"] == expected_threshold

    assert rules["win_win"]["conditions"][0]["threshold_home"] == rules["lose_lose"]["conditions"][0]["threshold_home"]
    assert rules["win_draw"]["conditions"][0]["threshold_home"] == rules["lose_draw"]["conditions"][0]["threshold_home"]
    assert rules["draw_win"]["conditions"][0]["threshold_home"] == rules["draw_lose"]["conditions"][0]["threshold_home"]
    assert rules["win_lose"]["conditions"][0]["threshold_home"] == rules["lose_win"]["conditions"][0]["threshold_home"]
