from scripts import setup_metabase


def valid_environment() -> dict[str, str]:
    return {
        "LOCAL_DATABASE_URL": "postgresql+psycopg://vwdp:secret@localhost:5433/vwdp",
        "METABASE_WAREHOUSE_PASSWORD": "reader-secret",
        "METABASE_ADMIN_EMAIL": "admin@example.com",
        "METABASE_ADMIN_PASSWORD": "admin-secret",
        "METABASE_ADMIN_FIRST_NAME": "VWDP",
        "METABASE_ADMIN_LAST_NAME": "Admin",
    }


def test_main_bootstraps_from_supplied_environment(monkeypatch, capsys) -> None:
    received = []
    monkeypatch.setattr(
        setup_metabase,
        "bootstrap_metabase",
        lambda settings: received.append(settings),
    )

    result = setup_metabase.main(valid_environment())

    assert result == 0
    assert received[0].admin_email == "admin@example.com"
    assert capsys.readouterr().out == "Metabase setup completed.\n"


def test_main_hides_credentials_on_failure(monkeypatch, capsys) -> None:
    def fail(_settings) -> None:
        raise RuntimeError("admin-secret reader-secret")

    monkeypatch.setattr(setup_metabase, "bootstrap_metabase", fail)

    result = setup_metabase.main(valid_environment())

    assert result == 1
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "admin-secret" not in error
    assert "reader-secret" not in error
