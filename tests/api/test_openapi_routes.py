from src.api.app import create_app


def test_required_routes_are_registered() -> None:
    paths = {route.path for route in create_app().routes}

    assert "/health" in paths
    assert "/provinces" in paths
    assert "/weather" in paths
    assert "/daily" in paths
    assert "/hourly" in paths
    assert "/statistics" in paths
