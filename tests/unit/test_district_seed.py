from src.database.seeds.districts import DISTRICTS


def test_district_seed_contains_hanoi_30_districts() -> None:
    district_ids = [d[0] for d in DISTRICTS]
    assert len(DISTRICTS) == 30
    assert sorted(district_ids) == list(range(1, 31))
