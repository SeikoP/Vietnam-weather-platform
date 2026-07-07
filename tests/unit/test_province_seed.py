from src.database.seeds.provinces import PROVINCES


def test_province_seed_contains_historical_63_provinces() -> None:
    province_ids = [province[0] for province in PROVINCES]

    assert len(PROVINCES) == 63
    assert sorted(province_ids) == list(range(1, 64))
