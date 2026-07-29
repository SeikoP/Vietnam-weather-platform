from __future__ import annotations

from pathlib import Path

import yaml


def test_etl_workflow_has_seven_visible_failure_boundaries() -> None:
    workflow = yaml.load(
        Path(".github/workflows/etl.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    assert list(workflow["jobs"]) == [
        "validate",
        "prepare-database",
        "collect-daily",
        "collect-hourly",
        "collect-aqi",
        "publish-r2",
        "summary",
    ]
    assert workflow["jobs"]["prepare-database"]["needs"] == "validate"
    assert workflow["jobs"]["publish-r2"]["needs"] == [
        "collect-daily",
        "collect-hourly",
        "collect-aqi",
    ]
    assert workflow["jobs"]["summary"]["if"] == "always()"


def test_r2_publish_runs_only_after_all_scheduled_collectors_succeed() -> None:
    workflow = yaml.load(
        Path(".github/workflows/etl.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    condition = workflow["jobs"]["publish-r2"]["if"]

    assert "github.event_name == 'schedule'" in condition
    assert "needs.collect-daily.result == 'success'" in condition
    assert "needs.collect-hourly.result == 'success'" in condition
    assert "needs.collect-aqi.result == 'success'" in condition

