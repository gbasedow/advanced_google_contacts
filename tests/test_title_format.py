import pytest
from custom_components.advanced_google_contacts.title_format import TitleFormatError, render_title, validate_title_format


@pytest.mark.parametrize("fmt,values,expected", [
    ("Geburtstag {name}[ - {age}]", {"name": "Anna", "age": "34"}, "Geburtstag Anna - 34"),
    ("Geburtstag {name}[ - {age}]", {"name": "Anna"}, "Geburtstag Anna"),
    ("{type}: {last_name}, {first_name}[ ({year})]", {"type": "Jahrestag", "first_name": "A", "last_name": "B", "year": "2010"}, "Jahrestag: B, A (2010)"),
    ("{name}", {"name": "A{b}"}, "A{b}"),
])
def test_render(fmt, values, expected):
    assert render_title(validate_title_format(fmt), values) == expected


@pytest.mark.parametrize("fmt", ["", "  ", "Geb {age}", "X {nme}", "X {name", "X [{name}", "X [[{age}]] {name}", "X {name!r}", "X {name:>5}", "{0} {name}"])
def test_invalid(fmt):
    with pytest.raises(TitleFormatError):
        validate_title_format(fmt)
