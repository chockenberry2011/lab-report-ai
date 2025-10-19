import pytest
from api.api.corrections.normalize import normalize_correction_item, normalize_items


def test_normalize_single_item_vendor_name():
    item = {"field": "vendor.name", "new_value": "Acme Co"}
    norm, stats = normalize_correction_item(item)
    assert norm["field"] == "vendor_name"
    assert norm["value"] == "Acme Co"
    assert stats["canonicalized"] == 1
    assert stats["value_filled"] == 1


def test_normalize_items_mixed():
    items = [
        {"field": "vendor.name", "new_value": "Acme"},  # canonical + fill
        {"field": "result_value", "value": "42"},       # already fine
        {"field": "unknown.key", "value": "x"},          # unknown
    ]
    out, stats = normalize_items(items)
    assert out[0]["field"] == "vendor_name"
    assert out[0]["value"] == "Acme"
    assert out[1]["field"] == "result_value"
    assert out[2]["field"] == "unknown.key"  # left as-is
    assert stats["canonicalized"] == 1
    assert stats["value_filled"] == 1
    assert stats["unknown_fields"] == 1

