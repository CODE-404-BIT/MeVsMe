from betmodel.normalize import normalize_name, canonical_market_key


def test_normalize_name_removes_punctuation_and_case():
    assert normalize_name("Paris Saint-Germain FC") == "paris saint germain fc"


def test_market_aliases_are_canonical():
    assert canonical_market_key("Over 2.5 Goals") == "TOTAL_GOALS_OVER"
    assert canonical_market_key("1X2 Home") == "MATCH_HOME"


def test_unknown_market_fails_closed():
    assert canonical_market_key("Mystery Prop") == "UNKNOWN:mystery prop"
