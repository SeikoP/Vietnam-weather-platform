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
