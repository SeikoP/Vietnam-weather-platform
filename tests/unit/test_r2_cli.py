from __future__ import annotations

from datetime import UTC, date, datetime

from scripts import bootstrap_r2_history, publish_r2_release


def test_bootstrap_fails_safely_when_local_database_url_is_missing(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("LOCAL_DATABASE_URL", raising=False)

    assert bootstrap_r2_history.main([]) == 1
    captured = capsys.readouterr()
    assert "LOCAL_DATABASE_URL" in captured.err
    assert "postgresql://" not in captured.err


def test_default_publish_target_is_yesterday_in_vietnam() -> None:
    now = datetime(2026, 7, 29, 18, 15, tzinfo=UTC)

    assert publish_r2_release.default_target_date(now) == date(2026, 7, 29)


def test_publish_cli_passes_bounded_force_repair_to_service(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeService:
        def publish_incremental(self, **kwargs):
            calls.append(kwargs)
            return None

    class FakePublisher:
        def verify_bucket(self) -> None:
            return None

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example")
    monkeypatch.setenv("R2_ACCOUNT_ID", "account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "access")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "weather")
    monkeypatch.setattr(
        publish_r2_release,
        "create_service",
        lambda *_args, **_kwargs: (FakeService(), FakePublisher(), object()),
    )

    result_path = tmp_path / "result.json"
    exit_code = publish_r2_release.main(
        [
            "--start-date",
            "2026-07-28",
            "--end-date",
            "2026-07-28",
            "--force-republish",
            "--result-json",
            str(result_path),
        ]
    )

    assert exit_code == 0
    assert calls == [
        {
            "target_date": date(2026, 7, 28),
            "start_date": date(2026, 7, 28),
            "end_date": date(2026, 7, 28),
            "force_republish": True,
        }
    ]
    assert '"status": "noop"' in result_path.read_text(encoding="utf-8")

