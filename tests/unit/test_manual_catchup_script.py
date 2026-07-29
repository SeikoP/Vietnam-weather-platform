from pathlib import Path


def test_manual_catchup_publishes_and_verifies_r2_after_all_etl_types():
    script_path = Path(__file__).parents[2] / "scripts" / "run_manual_catchup.ps1"
    script = script_path.read_text(encoding="utf-8")

    assert "if (-not $SkipR2 -and $RunType -eq 'all')" in script
    assert "scripts/publish_r2_release.py" in script
    assert "'--force-republish'" in script
    assert "'--verify-only'" in script
