from app.utils import parse_number


def test_parse_number():
    assert parse_number("91.3B") == 91.3e9
    assert parse_number("524M") == 524e6
    assert parse_number("1.42") == 1.42
    assert parse_number("12,345") == 12345
    assert parse_number(None) is None
    assert parse_number("invalid") is None
