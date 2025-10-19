from services.api.api.utils.paths import split_path
from services.api.api.utils.corrections import apply_corrections

def test_split_path_variants():
    assert split_path("patient.first_name") == ["patient", "first_name"]
    assert split_path("panels[0].tests[2].value") == ["panels", 0, "tests", 2, "value"]
    assert split_path("/panels/0/tests/2/value") == ["panels", 0, "tests", 2, "value"]

def test_apply_set_and_unset():
    base = {"patient": {"first_name": "Ann", "mrn": "123"}, "panels": [{"tests": [{"value": "1"}]}]}
    items = [
        {"op":"set","path":"patient.first_name","value":"Alice"},
        {"op":"unset","path":"patient.mrn"},
        {"op":"set","path":"panels[0].tests[0].value","value":"2"},
    ]
    out = apply_corrections(base, items)
    assert out["patient"]["first_name"] == "Alice"
    assert "mrn" not in out["patient"]
    assert out["panels"][0]["tests"][0]["value"] == "2"