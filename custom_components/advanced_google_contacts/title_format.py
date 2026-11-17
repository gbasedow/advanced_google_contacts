"""Title templates for calendar entries.

Placeholders: {name}, {first_name}, {last_name}, {type}, {age}, {year}.
Text in square brackets is optional: it is left out when one of its
placeholders is empty, e.g. "Geburtstag {name}[ - {age}]" gives
"Geburtstag Anna - 34", or "Geburtstag Anna" when the birth year is unknown.
"""
from __future__ import annotations

import re
import string

PLACEHOLDERS = ("name", "first_name", "last_name", "type", "age", "year")
NAME_PLACEHOLDERS = ("name", "first_name", "last_name")
_OPTIONAL = re.compile(r"\[([^\[\]]*)\]")
_FORMATTER = string.Formatter()


class TitleFormatError(ValueError):
    """The title format is invalid."""


def _fields(text: str) -> list[str]:
    try:
        parsed = list(_FORMATTER.parse(text))
    except ValueError as err:  # unbalanced braces
        raise TitleFormatError(str(err)) from err
    fields = []
    for _literal, field, spec, conversion in parsed:
        if field is None:
            continue
        if field not in PLACEHOLDERS or spec or conversion:
            raise TitleFormatError(f"Ungültiger Platzhalter: {{{field}}}")
        fields.append(field)
    return fields


def _parts(fmt: str):
    """Yield (text, optional) pieces of the format."""
    pos = 0
    for match in _OPTIONAL.finditer(fmt):
        yield fmt[pos:match.start()], False
        yield match.group(1), True
        pos = match.end()
    yield fmt[pos:], False


def validate_title_format(fmt: str) -> str:
    """Return the stripped format or raise TitleFormatError."""
    if not isinstance(fmt, str) or not fmt.strip():
        raise TitleFormatError("Das Format darf nicht leer sein.")
    fmt = fmt.strip()
    used: list[str] = []
    for text, optional in _parts(fmt):
        if not optional and ("[" in text or "]" in text):
            raise TitleFormatError("Eckige Klammern müssen paarweise und ohne Verschachtelung stehen.")
        used += _fields(text)
    if not any(field in NAME_PLACEHOLDERS for field in used):
        raise TitleFormatError("Das Format braucht {name}, {first_name} oder {last_name}.")
    return fmt


def render_title(fmt: str, values: dict[str, str]) -> str:
    """Render a validated format. Missing values count as empty."""
    safe = {key: str(values.get(key) or "") for key in PLACEHOLDERS}
    out = []
    for text, optional in _parts(fmt):
        if optional and any(not safe[field] for field in _fields(text)):
            continue
        out.append(text.format_map(safe))
    return "".join(out).strip()
