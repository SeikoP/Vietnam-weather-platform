from pathlib import Path


def test_setup_python_does_not_use_poetry_cache_before_poetry_is_installed():
    action_file = (
        Path(__file__).parents[2] / ".github" / "actions" / "setup-python-poetry" / "action.yml"
    )
    action = action_file.read_text(encoding="utf-8")

    setup_python_block = action.split("- uses: actions/setup-python@v5", maxsplit=1)[1].split(
        "- name: Install Poetry", maxsplit=1
    )[0]

    assert "cache: poetry" not in setup_python_block


def test_ci_job_provides_a_database_url_for_settings():
    workflow_file = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"
    workflow = workflow_file.read_text(encoding="utf-8")

    test_step = workflow.split("- name: Run tests", maxsplit=1)[1].split(
        "- name: Run Ruff", maxsplit=1
    )[0]

    assert "DATABASE_URL:" in test_step


def test_ci_runs_when_changes_are_pushed_to_main():
    workflow_file = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"
    workflow = workflow_file.read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "- main" in workflow


def test_etl_does_not_run_source_validation():
    workflow_file = Path(__file__).parents[2] / ".github" / "workflows" / "etl.yml"
    workflow = workflow_file.read_text(encoding="utf-8")

    assert "poetry run pytest" not in workflow
    assert "poetry run ruff check" not in workflow
