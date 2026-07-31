from pathlib import Path

LOADER_PATH = Path(__file__).parents[2] / "powerbi" / "r2_tables.pq"
R2_BASE_URL = "https://pub-74b943718d324227b2990146d782734c.r2.dev"
TABLES = (
    "dim_district",
    "dim_date",
    "dim_hour",
    "fact_weather_daily",
    "fact_weather_hourly",
    "fact_aqi_hourly",
)


def read_loader() -> str:
    assert LOADER_PATH.exists(), f"Missing Power Query loader: {LOADER_PATH}"
    return LOADER_PATH.read_text(encoding="utf-8")


def test_loader_uses_one_static_r2_data_source() -> None:
    loader = read_loader()

    assert loader.count(R2_BASE_URL) == 1
    assert "Web.Contents(" in loader
    assert "R2BaseUrl," in loader
    assert "RelativePath = AnalystPrefix & tableName & \".csv\"" in loader


def test_loader_exposes_all_six_analyst_tables() -> None:
    loader = read_loader()

    for table in TABLES:
        assert f'{table} = LoadR2Table("{table}")' in loader
