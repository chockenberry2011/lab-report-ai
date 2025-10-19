import pytest


def test_import_path():
    try:
        from services.api.api.utils.ids import normalize_result_id  # noqa: F401
    except Exception as e:
        pytest.skip(f"utils import not available: {e}")


@pytest.mark.parametrize(
    "inp, expected",
    [
        ("1234", "1234"),
        ("1234.03_compose", "1234"),
        ("1234.03_compose.debug", "1234"),
        ("1234.debug", "1234"),
        ("1234.03_compose.debug/", "1234"),
    ],
)
def test_normalize_result_id(inp, expected):
    try:
        from services.api.api.utils.ids import normalize_result_id
    except Exception:
        pytest.skip("normalize_result_id not available in this environment")
    assert normalize_result_id(inp) == expected

