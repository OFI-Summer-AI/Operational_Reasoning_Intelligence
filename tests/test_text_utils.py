from layers.ingestion.text_utils import normalize_unicode_text


def test_normalize_em_dash():
    assert normalize_unicode_text("Revenue Dashboard Unavailable \u2014 P1") == (
        "Revenue Dashboard Unavailable - P1"
    )


def test_repair_mojibake_em_dash():
    broken = "Revenue Dashboard Unavailable — P1".encode("utf-8").decode("latin-1")
    fixed = normalize_unicode_text(broken)
    assert " - P1" in fixed
    assert "â" not in fixed
