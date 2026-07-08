from src.api.app import create_app


def test_required_routes_are_registered() -> None:
    paths = {route.path for route in create_app().routes}
    assert "/health" in paths
    assert "/districts" in paths
    assert "/districts/{district_id}" in paths
    assert "/districts/{district_id}/daily" in paths
    assert "/districts/{district_id}/hourly" in paths
    assert "/districts/{district_id}/aqi" in paths
    assert "/daily" in paths
    assert "/hourly" in paths
    assert "/aqi" in paths
    assert "/statistics" in paths
